from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Mapping

import numpy as np

from .simulation import SimulationResult
from .strategy import BotSnapshot, GridBias, GridTradingBot


@dataclass(frozen=True)
class ManagerConfig:
    lookback: int = 45
    starting_capital: float = 250_000.0
    target_portfolio_vol: float = 0.20
    max_single_asset_weight: float = 0.38
    max_gross_leverage: float = 1.80
    correlation_penalty: float = 0.65
    drawdown_soft_limit: float = 0.12


@dataclass(frozen=True)
class AssetControlDirective:
    symbol: str
    regime: GridBias
    annualized_vol: float
    weight: float
    spacing_scale: float
    order_notional: float
    inventory_limit_notional: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    timestamp: datetime | None
    portfolio_equity: float
    gross_exposure: float
    controls: dict[str, AssetControlDirective]
    asset_snapshots: dict[str, BotSnapshot]


class AssetGridManager:
    def __init__(
        self,
        bots: Mapping[str, GridTradingBot],
        config: ManagerConfig | None = None,
    ) -> None:
        if not bots:
            raise ValueError("manager requires at least one grid bot")

        self.bots = dict(bots)
        self.config = config or ManagerConfig()
        self.price_history = {symbol: [] for symbol in self.bots}
        self.current_equity = self.config.starting_capital
        self.equity_curve: list[float] = [self.current_equity]

    def review_asset_controls(self) -> dict[str, AssetControlDirective]:
        symbols = tuple(self.bots)
        weights = np.full(len(symbols), 1.0 / len(symbols), dtype=float)
        annualized_vols = np.full(len(symbols), self.config.target_portfolio_vol, dtype=float)
        average_correlations = np.zeros(len(symbols), dtype=float)

        price_lengths = [len(self.price_history[symbol]) for symbol in symbols]
        if min(price_lengths) >= 3:
            lookback = min(min(price_lengths) - 1, self.config.lookback)
            price_matrix = np.column_stack(
                [
                    np.asarray(self.price_history[symbol][-lookback - 1 :], dtype=float)
                    for symbol in symbols
                ]
            )
            return_matrix = np.diff(np.log(price_matrix), axis=0)
            annualized_vols = np.nan_to_num(
                return_matrix.std(axis=0, ddof=1) * math.sqrt(365),
                nan=self.config.target_portfolio_vol,
            )
            correlation = np.eye(len(symbols), dtype=float)
            if len(return_matrix) > 1:
                correlation = np.nan_to_num(np.corrcoef(return_matrix, rowvar=False), nan=0.0)
                np.fill_diagonal(correlation, 1.0)
            average_correlations = np.array(
                [
                    (np.clip(correlation[index], 0.0, None).sum() - 1.0) / max(len(symbols) - 1, 1)
                    for index in range(len(symbols))
                ],
                dtype=float,
            )
            raw_weights = 1.0 / np.maximum(annualized_vols, 0.08)
            raw_weights /= 1.0 + self.config.correlation_penalty * average_correlations
            weights = _cap_weights(raw_weights, self.config.max_single_asset_weight)

        peak_equity = max(self.equity_curve)
        drawdown = max(0.0, 1.0 - (self.current_equity / peak_equity))
        risk_scalar = 0.55 if drawdown > self.config.drawdown_soft_limit else 1.0
        spacing_drawdown = 1.25 if drawdown > self.config.drawdown_soft_limit else 1.0

        controls: dict[str, AssetControlDirective] = {}
        for index, symbol in enumerate(symbols):
            annualized_vol = max(float(annualized_vols[index]), 0.05)
            bot = self.bots[symbol]
            regime = bot.infer_regime(self.price_history[symbol], annualized_vol)
            if average_correlations[index] > 0.65 and annualized_vol > 0.85:
                regime = GridBias.NEUTRAL

            inventory_limit_notional = self.current_equity * weights[index] * self.config.max_gross_leverage * risk_scalar
            order_notional = min(
                max(inventory_limit_notional / (bot.config.levels_per_side * 4.0), bot.config.base_order_notional * 0.30),
                inventory_limit_notional / 2.0,
            )
            spacing_scale = (
                1.0
                + (0.40 * average_correlations[index])
                + (0.45 * max(annualized_vol - self.config.target_portfolio_vol, 0.0))
            ) * spacing_drawdown
            controls[symbol] = AssetControlDirective(
                symbol=symbol,
                regime=regime,
                annualized_vol=annualized_vol,
                weight=float(weights[index]),
                spacing_scale=spacing_scale,
                order_notional=order_notional,
                inventory_limit_notional=inventory_limit_notional,
            )

        return controls

    def step(
        self,
        timestamp: datetime | None,
        prices: Mapping[str, float],
    ) -> PortfolioSnapshot:
        missing_symbols = set(self.bots).difference(prices)
        if missing_symbols:
            missing_display = ", ".join(sorted(missing_symbols))
            raise KeyError(f"missing prices for: {missing_display}")

        for symbol, price in prices.items():
            self.price_history[symbol].append(float(price))

        controls = self.review_asset_controls()
        asset_snapshots: dict[str, BotSnapshot] = {}
        for symbol, bot in self.bots.items():
            control = controls[symbol]
            asset_snapshots[symbol] = bot.step(
                timestamp,
                float(prices[symbol]),
                annualized_vol=control.annualized_vol,
                regime=control.regime,
                spacing_scale=control.spacing_scale,
                order_notional=control.order_notional,
                inventory_limit_notional=control.inventory_limit_notional,
            )

        strategy_equity = sum(snapshot.equity for snapshot in asset_snapshots.values())
        portfolio_equity = self.config.starting_capital + strategy_equity
        gross_exposure = sum(snapshot.gross_notional for snapshot in asset_snapshots.values()) / max(portfolio_equity, 1e-9)

        self.current_equity = portfolio_equity
        self.equity_curve.append(portfolio_equity)

        return PortfolioSnapshot(
            timestamp=timestamp,
            portfolio_equity=portfolio_equity,
            gross_exposure=gross_exposure,
            controls=controls,
            asset_snapshots=asset_snapshots,
        )

    def run_simulation(self, simulation: SimulationResult) -> list[PortfolioSnapshot]:
        snapshots: list[PortfolioSnapshot] = []
        for index, timestamp in enumerate(simulation.timestamps[1:], start=1):
            prices = {
                symbol: float(simulation.prices[index, column])
                for column, symbol in enumerate(simulation.asset_symbols)
            }
            snapshots.append(self.step(timestamp, prices))
        return snapshots


def _cap_weights(raw_weights: np.ndarray, max_weight: float) -> np.ndarray:
    normalized = raw_weights / raw_weights.sum()
    result = np.zeros_like(normalized)
    free = np.ones_like(normalized, dtype=bool)
    remaining = 1.0

    while np.any(free):
        free_indices = np.where(free)[0]
        scaled = normalized[free_indices] / normalized[free_indices].sum() * remaining
        over_mask = scaled > max_weight
        if not np.any(over_mask):
            result[free_indices] = scaled
            break

        over_indices = free_indices[over_mask]
        result[over_indices] = max_weight
        free[over_indices] = False
        remaining = 1.0 - result.sum()
        if remaining <= 1e-12:
            break

    total = result.sum()
    if total <= 0.0:
        return np.full_like(result, 1.0 / len(result))
    return result / total
