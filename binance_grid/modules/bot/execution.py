from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math

import numpy as np


class GridBias(StrEnum):
    LONG = "long"
    NEUTRAL = "neutral"
    SHORT = "short"


@dataclass(frozen=True)
class GridExecutionConfig:
    levels_per_side: int = 6
    min_spacing_bps: float = 35.0
    max_spacing_bps: float = 500.0
    rebalance_speed: float = 0.18


@dataclass(frozen=True)
class GridExecutionControl:
    regime: GridBias
    center_price: float
    spacing_pct: float
    buy_order_notional: float
    sell_order_notional: float
    long_notional_limit: float
    short_notional_limit: float
    buy_levels: tuple[float, ...]
    sell_levels: tuple[float, ...]


@dataclass(frozen=True)
class GridExecutionSnapshot:
    asset_symbol: str
    timestamp: datetime | None
    regime: GridBias
    price: float
    center_price: float
    spacing_pct: float
    inventory: float
    gross_notional: float
    cash: float
    realized_pnl: float
    equity: float
    active_grid_levels: int
    grid_levels_crossed_in_step: int
    fills_in_step: int
    cumulative_grid_levels_crossed: int
    cumulative_fills: int


class GridExecutionBot:
    def __init__(self, asset_symbol: str, config: GridExecutionConfig | None = None) -> None:
        self.asset_symbol = asset_symbol
        self.config = config or GridExecutionConfig()
        self.inventory = 0.0
        self.average_entry_price = 0.0
        self.cash = 0.0
        self.realized_pnl = 0.0
        self.center_price: float | None = None
        self.last_price: float | None = None
        self.cumulative_grid_levels_crossed = 0
        self.cumulative_fills = 0

    def make_control(
        self,
        *,
        price: float,
        spacing_pct: float,
        regime: GridBias,
        order_notional: float,
        inventory_limit_notional: float,
    ) -> GridExecutionControl:
        center_price = price if self.center_price is None else self.center_price + (price - self.center_price) * self.config.rebalance_speed
        spacing_pct = _clamp(
            spacing_pct,
            self.config.min_spacing_bps / 10_000.0,
            self.config.max_spacing_bps / 10_000.0,
        )
        bias_shift = 0.45 * spacing_pct
        buy_levels = self.config.levels_per_side
        sell_levels = self.config.levels_per_side
        buy_multiplier = 1.0
        sell_multiplier = 1.0
        long_limit_multiplier = 1.0
        short_limit_multiplier = 1.0

        if regime == GridBias.LONG:
            center_price *= 1.0 - bias_shift
            buy_levels += 2
            sell_levels = max(2, sell_levels - 2)
            buy_multiplier = 1.25
            sell_multiplier = 0.85
            long_limit_multiplier = 1.35
            short_limit_multiplier = 0.65
        elif regime == GridBias.SHORT:
            center_price *= 1.0 + bias_shift
            buy_levels = max(2, buy_levels - 2)
            sell_levels += 2
            buy_multiplier = 0.85
            sell_multiplier = 1.25
            long_limit_multiplier = 0.65
            short_limit_multiplier = 1.35

        return GridExecutionControl(
            regime=regime,
            center_price=center_price,
            spacing_pct=spacing_pct,
            buy_order_notional=order_notional * buy_multiplier,
            sell_order_notional=order_notional * sell_multiplier,
            long_notional_limit=inventory_limit_notional * long_limit_multiplier,
            short_notional_limit=inventory_limit_notional * short_limit_multiplier,
            buy_levels=tuple(center_price * (1.0 - spacing_pct * level) for level in range(1, buy_levels + 1)),
            sell_levels=tuple(center_price * (1.0 + spacing_pct * level) for level in range(1, sell_levels + 1)),
        )

    def step(
        self,
        timestamp: datetime | None,
        *,
        price: float,
        spacing_pct: float,
        regime: GridBias,
        order_notional: float,
        inventory_limit_notional: float,
    ) -> GridExecutionSnapshot:
        control = self.make_control(
            price=price,
            spacing_pct=spacing_pct,
            regime=regime,
            order_notional=order_notional,
            inventory_limit_notional=inventory_limit_notional,
        )
        grid_levels_crossed_in_step = 0
        fills_in_step = 0

        self.center_price = control.center_price
        if self.last_price is not None:
            grid_distance = max(control.center_price * control.spacing_pct, price * 1e-6)
            price_change = price - self.last_price
            steps_crossed = int(math.floor(abs(price_change) / grid_distance + 1e-9))
            grid_levels_crossed_in_step = steps_crossed
            self.cumulative_grid_levels_crossed += steps_crossed
            if steps_crossed > 0:
                for step in range(1, steps_crossed + 1):
                    if price_change < 0.0:
                        fill_price = max(self.last_price - grid_distance * step, price)
                        fills_in_step += int(self._buy_on_dip(fill_price, control))
                    else:
                        fill_price = min(self.last_price + grid_distance * step, price)
                        fills_in_step += int(self._sell_on_rally(fill_price, control))

        self.cumulative_fills += fills_in_step
        self.last_price = price
        gross_notional = abs(self.inventory) * price
        equity = self.cash + self.inventory * price
        return GridExecutionSnapshot(
            asset_symbol=self.asset_symbol,
            timestamp=timestamp,
            regime=control.regime,
            price=price,
            center_price=control.center_price,
            spacing_pct=control.spacing_pct,
            inventory=self.inventory,
            gross_notional=gross_notional,
            cash=self.cash,
            realized_pnl=self.realized_pnl,
            equity=equity,
            active_grid_levels=len(control.buy_levels) + len(control.sell_levels),
            grid_levels_crossed_in_step=grid_levels_crossed_in_step,
            fills_in_step=fills_in_step,
            cumulative_grid_levels_crossed=self.cumulative_grid_levels_crossed,
            cumulative_fills=self.cumulative_fills,
        )

    def seed_position(self, *, direction: GridBias, notional: float, price: float) -> None:
        quantity = notional / max(price, 1e-9)
        if direction == GridBias.LONG:
            self._execute_buy(quantity, price)
        elif direction == GridBias.SHORT:
            self._execute_sell(quantity, price)

    def close_all(self, price: float) -> None:
        if self.inventory > 0.0:
            self._execute_sell(self.inventory, price)
        elif self.inventory < 0.0:
            self._execute_buy(abs(self.inventory), price)

    def _buy_on_dip(self, fill_price: float, control: GridExecutionControl) -> bool:
        long_limit_units = control.long_notional_limit / max(fill_price, 1e-9)
        room = max(long_limit_units - self.inventory, 0.0)
        quantity = min(control.buy_order_notional / max(fill_price, 1e-9), room)
        return self._execute_buy(quantity, fill_price)

    def _sell_on_rally(self, fill_price: float, control: GridExecutionControl) -> bool:
        short_limit_units = control.short_notional_limit / max(fill_price, 1e-9)
        room = max(self.inventory + short_limit_units, 0.0)
        quantity = min(control.sell_order_notional / max(fill_price, 1e-9), room)
        return self._execute_sell(quantity, fill_price)

    def _execute_buy(self, quantity: float, price: float) -> bool:
        if quantity <= 0.0:
            return False

        self.cash -= quantity * price
        if self.inventory < 0.0:
            closing_quantity = min(quantity, abs(self.inventory))
            self.realized_pnl += (self.average_entry_price - price) * closing_quantity
            self.inventory += closing_quantity
            quantity -= closing_quantity
            if abs(self.inventory) < 1e-12:
                self.inventory = 0.0
                self.average_entry_price = 0.0

        if quantity > 0.0:
            if self.inventory > 0.0:
                total_cost = (self.average_entry_price * self.inventory) + (price * quantity)
                self.inventory += quantity
                self.average_entry_price = total_cost / self.inventory
            else:
                self.inventory = quantity
                self.average_entry_price = price
        return True

    def _execute_sell(self, quantity: float, price: float) -> bool:
        if quantity <= 0.0:
            return False

        self.cash += quantity * price
        if self.inventory > 0.0:
            closing_quantity = min(quantity, self.inventory)
            self.realized_pnl += (price - self.average_entry_price) * closing_quantity
            self.inventory -= closing_quantity
            quantity -= closing_quantity
            if abs(self.inventory) < 1e-12:
                self.inventory = 0.0
                self.average_entry_price = 0.0

        if quantity > 0.0:
            if self.inventory < 0.0:
                total_proceeds = (self.average_entry_price * abs(self.inventory)) + (price * quantity)
                self.inventory -= quantity
                self.average_entry_price = total_proceeds / abs(self.inventory)
            else:
                self.inventory = -quantity
                self.average_entry_price = price
        return True


def _clamp(value: float, lower_bound: float, upper_bound: float) -> float:
    return max(lower_bound, min(value, upper_bound))