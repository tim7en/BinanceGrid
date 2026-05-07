from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from ..common import MarketBar
from ..indicators import IndicatorSnapshot, TrendRegime, build_indicator_snapshot
from ..macro_regime import MacroRegimeState, MacroRiskRegime, assess_macro_regime
from ..risk_control import GridRiskPlan, build_grid_risk_plan
from .execution import GridBias, GridExecutionBot, GridExecutionSnapshot


class BotStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


@dataclass(frozen=True)
class SingleAssetInput:
    daily_bars: tuple[MarketBar, ...]
    intraday_bars: tuple[MarketBar, ...]
    dxy_values: tuple[float, ...]
    spread_10y2y_values: tuple[float, ...]
    spread_2y3m_values: tuple[float, ...]
    vix_values: tuple[float, ...]
    fear_greed_values: tuple[float, ...]


@dataclass(frozen=True)
class SingleAssetBotConfig:
    allocated_capital: float
    savings_rate: float = 0.30
    compounding_rate: float = 0.70
    macro_pause_days: int = 1
    loss_pause_days: int = 10
    max_loss_fraction: float = 0.50


@dataclass(frozen=True)
class SingleAssetBotSnapshot:
    symbol: str
    timestamp: datetime | None
    status: BotStatus
    reason: str
    current_price: float
    trend_regime: TrendRegime
    macro_regime: MacroRiskRegime
    leverage: float
    working_capital: float
    savings_balance: float
    total_equity: float
    pause_until: datetime | None
    grid_lower: float | None
    grid_upper: float | None
    grid_count: int
    active_grid_levels: int
    grid_levels_crossed_in_step: int
    fills_in_step: int
    cumulative_grid_levels_crossed: int
    cumulative_fills: int
    gross_notional: float
    breakout_triggered: bool
    fake_breakout_triggered: bool
    cumulative_fake_breakouts: int
    active_breakout: GridBias
    inventory: float
    realized_pnl: float
    indicator_snapshot: IndicatorSnapshot
    macro_state: MacroRegimeState
    risk_plan: GridRiskPlan | None


class SingleAssetGridBot:
    def __init__(self, symbol: str, config: SingleAssetBotConfig) -> None:
        if config.allocated_capital <= 0.0:
            raise ValueError("allocated_capital must be positive")

        self.symbol = symbol
        self.config = config
        self.working_capital = config.allocated_capital
        self.savings_balance = 0.0
        self.execution_bot = GridExecutionBot(symbol)
        self.current_plan: GridRiskPlan | None = None
        self.active_macro_regime: MacroRiskRegime | None = None
        self.active_breakout = GridBias.NEUTRAL
        self.fake_breakout_count = 0
        self.fake_breakout_recorded = False
        self.pause_until: datetime | None = None
        self.last_settlement_date = None
        self.daily_realized_profit = 0.0
        self.previous_realized_pnl = 0.0

    def step(self, market_input: SingleAssetInput) -> SingleAssetBotSnapshot:
        if not market_input.daily_bars or not market_input.intraday_bars:
            raise ValueError("daily and intraday bars are required")

        timestamp = market_input.intraday_bars[-1].timestamp
        current_price = market_input.intraday_bars[-1].close
        current_date = timestamp.date() if timestamp is not None else None
        if self.last_settlement_date is not None and current_date is not None and current_date != self.last_settlement_date:
            self._settle_daily_profit()
        if current_date is not None:
            self.last_settlement_date = current_date

        indicator_snapshot = build_indicator_snapshot(market_input.daily_bars, market_input.intraday_bars)
        macro_state = assess_macro_regime(
            market_input.dxy_values,
            market_input.spread_10y2y_values,
            market_input.spread_2y3m_values,
            market_input.vix_values,
            market_input.fear_greed_values,
        )
        breakout_triggered, fake_breakout_triggered = self._update_breakout_state(indicator_snapshot, current_price)
        effective_bias = self.active_breakout if self.active_breakout != GridBias.NEUTRAL else _grid_bias_from_trend(indicator_snapshot.trend.regime)

        if self.pause_until is not None and timestamp is not None and timestamp < self.pause_until:
            return self._build_snapshot(
                timestamp=timestamp,
                status=BotStatus.PAUSED,
                reason="pause_active",
                current_price=current_price,
                indicator_snapshot=indicator_snapshot,
                macro_state=macro_state,
                execution_snapshot=None,
                breakout_triggered=breakout_triggered,
                fake_breakout_triggered=fake_breakout_triggered,
            )

        if self.active_macro_regime is not None and macro_state.regime != self.active_macro_regime:
            self.execution_bot.close_all(current_price)
            self._capture_realized_delta()
            self.current_plan = None
            self.pause_until = timestamp + timedelta(days=self.config.macro_pause_days) if timestamp is not None else None
            self.active_macro_regime = macro_state.regime
            return self._build_snapshot(
                timestamp=timestamp,
                status=BotStatus.PAUSED,
                reason="macro_change",
                current_price=current_price,
                indicator_snapshot=indicator_snapshot,
                macro_state=macro_state,
                execution_snapshot=None,
                breakout_triggered=breakout_triggered,
                fake_breakout_triggered=fake_breakout_triggered,
            )

        self.active_macro_regime = macro_state.regime

        needs_new_plan = self.current_plan is None
        if self.current_plan is not None:
            needs_new_plan = current_price < self.current_plan.lower_range or current_price > self.current_plan.upper_range
        if needs_new_plan:
            self.current_plan = build_grid_risk_plan(
                indicator_snapshot,
                market_input.intraday_bars,
                macro_state,
                allocated_capital=self.working_capital,
            )
            if abs(self.execution_bot.inventory) < 1e-12:
                direction = effective_bias
                if direction != GridBias.NEUTRAL:
                    self.execution_bot.seed_position(
                        direction=direction,
                        notional=self.current_plan.initial_entry_notional,
                        price=current_price,
                    )

        execution_snapshot = self.execution_bot.step(
            timestamp,
            price=current_price,
            spacing_pct=self.current_plan.level_spacing / max(current_price, 1e-9),
            regime=effective_bias,
            order_notional=self.current_plan.order_notional,
            inventory_limit_notional=self.current_plan.total_grid_notional,
        )
        self._capture_realized_delta()

        if execution_snapshot.equity <= -(self.working_capital * self.config.max_loss_fraction):
            self.execution_bot.close_all(current_price)
            self._capture_realized_delta()
            self.current_plan = None
            self.pause_until = timestamp + timedelta(days=self.config.loss_pause_days) if timestamp is not None else None
            return self._build_snapshot(
                timestamp=timestamp,
                status=BotStatus.PAUSED,
                reason="loss_pause",
                current_price=current_price,
                indicator_snapshot=indicator_snapshot,
                macro_state=macro_state,
                execution_snapshot=None,
                breakout_triggered=breakout_triggered,
                fake_breakout_triggered=fake_breakout_triggered,
            )

        return self._build_snapshot(
            timestamp=timestamp,
            status=BotStatus.ACTIVE,
            reason="active",
            current_price=current_price,
            indicator_snapshot=indicator_snapshot,
            macro_state=macro_state,
            execution_snapshot=execution_snapshot,
            breakout_triggered=breakout_triggered,
            fake_breakout_triggered=fake_breakout_triggered,
        )

    def _update_breakout_state(self, indicator_snapshot: IndicatorSnapshot, current_price: float) -> tuple[bool, bool]:
        breakout_triggered = False
        fake_breakout_triggered = False
        aligned_breakout = _aligned_breakout(indicator_snapshot)
        if aligned_breakout != GridBias.NEUTRAL and aligned_breakout != self.active_breakout:
            self.active_breakout = aligned_breakout
            self.fake_breakout_recorded = False
            breakout_triggered = True

        if self.active_breakout == GridBias.LONG and current_price <= indicator_snapshot.slow_donchian.upper and not self.fake_breakout_recorded:
            self.fake_breakout_count += 1
            self.fake_breakout_recorded = True
            fake_breakout_triggered = True
        elif self.active_breakout == GridBias.SHORT and current_price >= indicator_snapshot.slow_donchian.lower and not self.fake_breakout_recorded:
            self.fake_breakout_count += 1
            self.fake_breakout_recorded = True
            fake_breakout_triggered = True

        return breakout_triggered, fake_breakout_triggered

    def _capture_realized_delta(self) -> None:
        realized_delta = self.execution_bot.realized_pnl - self.previous_realized_pnl
        if realized_delta > 0.0:
            self.daily_realized_profit += realized_delta
        self.previous_realized_pnl = self.execution_bot.realized_pnl

    def _settle_daily_profit(self) -> None:
        if self.daily_realized_profit <= 0.0:
            self.daily_realized_profit = 0.0
            return
        self.savings_balance += self.daily_realized_profit * self.config.savings_rate
        self.working_capital += self.daily_realized_profit * self.config.compounding_rate
        self.daily_realized_profit = 0.0

    def _build_snapshot(
        self,
        *,
        timestamp: datetime | None,
        status: BotStatus,
        reason: str,
        current_price: float,
        indicator_snapshot: IndicatorSnapshot,
        macro_state: MacroRegimeState,
        execution_snapshot: GridExecutionSnapshot | None,
        breakout_triggered: bool,
        fake_breakout_triggered: bool,
    ) -> SingleAssetBotSnapshot:
        gross_notional = abs(self.execution_bot.inventory) * current_price
        active_grid_levels = len(self.current_plan.buy_levels) + len(self.current_plan.sell_levels) if self.current_plan is not None else 0
        return SingleAssetBotSnapshot(
            symbol=self.symbol,
            timestamp=timestamp,
            status=status,
            reason=reason,
            current_price=current_price,
            trend_regime=indicator_snapshot.trend.regime,
            macro_regime=macro_state.regime,
            leverage=self.current_plan.leverage if self.current_plan is not None else 0.0,
            working_capital=self.working_capital,
            savings_balance=self.savings_balance,
            total_equity=self.working_capital + self.savings_balance + (self.execution_bot.cash + self.execution_bot.inventory * current_price),
            pause_until=self.pause_until,
            grid_lower=self.current_plan.lower_range if self.current_plan is not None else None,
            grid_upper=self.current_plan.upper_range if self.current_plan is not None else None,
            grid_count=self.current_plan.grid_count if self.current_plan is not None else 0,
            active_grid_levels=active_grid_levels,
            grid_levels_crossed_in_step=0 if execution_snapshot is None else execution_snapshot.grid_levels_crossed_in_step,
            fills_in_step=0 if execution_snapshot is None else execution_snapshot.fills_in_step,
            cumulative_grid_levels_crossed=self.execution_bot.cumulative_grid_levels_crossed,
            cumulative_fills=self.execution_bot.cumulative_fills,
            gross_notional=gross_notional,
            breakout_triggered=breakout_triggered,
            fake_breakout_triggered=fake_breakout_triggered,
            cumulative_fake_breakouts=self.fake_breakout_count,
            active_breakout=self.active_breakout,
            inventory=self.execution_bot.inventory,
            realized_pnl=self.execution_bot.realized_pnl,
            indicator_snapshot=indicator_snapshot,
            macro_state=macro_state,
            risk_plan=self.current_plan,
        )


def _grid_bias_from_trend(regime: TrendRegime) -> GridBias:
    if regime == TrendRegime.BULL:
        return GridBias.LONG
    if regime == TrendRegime.BEAR:
        return GridBias.SHORT
    return GridBias.NEUTRAL


def _aligned_breakout(indicator_snapshot: IndicatorSnapshot) -> GridBias:
    if indicator_snapshot.breakout.value == "long" and indicator_snapshot.trend.regime == TrendRegime.BULL:
        return GridBias.LONG
    if indicator_snapshot.breakout.value == "short" and indicator_snapshot.trend.regime == TrendRegime.BEAR:
        return GridBias.SHORT
    return GridBias.NEUTRAL