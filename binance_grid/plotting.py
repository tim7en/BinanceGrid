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

from .manager import AssetGridManager, PortfolioSnapshot
from .simulation import MacroRegime, SimulationResult, simulate_price_paths
from .strategy import GridBias, GridTradingBot


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
    market_overview: Path
    portfolio_overview: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "market_overview": self.market_overview,
            "portfolio_overview": self.portfolio_overview,
        }


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

    return PlotArtifacts(
        market_overview=save_market_overview(simulation, output_root / "market_overview.png"),
        portfolio_overview=save_portfolio_overview(portfolio_history, output_root / "portfolio_overview.png"),
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