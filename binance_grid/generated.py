from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from pathlib import Path

import numpy as np

from .modules.common import MarketBar
from .modules.portfolio import (
    AssetHistory,
    MacroHistory,
    PortfolioManagerConfig,
    PortfolioManagerSnapshot,
    PortfolioRiskController,
    WalkForwardAnalytics,
    run_walk_forward_backtest,
    summarize_walkforward_snapshots,
)
from .plotting import save_market_overview, save_walkforward_dashboard
from .simulation import MacroRegime, SimulationResult, simulate_price_paths


REGIME_VOLUME_MULTIPLIER: dict[MacroRegime, float] = {
    MacroRegime.EXPANSION: 0.95,
    MacroRegime.RANGE: 0.80,
    MacroRegime.STRESS: 1.45,
    MacroRegime.MANIA: 1.25,
}

REGIME_INTRADAY_NOISE: dict[MacroRegime, float] = {
    MacroRegime.EXPANSION: 0.0018,
    MacroRegime.RANGE: 0.0012,
    MacroRegime.STRESS: 0.0034,
    MacroRegime.MANIA: 0.0028,
}

BASE_DAILY_VOLUME: dict[str, float] = {
    "BTC": 6_500.0,
    "SP500": 8_000.0,
    "SOL": 9_500.0,
    "GOLD": 4_250.0,
}


@dataclass(frozen=True)
class GeneratedBacktestArtifacts:
    market_overview: Path | None = None
    walkforward_dashboard: Path | None = None
    returns_summary: Path | None = None
    step_trace_csv: Path | None = None
    day_by_day_example_csv: Path | None = None

    def as_dict(self) -> dict[str, Path]:
        artifacts: dict[str, Path] = {}
        if self.market_overview is not None:
            artifacts["market_overview"] = self.market_overview
        if self.walkforward_dashboard is not None:
            artifacts["walkforward_dashboard"] = self.walkforward_dashboard
        if self.returns_summary is not None:
            artifacts["returns_summary"] = self.returns_summary
        if self.step_trace_csv is not None:
            artifacts["step_trace_csv"] = self.step_trace_csv
        if self.day_by_day_example_csv is not None:
            artifacts["day_by_day_example_csv"] = self.day_by_day_example_csv
        return artifacts


@dataclass(frozen=True)
class GeneratedBacktestResult:
    simulation: SimulationResult
    histories: dict[str, AssetHistory]
    macro_history: MacroHistory
    snapshots: list[PortfolioManagerSnapshot]
    analytics: WalkForwardAnalytics
    artifacts: GeneratedBacktestArtifacts | None = None


def build_generated_histories(
    simulation: SimulationResult,
    *,
    intraday_bars_per_day: int = 24,
    seed: int | None = 101,
) -> dict[str, AssetHistory]:
    if intraday_bars_per_day < 2:
        raise ValueError("intraday_bars_per_day must be at least 2")
    if simulation.steps_per_year != 365:
        raise ValueError("generated history adapter expects 365 simulation steps per year")

    rng = np.random.default_rng(seed)
    histories: dict[str, AssetHistory] = {}
    interval = timedelta(seconds=86_400 / (intraday_bars_per_day + 1))

    for asset_index, symbol in enumerate(simulation.asset_symbols):
        daily_bars: list[MarketBar] = []
        intraday_bars: list[MarketBar] = []
        for step_index, regime in enumerate(simulation.regimes):
            day_open = float(simulation.prices[step_index, asset_index])
            day_close = float(simulation.prices[step_index + 1, asset_index])
            day_timestamp = simulation.timestamps[step_index + 1]
            day_log_return = math.log(day_close / max(day_open, 1e-9))
            regime_volume = REGIME_VOLUME_MULTIPLIER[regime]
            wick_scale = max(abs(day_log_return), 0.0025) * regime_volume
            up_wick = abs(rng.normal(wick_scale, wick_scale * 0.25))
            down_wick = abs(rng.normal(wick_scale, wick_scale * 0.25))
            high = max(day_open, day_close) * math.exp(up_wick)
            low = min(day_open, day_close) / math.exp(down_wick)
            base_volume = BASE_DAILY_VOLUME.get(symbol, 5_000.0)
            day_volume = base_volume * regime_volume * (1.0 + min(abs(day_log_return) * 30.0, 3.0))
            daily_bars.append(
                MarketBar(
                    timestamp=day_timestamp,
                    open=day_open,
                    high=high,
                    low=low,
                    close=day_close,
                    volume=day_volume,
                )
            )
            intraday_bars.extend(
                _build_intraday_bars(
                    day_open,
                    day_close,
                    day_timestamp,
                    regime=regime,
                    intraday_bars_per_day=intraday_bars_per_day,
                    day_volume=day_volume,
                    interval=interval,
                    rng=rng,
                )
            )
        histories[symbol] = AssetHistory(
            daily_bars=tuple(daily_bars),
            intraday_bars=tuple(intraday_bars),
        )
    return histories


def build_generated_macro_history(
    simulation: SimulationResult,
    *,
    seed: int | None = 211,
) -> MacroHistory:
    rng = np.random.default_rng(seed)
    dxy_values: list[float] = []
    spread_10y2y_values: list[float] = []
    spread_2y3m_values: list[float] = []
    vix_values: list[float] = []
    fear_greed_values: list[float] = []

    profiles = {
        MacroRegime.EXPANSION: (101.5, 0.85, 0.35, 16.0, 66.0),
        MacroRegime.RANGE: (103.0, 0.25, 0.10, 21.0, 50.0),
        MacroRegime.STRESS: (106.0, -0.35, -0.22, 33.0, 24.0),
        MacroRegime.MANIA: (100.5, 0.45, 0.15, 18.0, 80.0),
    }
    previous = profiles[simulation.regimes[0]]
    for regime in simulation.regimes:
        target = profiles[regime]
        smoothed = tuple((0.65 * previous[index]) + (0.35 * target[index]) for index in range(len(target)))
        previous = smoothed
        dxy_values.append(float(smoothed[0] + rng.normal(0.0, 0.25)))
        spread_10y2y_values.append(float(smoothed[1] + rng.normal(0.0, 0.03)))
        spread_2y3m_values.append(float(smoothed[2] + rng.normal(0.0, 0.03)))
        vix_values.append(float(max(smoothed[3] + rng.normal(0.0, 0.8), 10.0)))
        fear_greed_values.append(float(np.clip(smoothed[4] + rng.normal(0.0, 3.0), 0.0, 100.0)))

    return MacroHistory(
        dxy_values=tuple(dxy_values),
        spread_10y2y_values=tuple(spread_10y2y_values),
        spread_2y3m_values=tuple(spread_2y3m_values),
        vix_values=tuple(vix_values),
        fear_greed_values=tuple(fear_greed_values),
    )


def run_generated_backtest(
    *,
    years: int = 3,
    seed: int = 21,
    intraday_seed: int = 121,
    intraday_bars_per_day: int = 24,
    output_dir: str | Path | None = None,
    portfolio_config: PortfolioManagerConfig | None = None,
    example_symbol: str | None = None,
) -> GeneratedBacktestResult:
    simulation = simulate_price_paths(years=years, steps_per_year=365, seed=seed)
    histories = build_generated_histories(
        simulation,
        intraday_bars_per_day=intraday_bars_per_day,
        seed=intraday_seed,
    )
    macro_history = build_generated_macro_history(
        simulation,
        seed=intraday_seed + 17,
    )
    controller = PortfolioRiskController(
        simulation.asset_symbols,
        portfolio_config or PortfolioManagerConfig(total_capital=100_000.0),
    )
    snapshots = run_walk_forward_backtest(controller, histories, macro_history)
    analytics = summarize_walkforward_snapshots(snapshots)

    artifacts: GeneratedBacktestArtifacts | None = None
    if output_dir is not None:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        selected_symbol = example_symbol or simulation.asset_symbols[0]
        if selected_symbol not in histories:
            raise KeyError(f"example symbol not found: {selected_symbol}")
        market_overview = save_market_overview(simulation, output_root / "generated_market_overview.png")
        walkforward_dashboard = save_walkforward_dashboard(snapshots, output_root / "generated_walkforward_dashboard.png")
        returns_summary = output_root / "generated_returns_summary.txt"
        returns_summary.write_text(_format_returns_summary(analytics), encoding="utf-8")
        step_trace_csv = output_root / "generated_step_trace.csv"
        day_by_day_example_csv = output_root / f"generated_{selected_symbol.lower()}_day_by_day.csv"
        _write_step_trace_csv(
            simulation=simulation,
            histories=histories,
            macro_history=macro_history,
            snapshots=snapshots,
            analytics=analytics,
            output_path=step_trace_csv,
        )
        _write_day_by_day_example_csv(
            simulation=simulation,
            histories=histories,
            macro_history=macro_history,
            snapshots=snapshots,
            analytics=analytics,
            symbol=selected_symbol,
            output_path=day_by_day_example_csv,
        )
        artifacts = GeneratedBacktestArtifacts(
            market_overview=market_overview,
            walkforward_dashboard=walkforward_dashboard,
            returns_summary=returns_summary,
            step_trace_csv=step_trace_csv,
            day_by_day_example_csv=day_by_day_example_csv,
        )

    return GeneratedBacktestResult(
        simulation=simulation,
        histories=histories,
        macro_history=macro_history,
        snapshots=snapshots,
        analytics=analytics,
        artifacts=artifacts,
    )


def _build_intraday_bars(
    day_open: float,
    day_close: float,
    day_timestamp: datetime,
    *,
    regime: MacroRegime,
    intraday_bars_per_day: int,
    day_volume: float,
    interval: timedelta,
    rng: np.random.Generator,
) -> list[MarketBar]:
    target_log_return = math.log(day_close / max(day_open, 1e-9))
    noise_scale = REGIME_INTRADAY_NOISE[regime] + (abs(target_log_return) / max(intraday_bars_per_day, 1)) * 2.5
    raw_increments = rng.normal(0.0, noise_scale, size=intraday_bars_per_day)
    increments = raw_increments - raw_increments.mean() + (target_log_return / intraday_bars_per_day)
    log_prices = math.log(max(day_open, 1e-9)) + np.cumsum(increments)
    closes = np.exp(log_prices)
    session_start = day_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

    bars: list[MarketBar] = []
    previous_close = day_open
    for index, close in enumerate(closes):
        wiggle = max(abs(float(increments[index])) * 0.85, 0.0004)
        high = max(previous_close, float(close)) * math.exp(wiggle)
        low = min(previous_close, float(close)) / math.exp(wiggle)
        progress = index / max(intraday_bars_per_day - 1, 1)
        time_weight = 1.05 + (0.55 * abs(progress - 0.5) * 2.0)
        move_weight = 1.0 + min(abs(float(increments[index])) * 120.0, 3.5)
        noisy_scale = max(0.35, 1.0 + (0.08 * rng.standard_normal()))
        volume = max(day_volume / intraday_bars_per_day * time_weight * move_weight * noisy_scale, 1.0)
        bars.append(
            MarketBar(
                timestamp=session_start + interval * (index + 1),
                open=previous_close,
                high=high,
                low=low,
                close=float(close),
                volume=volume,
            )
        )
        previous_close = float(close)
    return bars


def _format_returns_summary(analytics: WalkForwardAnalytics) -> str:
    return "\n".join(
        [
            f"Start equity: {analytics.equity_curve[0]:,.2f}",
            f"Final equity: {analytics.equity_curve[-1]:,.2f}",
            f"Total return: {analytics.total_return * 100.0:.2f}%",
            f"Annualized return: {analytics.annualized_return * 100.0:.2f}%",
            f"Max drawdown: {analytics.max_drawdown * 100.0:.2f}%",
            f"Total fills: {analytics.cumulative_fills[-1]:.0f}",
            f"Grid crosses: {analytics.cumulative_grid_crosses[-1]:.0f}",
            f"Fill rate: {analytics.cumulative_fill_rate[-1] * 100.0:.2f}%",
            f"Aligned breakouts: {analytics.cumulative_breakouts[-1]:.0f}",
            f"Fake breakouts: {analytics.cumulative_fake_breakouts[-1]:.0f}",
        ]
    )


TRACE_FIELDNAMES = [
    "snapshot_index",
    "timestamp",
    "session_date",
    "symbol",
    "session_regime",
    "completed_daily_timestamp",
    "completed_daily_open",
    "completed_daily_high",
    "completed_daily_low",
    "completed_daily_close",
    "completed_daily_volume",
    "intraday_open",
    "intraday_high",
    "intraday_low",
    "intraday_close",
    "intraday_volume",
    "vwap",
    "trend_fast_ma",
    "trend_slow_ma",
    "trend_regime",
    "trend_crossed_up",
    "trend_crossed_down",
    "fast_donchian_upper",
    "fast_donchian_middle",
    "fast_donchian_lower",
    "slow_donchian_upper",
    "slow_donchian_middle",
    "slow_donchian_lower",
    "breakout_direction",
    "volume_fast_average",
    "volume_slow_average",
    "volume_ratio",
    "volume_phase",
    "macro_observation_count",
    "macro_latest_dxy",
    "macro_latest_spread_10y2y",
    "macro_latest_spread_2y3m",
    "macro_latest_vix",
    "macro_latest_fear_greed",
    "macro_regime",
    "macro_score",
    "macro_dxy_score",
    "macro_curve_score",
    "macro_vix_score",
    "macro_sentiment_score",
    "macro_leverage_cap",
    "bot_status",
    "bot_reason",
    "current_price",
    "active_breakout",
    "breakout_triggered",
    "fake_breakout_triggered",
    "cumulative_fake_breakouts",
    "grid_lower",
    "grid_upper",
    "grid_count",
    "active_grid_levels",
    "level_spacing",
    "atr",
    "atr_pct",
    "realized_volatility_200",
    "leverage",
    "total_grid_notional",
    "initial_entry_notional",
    "reserve_notional",
    "order_notional",
    "buy_level_count",
    "sell_level_count",
    "nearest_buy_level",
    "nearest_sell_level",
    "inventory",
    "gross_notional",
    "realized_pnl",
    "total_equity",
    "working_capital",
    "savings_balance",
    "grid_levels_crossed_in_step",
    "fills_in_step",
    "cumulative_grid_levels_crossed",
    "cumulative_fills",
    "portfolio_total_equity",
    "portfolio_total_savings",
    "portfolio_gross_exposure",
    "portfolio_cumulative_return",
    "portfolio_drawdown",
]


def _write_step_trace_csv(
    *,
    simulation: SimulationResult,
    histories: dict[str, AssetHistory],
    macro_history: MacroHistory,
    snapshots: list[PortfolioManagerSnapshot],
    analytics: WalkForwardAnalytics,
    output_path: Path,
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDNAMES)
        writer.writeheader()
        for row in _iter_trace_rows(
            simulation=simulation,
            histories=histories,
            macro_history=macro_history,
            snapshots=snapshots,
            analytics=analytics,
        ):
            writer.writerow(row)


def _write_day_by_day_example_csv(
    *,
    simulation: SimulationResult,
    histories: dict[str, AssetHistory],
    macro_history: MacroHistory,
    snapshots: list[PortfolioManagerSnapshot],
    analytics: WalkForwardAnalytics,
    symbol: str,
    output_path: Path,
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDNAMES)
        writer.writeheader()
        current_session_date: str | None = None
        pending_row: dict[str, object] | None = None
        for row in _iter_trace_rows(
            simulation=simulation,
            histories=histories,
            macro_history=macro_history,
            snapshots=snapshots,
            analytics=analytics,
        ):
            if row["symbol"] != symbol:
                continue
            row_session_date = str(row["session_date"])
            if current_session_date is None or row_session_date == current_session_date:
                current_session_date = row_session_date
                pending_row = row
                continue
            if pending_row is not None:
                writer.writerow(pending_row)
            current_session_date = row_session_date
            pending_row = row

        if pending_row is not None:
            writer.writerow(pending_row)


def _iter_trace_rows(
    *,
    simulation: SimulationResult,
    histories: dict[str, AssetHistory],
    macro_history: MacroHistory,
    snapshots: list[PortfolioManagerSnapshot],
    analytics: WalkForwardAnalytics,
):
    regime_by_date = {
        timestamp.date(): regime.value
        for timestamp, regime in zip(simulation.timestamps[1:], simulation.regimes, strict=True)
    }
    intraday_lookup = {
        symbol: {bar.timestamp: bar for bar in history.intraday_bars}
        for symbol, history in histories.items()
    }
    daily_dates = {
        symbol: [bar.timestamp.date() for bar in history.daily_bars]
        for symbol, history in histories.items()
    }

    for snapshot_index, portfolio_snapshot in enumerate(snapshots):
        for symbol, asset_snapshot in portfolio_snapshot.asset_snapshots.items():
            session_timestamp = asset_snapshot.timestamp
            current_bar = intraday_lookup[symbol].get(session_timestamp)
            completed_count = _completed_daily_count(daily_dates[symbol], session_timestamp)
            completed_daily_bar = histories[symbol].daily_bars[completed_count - 1] if completed_count > 0 else None
            macro_index = completed_count - 1 if completed_count > 0 else None
            risk_plan = asset_snapshot.risk_plan
            indicator_snapshot = asset_snapshot.indicator_snapshot

            yield {
                "snapshot_index": snapshot_index,
                "timestamp": None if session_timestamp is None else session_timestamp.isoformat(),
                "session_date": None if session_timestamp is None else session_timestamp.date().isoformat(),
                "symbol": symbol,
                "session_regime": None if session_timestamp is None else regime_by_date.get(session_timestamp.date()),
                "completed_daily_timestamp": None if completed_daily_bar is None else completed_daily_bar.timestamp.isoformat(),
                "completed_daily_open": None if completed_daily_bar is None else completed_daily_bar.open,
                "completed_daily_high": None if completed_daily_bar is None else completed_daily_bar.high,
                "completed_daily_low": None if completed_daily_bar is None else completed_daily_bar.low,
                "completed_daily_close": None if completed_daily_bar is None else completed_daily_bar.close,
                "completed_daily_volume": None if completed_daily_bar is None else completed_daily_bar.volume,
                "intraday_open": None if current_bar is None else current_bar.open,
                "intraday_high": None if current_bar is None else current_bar.high,
                "intraday_low": None if current_bar is None else current_bar.low,
                "intraday_close": None if current_bar is None else current_bar.close,
                "intraday_volume": None if current_bar is None else current_bar.volume,
                "vwap": indicator_snapshot.vwap,
                "trend_fast_ma": indicator_snapshot.trend.fast_value,
                "trend_slow_ma": indicator_snapshot.trend.slow_value,
                "trend_regime": indicator_snapshot.trend.regime.value,
                "trend_crossed_up": indicator_snapshot.trend.crossed_up,
                "trend_crossed_down": indicator_snapshot.trend.crossed_down,
                "fast_donchian_upper": indicator_snapshot.fast_donchian.upper,
                "fast_donchian_middle": indicator_snapshot.fast_donchian.middle,
                "fast_donchian_lower": indicator_snapshot.fast_donchian.lower,
                "slow_donchian_upper": indicator_snapshot.slow_donchian.upper,
                "slow_donchian_middle": indicator_snapshot.slow_donchian.middle,
                "slow_donchian_lower": indicator_snapshot.slow_donchian.lower,
                "breakout_direction": indicator_snapshot.breakout.value,
                "volume_fast_average": indicator_snapshot.volume.fast_average,
                "volume_slow_average": indicator_snapshot.volume.slow_average,
                "volume_ratio": indicator_snapshot.volume.ratio,
                "volume_phase": indicator_snapshot.volume.phase.value,
                "macro_observation_count": completed_count,
                "macro_latest_dxy": _macro_value(macro_history.dxy_values, macro_index),
                "macro_latest_spread_10y2y": _macro_value(macro_history.spread_10y2y_values, macro_index),
                "macro_latest_spread_2y3m": _macro_value(macro_history.spread_2y3m_values, macro_index),
                "macro_latest_vix": _macro_value(macro_history.vix_values, macro_index),
                "macro_latest_fear_greed": _macro_value(macro_history.fear_greed_values, macro_index),
                "macro_regime": asset_snapshot.macro_state.regime.value,
                "macro_score": asset_snapshot.macro_state.score,
                "macro_dxy_score": asset_snapshot.macro_state.dxy_score,
                "macro_curve_score": asset_snapshot.macro_state.curve_score,
                "macro_vix_score": asset_snapshot.macro_state.vix_score,
                "macro_sentiment_score": asset_snapshot.macro_state.sentiment_score,
                "macro_leverage_cap": asset_snapshot.macro_state.leverage_cap,
                "bot_status": asset_snapshot.status.value,
                "bot_reason": asset_snapshot.reason,
                "current_price": asset_snapshot.current_price,
                "active_breakout": asset_snapshot.active_breakout.value,
                "breakout_triggered": asset_snapshot.breakout_triggered,
                "fake_breakout_triggered": asset_snapshot.fake_breakout_triggered,
                "cumulative_fake_breakouts": asset_snapshot.cumulative_fake_breakouts,
                "grid_lower": None if risk_plan is None else risk_plan.lower_range,
                "grid_upper": None if risk_plan is None else risk_plan.upper_range,
                "grid_count": asset_snapshot.grid_count,
                "active_grid_levels": asset_snapshot.active_grid_levels,
                "level_spacing": None if risk_plan is None else risk_plan.level_spacing,
                "atr": None if risk_plan is None else risk_plan.atr,
                "atr_pct": None if risk_plan is None else risk_plan.atr_pct,
                "realized_volatility_200": None if risk_plan is None else risk_plan.realized_volatility_200,
                "leverage": asset_snapshot.leverage,
                "total_grid_notional": None if risk_plan is None else risk_plan.total_grid_notional,
                "initial_entry_notional": None if risk_plan is None else risk_plan.initial_entry_notional,
                "reserve_notional": None if risk_plan is None else risk_plan.reserve_notional,
                "order_notional": None if risk_plan is None else risk_plan.order_notional,
                "buy_level_count": 0 if risk_plan is None else len(risk_plan.buy_levels),
                "sell_level_count": 0 if risk_plan is None else len(risk_plan.sell_levels),
                "nearest_buy_level": None if risk_plan is None or not risk_plan.buy_levels else risk_plan.buy_levels[0],
                "nearest_sell_level": None if risk_plan is None or not risk_plan.sell_levels else risk_plan.sell_levels[0],
                "inventory": asset_snapshot.inventory,
                "gross_notional": asset_snapshot.gross_notional,
                "realized_pnl": asset_snapshot.realized_pnl,
                "total_equity": asset_snapshot.total_equity,
                "working_capital": asset_snapshot.working_capital,
                "savings_balance": asset_snapshot.savings_balance,
                "grid_levels_crossed_in_step": asset_snapshot.grid_levels_crossed_in_step,
                "fills_in_step": asset_snapshot.fills_in_step,
                "cumulative_grid_levels_crossed": asset_snapshot.cumulative_grid_levels_crossed,
                "cumulative_fills": asset_snapshot.cumulative_fills,
                "portfolio_total_equity": portfolio_snapshot.total_equity,
                "portfolio_total_savings": portfolio_snapshot.total_savings,
                "portfolio_gross_exposure": portfolio_snapshot.gross_exposure,
                "portfolio_cumulative_return": float(analytics.cumulative_returns[snapshot_index]),
                "portfolio_drawdown": float(analytics.drawdown[snapshot_index]),
            }


def _completed_daily_count(daily_dates: list, session_timestamp: datetime | None) -> int:
    if session_timestamp is None:
        return 0
    return bisect_left(daily_dates, session_timestamp.date())


def _macro_value(values: tuple[float, ...], index: int | None) -> float | None:
    if index is None or index < 0 or index >= len(values):
        return None
    return values[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full reinforced walk-forward setup on generated market data.")
    parser.add_argument("--years", type=int, default=3, help="Number of synthetic daily years to generate.")
    parser.add_argument("--seed", type=int, default=21, help="Seed for the daily synthetic market path.")
    parser.add_argument("--intraday-seed", type=int, default=121, help="Seed for the intraday path expansion.")
    parser.add_argument("--intraday-bars-per-day", type=int, default=24, help="Compressed intraday bars per synthetic day.")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Directory where generated reports and plots will be written.")
    parser.add_argument("--example-symbol", default=None, help="Symbol used for the day-by-day example CSV. Defaults to the first configured asset.")
    args = parser.parse_args()

    result = run_generated_backtest(
        years=args.years,
        seed=args.seed,
        intraday_seed=args.intraday_seed,
        intraday_bars_per_day=args.intraday_bars_per_day,
        output_dir=args.output_dir,
        example_symbol=args.example_symbol,
    )
    print(f"snapshots={len(result.snapshots)}")
    print(f"final_equity={result.analytics.equity_curve[-1]:.2f}")
    print(f"total_return={result.analytics.total_return * 100.0:.2f}%")
    print(f"annualized_return={result.analytics.annualized_return * 100.0:.2f}%")
    print(f"max_drawdown={result.analytics.max_drawdown * 100.0:.2f}%")
    print(f"fill_rate={result.analytics.cumulative_fill_rate[-1] * 100.0:.2f}%")
    if result.artifacts is not None:
        for name, path in result.artifacts.as_dict().items():
            print(f"{name}: {path.resolve()}")


if __name__ == "__main__":
    main()