from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import numpy as np

from .coordinator import CoordinatorSnapshot


@dataclass(frozen=True)
class WalkForwardAnalytics:
    timestamps: tuple[datetime | None, ...]
    equity_curve: np.ndarray
    step_returns: np.ndarray
    cumulative_returns: np.ndarray
    drawdown: np.ndarray
    gross_exposure: np.ndarray
    active_grids: np.ndarray
    step_grid_crosses: np.ndarray
    cumulative_grid_crosses: np.ndarray
    step_fills: np.ndarray
    cumulative_fills: np.ndarray
    cumulative_fill_rate: np.ndarray
    step_breakouts: np.ndarray
    cumulative_breakouts: np.ndarray
    step_fake_breakouts: np.ndarray
    cumulative_fake_breakouts: np.ndarray
    total_return: float
    annualized_return: float
    max_drawdown: float


def summarize_walkforward_snapshots(snapshots: Sequence[CoordinatorSnapshot]) -> WalkForwardAnalytics:
    if not snapshots:
        raise ValueError("walk-forward analytics require at least one snapshot")

    timestamps = tuple(snapshot.timestamp for snapshot in snapshots)
    equity_curve = np.array([snapshot.portfolio_equity for snapshot in snapshots], dtype=float)
    step_returns = np.zeros_like(equity_curve)
    if len(equity_curve) > 1:
        step_returns[1:] = np.divide(
            equity_curve[1:],
            np.maximum(equity_curve[:-1], 1e-9),
            out=np.ones(len(equity_curve) - 1, dtype=float),
        ) - 1.0
    cumulative_returns = np.divide(
        equity_curve,
        np.maximum(equity_curve[0], 1e-9),
        out=np.ones_like(equity_curve),
    ) - 1.0
    rolling_peak = np.maximum.accumulate(equity_curve)
    drawdown = np.divide(
        equity_curve,
        np.maximum(rolling_peak, 1e-9),
        out=np.ones_like(equity_curve),
    ) - 1.0
    gross_exposure = np.array([snapshot.gross_exposure for snapshot in snapshots], dtype=float)
    active_grids = np.array(
        [sum(decision.bot_snapshot.active_grid_levels for decision in snapshot.decisions.values()) for snapshot in snapshots],
        dtype=float,
    )
    step_grid_crosses = np.array(
        [sum(decision.bot_snapshot.grid_levels_crossed_in_step for decision in snapshot.decisions.values()) for snapshot in snapshots],
        dtype=float,
    )
    cumulative_grid_crosses = np.cumsum(step_grid_crosses)
    step_fills = np.array(
        [sum(decision.bot_snapshot.fills_in_step for decision in snapshot.decisions.values()) for snapshot in snapshots],
        dtype=float,
    )
    cumulative_fills = np.cumsum(step_fills)
    cumulative_fill_rate = np.divide(
        cumulative_fills,
        np.maximum(cumulative_grid_crosses, 1.0),
        out=np.zeros_like(cumulative_fills),
    )
    step_breakouts = np.array(
        [sum(1 for decision in snapshot.decisions.values() if decision.bias.breakout_triggered) for snapshot in snapshots],
        dtype=float,
    )
    cumulative_breakouts = np.cumsum(step_breakouts)
    step_fake_breakouts = np.array(
        [sum(1 for decision in snapshot.decisions.values() if decision.fake_breakout_triggered) for snapshot in snapshots],
        dtype=float,
    )
    cumulative_fake_breakouts = np.cumsum(step_fake_breakouts)
    total_return = float(cumulative_returns[-1])
    annualized_return = total_return
    if timestamps[0] is not None and timestamps[-1] is not None and timestamps[-1] > timestamps[0]:
        elapsed_years = (timestamps[-1] - timestamps[0]).total_seconds() / (365.25 * 24.0 * 60.0 * 60.0)
        if elapsed_years > 0.0:
            annualized_return = float((equity_curve[-1] / max(equity_curve[0], 1e-9)) ** (1.0 / elapsed_years) - 1.0)

    return WalkForwardAnalytics(
        timestamps=timestamps,
        equity_curve=equity_curve,
        step_returns=step_returns,
        cumulative_returns=cumulative_returns,
        drawdown=drawdown,
        gross_exposure=gross_exposure,
        active_grids=active_grids,
        step_grid_crosses=step_grid_crosses,
        cumulative_grid_crosses=cumulative_grid_crosses,
        step_fills=step_fills,
        cumulative_fills=cumulative_fills,
        cumulative_fill_rate=cumulative_fill_rate,
        step_breakouts=step_breakouts,
        cumulative_breakouts=cumulative_breakouts,
        step_fake_breakouts=step_fake_breakouts,
        cumulative_fake_breakouts=cumulative_fake_breakouts,
        total_return=total_return,
        annualized_return=annualized_return,
        max_drawdown=float(drawdown.min()),
    )