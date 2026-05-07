from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .coordinator import CoordinatorConfig, CoordinatorSnapshot, MarketFrame, RuleBasedGridCoordinator


def build_walk_forward_batches(
    histories: Mapping[str, MarketFrame],
    config: CoordinatorConfig,
) -> list[dict[str, MarketFrame]]:
    if not histories:
        raise ValueError("walk-forward histories cannot be empty")

    intraday_required = max(
        config.intraday_slow_window + 1,
        config.volume_slow_window,
        config.atr_window + 1,
    )
    daily_required = config.daily_slow_window
    max_steps = min(len(frame.five_minute_bars) for frame in histories.values())
    batches: list[dict[str, MarketFrame]] = []

    for end_index in range(intraday_required, max_steps + 1):
        batch: dict[str, MarketFrame] = {}
        ready = True
        for symbol, history in histories.items():
            current_bar = history.five_minute_bars[end_index - 1]
            if current_bar.timestamp is None:
                raise ValueError("walk-forward intraday bars require timestamps")
            daily_bars = _completed_daily_bars(history.daily_bars, current_bar.timestamp)
            if len(daily_bars) < daily_required:
                ready = False
                break
            batch[symbol] = MarketFrame(
                daily_bars=daily_bars,
                five_minute_bars=history.five_minute_bars[:end_index],
            )
        if ready:
            batches.append(batch)
    return batches


def run_walk_forward_backtest(
    coordinator: RuleBasedGridCoordinator,
    histories: Mapping[str, MarketFrame],
) -> list[CoordinatorSnapshot]:
    batches = build_walk_forward_batches(histories, coordinator.config)
    return [coordinator.step(batch) for batch in batches]


def _completed_daily_bars(bars: tuple, current_timestamp: datetime) -> tuple:
    return tuple(
        bar
        for bar in bars
        if bar.timestamp is not None and bar.timestamp.date() < current_timestamp.date()
    )