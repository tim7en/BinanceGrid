from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from .analytics import summarize_walkforward_snapshots
from .coordinator import CoordinatorConfig, MarketFrame, PriceBar, RuleBasedGridCoordinator
from .manager import AssetGridManager, PortfolioSnapshot
from .simulation import MacroRegime, SimulationResult, simulate_price_paths
from .strategy import GridBias, GridTradingBot
from .walkforward import run_walk_forward_backtest


REGIME_COLORS: dict[MacroRegime, str] = {
    MacroRegime.EXPANSION: "#dff3e4",
    MacroRegime.RANGE: "#f8f4d8",
    MacroRegime.STRESS: "#f8d7da",
    MacroRegime.MANIA: "#d6e9ff",
}

BIAS_COLORS: dict[GridBias, str] = {
    GridBias.LONG: "#1f77b4",
    GridBias.NEUTRAL: "#7f7f7f",
    GridBias.SHORT: "#d62728",
}


@dataclass(frozen=True)
class PlotArtifacts:
    market_overview: Path | None = None
    portfolio_overview: Path | None = None
    walkforward_dashboard: Path | None = None

    def as_dict(self) -> dict[str, Path]:
        artifacts: dict[str, Path] = {}
        if self.market_overview is not None:
            artifacts["market_overview"] = self.market_overview
        if self.portfolio_overview is not None:
            artifacts["portfolio_overview"] = self.portfolio_overview
        if self.walkforward_dashboard is not None:
            artifacts["walkforward_dashboard"] = self.walkforward_dashboard
        return artifacts


def save_market_overview(
    simulation: SimulationResult,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    normalized_prices = simulation.prices / simulation.prices[0]
    figure, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True)

    for axis, symbol, values in zip(axes.flat, simulation.asset_symbols, normalized_prices.T, strict=True):
        _shade_regimes(axis, simulation.timestamps, simulation.regimes)
        axis.plot(simulation.timestamps, values, color="#111827", linewidth=1.4)
        axis.set_title(symbol)
        axis.set_ylabel("Normalized Price")
        axis.grid(alpha=0.25, linewidth=0.6)

    legend_handles = [
        Patch(facecolor=color, edgecolor="none", alpha=0.35, label=regime.value)
        for regime, color in REGIME_COLORS.items()
    ]
    axes[0, 0].legend(handles=legend_handles, loc="upper left", frameon=False, ncol=2)
    for axis in axes[-1]:
        axis.set_xlabel("Time")
        axis.xaxis.set_major_locator(mdates.YearLocator(base=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    figure.suptitle("Synthetic Multi-Asset Market Paths")
    figure.tight_layout()
    figure.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return output


def save_portfolio_overview(
    snapshots: Sequence[PortfolioSnapshot],
    output_path: str | Path,
) -> Path:
    if not snapshots:
        raise ValueError("portfolio plotting requires at least one snapshot")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    timestamps = [snapshot.timestamp for snapshot in snapshots]
    equity = np.array([snapshot.portfolio_equity for snapshot in snapshots], dtype=float)
    gross_exposure = np.array([snapshot.gross_exposure for snapshot in snapshots], dtype=float)
    average_spacing = np.array(
        [np.mean([control.spacing_scale for control in snapshot.controls.values()]) for snapshot in snapshots],
        dtype=float,
    )
    bias_counts = {
        bias: np.array(
            [sum(1 for control in snapshot.controls.values() if control.regime == bias) for snapshot in snapshots],
            dtype=float,
        )
        for bias in GridBias
    }

    figure, axes = plt.subplots(3, 1, figsize=(16, 11), sharex=True)
    axes[0].plot(timestamps, equity, color="#0f172a", linewidth=1.5)
    axes[0].set_ylabel("Portfolio Equity")
    axes[0].grid(alpha=0.25, linewidth=0.6)

    axes[1].plot(timestamps, gross_exposure, color="#1d4ed8", linewidth=1.4, label="Gross Exposure")
    axes[1].plot(timestamps, average_spacing, color="#b45309", linewidth=1.2, label="Avg Spacing Scale")
    axes[1].set_ylabel("Risk Controls")
    axes[1].grid(alpha=0.25, linewidth=0.6)
    axes[1].legend(frameon=False, loc="upper left")

    cumulative = np.zeros(len(snapshots), dtype=float)
    for bias in (GridBias.LONG, GridBias.NEUTRAL, GridBias.SHORT):
        values = bias_counts[bias]
        axes[2].fill_between(
            timestamps,
            cumulative,
            cumulative + values,
            color=BIAS_COLORS[bias],
            alpha=0.75,
            label=bias.value,
        )
        cumulative += values
    axes[2].set_ylabel("Bot Count")
    axes[2].set_xlabel("Time")
    axes[2].grid(alpha=0.25, linewidth=0.6)
    axes[2].legend(frameon=False, loc="upper left", ncol=3)
    axes[2].xaxis.set_major_locator(mdates.YearLocator(base=2))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    figure.suptitle("Grid Manager Portfolio Overview")
    figure.tight_layout()
    figure.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return output


def save_walkforward_dashboard(
    snapshots,
    output_path: str | Path,
) -> Path:
    if not snapshots:
        raise ValueError("walk-forward plotting requires at least one snapshot")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    analytics = summarize_walkforward_snapshots(snapshots)
    timestamps = _plot_x_values(analytics.timestamps)

    figure, axes = plt.subplots(3, 2, figsize=(18, 12))
    axes = axes.reshape(3, 2)

    axes[0, 0].plot(timestamps, analytics.equity_curve, color="#0f172a", linewidth=1.6)
    axes[0, 0].set_title("Equity Curve")
    axes[0, 0].set_ylabel("Equity")
    axes[0, 0].grid(alpha=0.25, linewidth=0.6)

    axes[0, 1].fill_between(timestamps, analytics.drawdown * 100.0, 0.0, color="#dc2626", alpha=0.35)
    axes[0, 1].plot(timestamps, analytics.drawdown * 100.0, color="#991b1b", linewidth=1.2)
    exposure_axis = axes[0, 1].twinx()
    exposure_axis.plot(timestamps, analytics.gross_exposure, color="#1d4ed8", linewidth=1.1, alpha=0.85)
    axes[0, 1].set_title("Drawdown And Gross Exposure")
    axes[0, 1].set_ylabel("Drawdown %")
    exposure_axis.set_ylabel("Gross Exposure")
    axes[0, 1].grid(alpha=0.25, linewidth=0.6)

    axes[1, 0].plot(timestamps, analytics.active_grids, color="#7c3aed", linewidth=1.4, label="Active Grids")
    grid_axis = axes[1, 0].twinx()
    grid_axis.plot(timestamps, analytics.cumulative_grid_crosses, color="#0f766e", linewidth=1.2, label="Cumulative Crosses")
    axes[1, 0].set_title("Grid Usage")
    axes[1, 0].set_ylabel("Active Grids")
    grid_axis.set_ylabel("Grid Crosses")
    axes[1, 0].grid(alpha=0.25, linewidth=0.6)

    axes[1, 1].bar(timestamps, analytics.step_fills, color="#2563eb", alpha=0.55, label="Fills / Step")
    fill_axis = axes[1, 1].twinx()
    fill_axis.plot(timestamps, analytics.cumulative_fill_rate * 100.0, color="#ea580c", linewidth=1.2, label="Cumulative Fill Rate")
    axes[1, 1].set_title("Fill Frequency")
    axes[1, 1].set_ylabel("Step Fills")
    fill_axis.set_ylabel("Fill Rate %")
    axes[1, 1].grid(alpha=0.25, linewidth=0.6)

    axes[2, 0].plot(timestamps, analytics.cumulative_breakouts, color="#16a34a", linewidth=1.3, label="Aligned Breakouts")
    axes[2, 0].plot(timestamps, analytics.cumulative_fake_breakouts, color="#dc2626", linewidth=1.3, label="Fake Breakouts")
    axes[2, 0].set_title("Breakout Quality")
    axes[2, 0].set_ylabel("Count")
    axes[2, 0].grid(alpha=0.25, linewidth=0.6)
    axes[2, 0].legend(frameon=False, loc="upper left")

    axes[2, 1].axis("off")
    total_crosses = analytics.cumulative_grid_crosses[-1]
    total_fills = analytics.cumulative_fills[-1]
    summary = "\n".join(
        [
            f"Final equity: {analytics.equity_curve[-1]:,.2f}",
            f"Max drawdown: {analytics.max_drawdown * 100.0:.2f}%",
            f"Total active grids: {analytics.active_grids[-1]:.0f}",
            f"Grid crosses: {total_crosses:.0f}",
            f"Total fills: {total_fills:.0f}",
            f"Fill rate: {analytics.cumulative_fill_rate[-1] * 100.0:.2f}%",
            f"Aligned breakouts: {analytics.cumulative_breakouts[-1]:.0f}",
            f"Fake breakouts: {analytics.cumulative_fake_breakouts[-1]:.0f}",
        ]
    )
    axes[2, 1].text(
        0.02,
        0.96,
        summary,
        va="top",
        ha="left",
        fontsize=11,
        family="monospace",
        bbox={"facecolor": "#f8fafc", "edgecolor": "#cbd5e1", "boxstyle": "round,pad=0.6"},
    )

    axes[2, 0].set_xlabel("Time")
    axes[1, 1].set_xlabel("Time")
    for axis in (axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1], axes[2, 0]):
        _format_time_axis(axis, analytics.timestamps)

    figure.suptitle("Reinforced Walk-Forward Grid Dashboard")
    figure.subplots_adjust(hspace=0.35, wspace=0.30, bottom=0.10, top=0.93)
    figure.savefig(output, dpi=150)
    plt.close(figure)
    return output


def create_demo_plots(
    output_dir: str | Path,
    *,
    years: int = 10,
    steps_per_year: int = 365,
    seed: int = 21,
) -> PlotArtifacts:
    output_root = Path(output_dir)
    simulation = simulate_price_paths(years=years, steps_per_year=steps_per_year, seed=seed)
    bots = {symbol: GridTradingBot(symbol) for symbol in simulation.asset_symbols}
    manager = AssetGridManager(bots)
    portfolio_history = manager.run_simulation(simulation)
    walkforward_histories = _build_walkforward_demo_histories()
    walkforward_coordinator = RuleBasedGridCoordinator(
        {symbol: GridTradingBot(symbol) for symbol in walkforward_histories},
        CoordinatorConfig(),
    )
    walkforward_history = run_walk_forward_backtest(walkforward_coordinator, walkforward_histories)

    return PlotArtifacts(
        market_overview=save_market_overview(simulation, output_root / "market_overview.png"),
        portfolio_overview=save_portfolio_overview(portfolio_history, output_root / "portfolio_overview.png"),
        walkforward_dashboard=save_walkforward_dashboard(walkforward_history, output_root / "walkforward_dashboard.png"),
    )


def _shade_regimes(axis: plt.Axes, timestamps: Sequence, regimes: Sequence[MacroRegime]) -> None:
    if len(timestamps) != len(regimes) + 1:
        raise ValueError("timestamps must contain exactly one more item than regimes")

    segment_start = 0
    current_regime = regimes[0]
    for index in range(1, len(regimes) + 1):
        reached_end = index == len(regimes)
        next_regime = None if reached_end else regimes[index]
        if reached_end or next_regime != current_regime:
            axis.axvspan(
                timestamps[segment_start],
                timestamps[index],
                color=REGIME_COLORS[current_regime],
                alpha=0.35,
                linewidth=0.0,
            )
            if not reached_end:
                segment_start = index
                current_regime = next_regime


def _build_walkforward_demo_histories() -> dict[str, MarketFrame]:
    start = np.datetime64("2024-01-01")
    symbols = {
        "BTC": {
            "daily": [100.0 + 0.28 * index for index in range(221)],
            "intraday": [100.0] * 50 + [99.6] * 50 + _alternating_path(101.0, 90, 0.05, 0.95),
            "boosted": set(range(120, 190)),
            "boost": 900.0,
        },
        "SP500": {
            "daily": [200.0 + 0.10 * index for index in range(221)],
            "intraday": [200.0] * 50 + [199.7] * 50 + _alternating_path(200.6, 90, 0.02, 0.55),
            "boosted": set(range(135, 190)),
            "boost": 350.0,
        },
        "SOL": {
            "daily": [60.0 + 0.42 * index for index in range(221)],
            "intraday": [60.0] * 50 + [59.2] * 50 + _alternating_path(61.0, 90, 0.09, 1.35),
            "boosted": set(range(110, 190)),
            "boost": 1_400.0,
        },
        "GOLD": {
            "daily": [180.0 - 0.12 * index for index in range(221)],
            "intraday": [180.0] * 50 + [180.4] * 50 + _alternating_path(179.4, 90, -0.04, 0.90),
            "boosted": set(range(118, 190)),
            "boost": 600.0,
        },
    }
    base_day = _to_datetime(start)
    intraday_day = _to_datetime(start + np.timedelta64(220, "D"))
    histories: dict[str, MarketFrame] = {}
    for symbol, profile in symbols.items():
        histories[symbol] = MarketFrame(
            daily_bars=_bars_from_closes(
                profile["daily"],
                start=base_day,
                step=timedelta(days=1),
                high_pad=1.2,
                low_pad=1.2,
                base_volume=1_200.0,
            ),
            five_minute_bars=_bars_from_closes(
                profile["intraday"],
                start=intraday_day,
                step=timedelta(minutes=5),
                high_pad=0.8,
                low_pad=0.8,
                base_volume=120.0,
                boosted_indices=profile["boosted"],
                boost_size=profile["boost"],
            ),
        )
    return histories


def _bars_from_closes(
    closes: Sequence[float],
    *,
    start,
    step,
    high_pad: float,
    low_pad: float,
    base_volume: float,
    boosted_indices: set[int] | None = None,
    boost_size: float = 0.0,
) -> tuple[PriceBar, ...]:
    boosted_indices = boosted_indices or set()
    previous = float(closes[0])
    bars: list[PriceBar] = []
    for index, close in enumerate(closes):
        volume = base_volume + (boost_size if index in boosted_indices else 0.0)
        bars.append(
            PriceBar(
                timestamp=start + step * index,
                open=previous,
                high=float(close) + high_pad,
                low=float(close) - low_pad,
                close=float(close),
                volume=volume,
            )
        )
        previous = float(close)
    return tuple(bars)


def _alternating_path(base: float, steps: int, drift: float, amplitude: float) -> list[float]:
    values: list[float] = []
    level = base
    for index in range(steps):
        level += drift
        values.append(level + (amplitude if index % 2 == 0 else -amplitude))
    return values


def _plot_x_values(timestamps: Sequence) -> Sequence:
    if all(timestamp is not None for timestamp in timestamps):
        return timestamps
    return np.arange(len(timestamps))


def _format_time_axis(axis: plt.Axes, timestamps: Sequence) -> None:
    if all(timestamp is not None for timestamp in timestamps):
        locator = mdates.AutoDateLocator(maxticks=6)
        formatter = mdates.ConciseDateFormatter(locator)
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(formatter)


def _to_datetime(value: np.datetime64):
    epoch_seconds = value.astype("datetime64[s]").astype(int)
    return datetime.utcfromtimestamp(int(epoch_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate plots for the Binance Grid research toolkit.")
    parser.add_argument("--output-dir", default="artifacts/plots", help="Directory where PNG plots will be written.")
    parser.add_argument("--years", type=int, default=10, help="Simulation horizon in years.")
    parser.add_argument("--steps-per-year", type=int, default=365, help="Number of simulation steps per year.")
    parser.add_argument("--seed", type=int, default=21, help="Random seed for deterministic plot generation.")
    args = parser.parse_args()

    artifacts = create_demo_plots(
        args.output_dir,
        years=args.years,
        steps_per_year=args.steps_per_year,
        seed=args.seed,
    )
    for name, path in artifacts.as_dict().items():
        print(f"{name}: {path.resolve()}")


if __name__ == "__main__":
    main()