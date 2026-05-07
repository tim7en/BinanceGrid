from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from .modules.bot import GridBias
from .modules.portfolio import PortfolioManagerSnapshot, summarize_walkforward_snapshots
from .simulation import MacroRegime, SimulationResult, simulate_price_paths


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
    walkforward_dashboard: Path | None = None

    def as_dict(self) -> dict[str, Path]:
        artifacts: dict[str, Path] = {}
        if self.market_overview is not None:
            artifacts["market_overview"] = self.market_overview
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


def save_walkforward_dashboard(
    snapshots: Sequence[PortfolioManagerSnapshot],
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
    years: int = 3,
    seed: int = 21,
    intraday_seed: int = 121,
    intraday_bars_per_day: int = 24,
) -> PlotArtifacts:
    output_root = Path(output_dir)
    from .generated import run_generated_backtest

    result = run_generated_backtest(
        years=years,
        seed=seed,
        intraday_seed=intraday_seed,
        intraday_bars_per_day=intraday_bars_per_day,
        output_dir=output_root,
    )
    return PlotArtifacts(
        market_overview=None if result.artifacts is None else result.artifacts.market_overview,
        walkforward_dashboard=None if result.artifacts is None else result.artifacts.walkforward_dashboard,
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
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate plots for the Binance Grid research toolkit.")
    parser.add_argument("--output-dir", default="artifacts/plots", help="Directory where PNG plots will be written.")
    parser.add_argument("--years", type=int, default=3, help="Simulation horizon in years.")
    parser.add_argument("--seed", type=int, default=21, help="Random seed for deterministic plot generation.")
    parser.add_argument("--intraday-seed", type=int, default=121, help="Random seed for intraday path expansion.")
    parser.add_argument("--intraday-bars-per-day", type=int, default=24, help="Compressed intraday bars per synthetic day.")
    args = parser.parse_args()

    artifacts = create_demo_plots(
        args.output_dir,
        years=args.years,
        seed=args.seed,
        intraday_seed=args.intraday_seed,
        intraday_bars_per_day=args.intraday_bars_per_day,
    )
    for name, path in artifacts.as_dict().items():
        print(f"{name}: {path.resolve()}")


if __name__ == "__main__":
    main()