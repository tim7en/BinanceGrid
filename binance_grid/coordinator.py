from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence

from .allocation import AllocationConfig, MarketAllocation, allocate_market_capital
from .indicators import AtrMetrics, VolumeSignal, annualized_realized_volatility, average_true_range, volume_confirmation
from .reinforcement import ReinforcementConfig, ReinforcementState, compute_reinforcement
from .signals import CrossoverSignal, TrendBias, detect_moving_average_crossover, determine_daily_bias
from .strategy import BotSnapshot, GridBias, GridTradingBot


@dataclass(frozen=True)
class PriceBar:
    timestamp: datetime | None
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MarketFrame:
    daily_bars: tuple[PriceBar, ...]
    five_minute_bars: tuple[PriceBar, ...]

    @property
    def last_timestamp(self) -> datetime | None:
        return self.five_minute_bars[-1].timestamp

    @property
    def last_price(self) -> float:
        return float(self.five_minute_bars[-1].close)


@dataclass(frozen=True)
class CoordinatorConfig:
    allocation: AllocationConfig = field(default_factory=AllocationConfig)
    reinforcement: ReinforcementConfig = field(default_factory=ReinforcementConfig)
    daily_fast_window: int = 50
    daily_slow_window: int = 200
    donchian_window: int = 20
    intraday_fast_window: int = 50
    intraday_slow_window: int = 100
    atr_window: int = 20
    volume_fast_window: int = 20
    volume_slow_window: int = 50
    volume_confirmation_threshold: float = 1.2
    intraday_periods_per_year: int = 365 * 24 * 12


@dataclass(frozen=True)
class AssetDecision:
    symbol: str
    bias: TrendBias
    crossover: CrossoverSignal
    volume: VolumeSignal
    reinforcement: ReinforcementState
    atr: AtrMetrics
    allocation: MarketAllocation
    regime: GridBias
    active_breakout: GridBias
    fake_breakout_triggered: bool
    cumulative_fake_breakouts: int
    grid_spacing_pct: float
    bot_snapshot: BotSnapshot


@dataclass(frozen=True)
class CoordinatorSnapshot:
    timestamp: datetime | None
    portfolio_equity: float
    gross_exposure: float
    decisions: dict[str, AssetDecision]


class RuleBasedGridCoordinator:
    def __init__(
        self,
        bots: Mapping[str, GridTradingBot],
        config: CoordinatorConfig | None = None,
    ) -> None:
        if not bots:
            raise ValueError("coordinator requires at least one bot")

        self.bots = dict(bots)
        self.config = config or CoordinatorConfig()
        self.active_regimes = {symbol: GridBias.NEUTRAL for symbol in self.bots}
        self.active_breakouts = {symbol: GridBias.NEUTRAL for symbol in self.bots}
        self.fake_breakout_counts = {symbol: 0 for symbol in self.bots}
        self.fake_breakout_recorded = {symbol: False for symbol in self.bots}
        self.portfolio_equity = self.config.allocation.starting_balance

    def step(self, frames: Mapping[str, MarketFrame]) -> CoordinatorSnapshot:
        missing_symbols = set(self.bots).difference(frames)
        if missing_symbols:
            missing_display = ", ".join(sorted(missing_symbols))
            raise KeyError(f"missing frames for: {missing_display}")

        decisions: dict[str, AssetDecision] = {}
        for symbol, bot in self.bots.items():
            frame = frames[symbol]
            daily_closes = [bar.close for bar in frame.daily_bars]
            daily_highs = [bar.high for bar in frame.daily_bars]
            daily_lows = [bar.low for bar in frame.daily_bars]
            intraday_closes = [bar.close for bar in frame.five_minute_bars]
            intraday_highs = [bar.high for bar in frame.five_minute_bars]
            intraday_lows = [bar.low for bar in frame.five_minute_bars]
            intraday_volumes = [bar.volume for bar in frame.five_minute_bars]

            bias = determine_daily_bias(
                daily_closes,
                daily_highs,
                daily_lows,
                fast_window=self.config.daily_fast_window,
                slow_window=self.config.daily_slow_window,
                donchian_window=self.config.donchian_window,
                previous_breakout=self.active_breakouts[symbol],
            )
            if bias.breakout_triggered:
                self.active_breakouts[symbol] = bias.breakout_regime
                self.fake_breakout_recorded[symbol] = False
            elif bias.breakout_persisted:
                self.active_breakouts[symbol] = bias.breakout_regime

            fake_breakout_triggered = False
            if bias.fake_breakout and not self.fake_breakout_recorded[symbol]:
                self.fake_breakout_counts[symbol] += 1
                self.fake_breakout_recorded[symbol] = True
                fake_breakout_triggered = True

            crossover = detect_moving_average_crossover(
                intraday_closes,
                fast_window=self.config.intraday_fast_window,
                slow_window=self.config.intraday_slow_window,
            )
            volume = volume_confirmation(
                intraday_volumes,
                fast_window=self.config.volume_fast_window,
                slow_window=self.config.volume_slow_window,
                leverage_cap=self.config.allocation.max_leverage,
                confirmation_threshold=self.config.volume_confirmation_threshold,
            )
            reinforcement = compute_reinforcement(
                bias,
                crossover,
                volume,
                previous_regime=self.active_regimes[symbol],
                active_breakout=self.active_breakouts[symbol],
                config=self.config.reinforcement,
            )
            atr = average_true_range(
                intraday_highs,
                intraday_lows,
                intraday_closes,
                window=self.config.atr_window,
            )
            allocation = allocate_market_capital(
                self.config.allocation,
                leverage_multiplier=reinforcement.applied_leverage,
                grid_levels_per_side=bot.config.levels_per_side,
                account_balance=self.portfolio_equity,
            )
            regime = reinforcement.regime
            self.active_regimes[symbol] = regime
            annualized_vol = max(
                annualized_realized_volatility(
                    intraday_closes,
                    periods_per_year=self.config.intraday_periods_per_year,
                ),
                atr.atr_pct * (self.config.intraday_periods_per_year ** 0.5),
                0.05,
            )
            grid_spacing_pct = atr.atr_pct / bot.config.levels_per_side
            bot_snapshot = bot.step(
                frame.last_timestamp,
                frame.last_price,
                annualized_vol=annualized_vol,
                regime=regime,
                spacing_pct_override=grid_spacing_pct,
                order_notional=allocation.order_notional,
                inventory_limit_notional=allocation.target_notional_limit,
            )
            decisions[symbol] = AssetDecision(
                symbol=symbol,
                bias=bias,
                crossover=crossover,
                volume=volume,
                reinforcement=reinforcement,
                atr=atr,
                allocation=allocation,
                regime=regime,
                active_breakout=self.active_breakouts[symbol],
                fake_breakout_triggered=fake_breakout_triggered,
                cumulative_fake_breakouts=self.fake_breakout_counts[symbol],
                grid_spacing_pct=bot_snapshot.spacing_pct,
                bot_snapshot=bot_snapshot,
            )

        strategy_equity = sum(decision.bot_snapshot.equity for decision in decisions.values())
        self.portfolio_equity = self.config.allocation.starting_balance + strategy_equity
        gross_exposure = sum(decision.bot_snapshot.gross_notional for decision in decisions.values()) / max(self.portfolio_equity, 1e-9)
        latest_timestamp = max(
            (decision.bot_snapshot.timestamp for decision in decisions.values()),
            key=lambda value: value or datetime.min,
        )
        return CoordinatorSnapshot(
            timestamp=latest_timestamp,
            portfolio_equity=self.portfolio_equity,
            gross_exposure=gross_exposure,
            decisions=decisions,
        )

    def run_backtest(self, frames: Sequence[Mapping[str, MarketFrame]]) -> list[CoordinatorSnapshot]:
        return [self.step(frame_batch) for frame_batch in frames]