from __future__ import annotations

import argparse
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

    def as_dict(self) -> dict[str, Path]:
        artifacts: dict[str, Path] = {}
        if self.market_overview is not None:
            artifacts["market_overview"] = self.market_overview
        if self.walkforward_dashboard is not None:
            artifacts["walkforward_dashboard"] = self.walkforward_dashboard
        if self.returns_summary is not None:
            artifacts["returns_summary"] = self.returns_summary
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
        market_overview = save_market_overview(simulation, output_root / "generated_market_overview.png")
        walkforward_dashboard = save_walkforward_dashboard(snapshots, output_root / "generated_walkforward_dashboard.png")
        returns_summary = output_root / "generated_returns_summary.txt"
        returns_summary.write_text(_format_returns_summary(analytics), encoding="utf-8")
        artifacts = GeneratedBacktestArtifacts(
            market_overview=market_overview,
            walkforward_dashboard=walkforward_dashboard,
            returns_summary=returns_summary,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full reinforced walk-forward setup on generated market data.")
    parser.add_argument("--years", type=int, default=3, help="Number of synthetic daily years to generate.")
    parser.add_argument("--seed", type=int, default=21, help="Seed for the daily synthetic market path.")
    parser.add_argument("--intraday-seed", type=int, default=121, help="Seed for the intraday path expansion.")
    parser.add_argument("--intraday-bars-per-day", type=int, default=24, help="Compressed intraday bars per synthetic day.")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Directory where generated reports and plots will be written.")
    args = parser.parse_args()

    result = run_generated_backtest(
        years=args.years,
        seed=args.seed,
        intraday_seed=args.intraday_seed,
        intraday_bars_per_day=args.intraday_bars_per_day,
        output_dir=args.output_dir,
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