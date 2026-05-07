from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from typing import Iterator, Mapping, Sequence

from ..bot import SingleAssetInput
from ..common import MarketBar
from .manager import PortfolioManagerSnapshot, PortfolioRiskController


@dataclass(frozen=True)
class AssetHistory:
    daily_bars: tuple[MarketBar, ...]
    intraday_bars: tuple[MarketBar, ...]


@dataclass(frozen=True)
class MacroHistory:
    dxy_values: tuple[float, ...]
    spread_10y2y_values: tuple[float, ...]
    spread_2y3m_values: tuple[float, ...]
    vix_values: tuple[float, ...]
    fear_greed_values: tuple[float, ...]


class _PrefixView(Sequence):
    def __init__(self, source: tuple[MarketBar, ...], stop: int) -> None:
        self._source = source
        self._stop = stop

    def __len__(self) -> int:
        return self._stop

    def __iter__(self):
        return islice(self._source, self._stop)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return tuple(self)[item]
        index = item
        if index < 0:
            index += self._stop
        if index < 0 or index >= self._stop:
            raise IndexError(index)
        return self._source[index]


def iter_walk_forward_inputs(
    histories: Mapping[str, AssetHistory],
    macro_history: MacroHistory,
) -> Iterator[dict[str, SingleAssetInput]]:
    if not histories:
        raise ValueError("walk-forward histories cannot be empty")

    intraday_required = 201
    daily_required = 200
    macro_required = 25
    max_steps = min(len(history.intraday_bars) for history in histories.values())
    for end_index in range(intraday_required, max_steps + 1):
        batch: dict[str, SingleAssetInput] = {}
        ready = True
        for symbol, history in histories.items():
            current_bar = history.intraday_bars[end_index - 1]
            if current_bar.timestamp is None:
                raise ValueError("intraday bars require timestamps")
            daily_bars = _completed_daily_bars(history.daily_bars, current_bar.timestamp)
            macro_index = len(daily_bars)
            if len(daily_bars) < daily_required or macro_index < macro_required:
                ready = False
                break
            batch[symbol] = SingleAssetInput(
                daily_bars=daily_bars,
                intraday_bars=_PrefixView(history.intraday_bars, end_index),
                dxy_values=macro_history.dxy_values[:macro_index],
                spread_10y2y_values=macro_history.spread_10y2y_values[:macro_index],
                spread_2y3m_values=macro_history.spread_2y3m_values[:macro_index],
                vix_values=macro_history.vix_values[:macro_index],
                fear_greed_values=macro_history.fear_greed_values[:macro_index],
            )
        if ready:
            yield batch


def run_walk_forward_backtest(
    controller: PortfolioRiskController,
    histories: Mapping[str, AssetHistory],
    macro_history: MacroHistory,
) -> list[PortfolioManagerSnapshot]:
    return [controller.step(batch) for batch in iter_walk_forward_inputs(histories, macro_history)]


def _completed_daily_bars(bars: tuple[MarketBar, ...], current_timestamp: datetime) -> tuple[MarketBar, ...]:
    return tuple(
        bar
        for bar in bars
        if bar.timestamp is not None and bar.timestamp.date() < current_timestamp.date()
    )