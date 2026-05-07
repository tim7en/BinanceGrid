from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

import numpy as np

from ..common import MarketBar


class TrendRegime(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"


class BreakoutDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class VolumePhase(StrEnum):
    EXPANSION = "expansion"
    COMPRESSION = "compression"


@dataclass(frozen=True)
class MovingAverageState:
    fast_value: float
    slow_value: float
    regime: TrendRegime
    crossed_up: bool
    crossed_down: bool


@dataclass(frozen=True)
class DonchianState:
    window: int
    upper: float
    middle: float
    lower: float


@dataclass(frozen=True)
class VolumeState:
    fast_average: float
    slow_average: float
    ratio: float
    phase: VolumePhase


@dataclass(frozen=True)
class IndicatorSnapshot:
    vwap: float
    trend: MovingAverageState
    slow_donchian: DonchianState
    fast_donchian: DonchianState
    breakout: BreakoutDirection
    volume: VolumeState


def rolling_vwap(bars: Sequence[MarketBar], window: int | None = None) -> float:
    if not bars:
        raise ValueError("bars are required for VWAP")

    sample = bars if window is None else bars[-window:]
    prices = np.asarray([(bar.high + bar.low + bar.close) / 3.0 for bar in sample], dtype=float)
    volumes = np.asarray([bar.volume for bar in sample], dtype=float)
    return float(np.dot(prices, volumes) / max(volumes.sum(), 1e-9))


def moving_average_regime(
    closes: Sequence[float],
    *,
    fast_window: int = 50,
    slow_window: int = 200,
) -> MovingAverageState:
    if len(closes) < slow_window:
        raise ValueError("not enough closes for moving-average regime")

    close_array = np.asarray(closes, dtype=float)
    fast_value = float(close_array[-fast_window:].mean())
    slow_value = float(close_array[-slow_window:].mean())

    previous_fast = fast_value
    previous_slow = slow_value
    crossed_up = False
    crossed_down = False
    if len(closes) >= slow_window + 1:
        previous_fast = float(close_array[-fast_window - 1 : -1].mean())
        previous_slow = float(close_array[-slow_window - 1 : -1].mean())
        crossed_up = previous_fast <= previous_slow and fast_value > slow_value
        crossed_down = previous_fast >= previous_slow and fast_value < slow_value

    if fast_value > slow_value:
        regime = TrendRegime.BULL
    elif fast_value < slow_value:
        regime = TrendRegime.BEAR
    else:
        regime = TrendRegime.NEUTRAL

    return MovingAverageState(
        fast_value=fast_value,
        slow_value=slow_value,
        regime=regime,
        crossed_up=crossed_up,
        crossed_down=crossed_down,
    )


def donchian_channel(bars: Sequence[MarketBar], *, window: int) -> DonchianState:
    if len(bars) < window:
        raise ValueError("not enough bars for Donchian channel")

    sample = bars[-window:]
    upper = max(bar.high for bar in sample)
    lower = min(bar.low for bar in sample)
    return DonchianState(window=window, upper=upper, middle=(upper + lower) / 2.0, lower=lower)


def donchian_breakout_signal(bars: Sequence[MarketBar], *, window: int) -> BreakoutDirection:
    if len(bars) < window + 1:
        raise ValueError("not enough bars for Donchian breakout")

    reference = donchian_channel(bars[:-1], window=window)
    current_close = bars[-1].close
    if current_close > reference.upper:
        return BreakoutDirection.LONG
    if current_close < reference.lower:
        return BreakoutDirection.SHORT
    return BreakoutDirection.NONE


def volume_phase(
    bars: Sequence[MarketBar],
    *,
    fast_window: int = 50,
    slow_window: int = 200,
    expansion_threshold: float = 1.20,
) -> VolumeState:
    if len(bars) < slow_window:
        raise ValueError("not enough bars for volume phase")

    volumes = np.asarray([bar.volume for bar in bars], dtype=float)
    fast_average = float(volumes[-fast_window:].mean())
    slow_average = float(volumes[-slow_window:].mean())
    ratio = fast_average / max(slow_average, 1e-9)
    phase = VolumePhase.EXPANSION if ratio >= expansion_threshold else VolumePhase.COMPRESSION
    return VolumeState(
        fast_average=fast_average,
        slow_average=slow_average,
        ratio=ratio,
        phase=phase,
    )


def build_indicator_snapshot(
    daily_bars: Sequence[MarketBar],
    intraday_bars: Sequence[MarketBar],
) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        vwap=rolling_vwap(intraday_bars),
        trend=moving_average_regime([bar.close for bar in daily_bars]),
        slow_donchian=donchian_channel(intraday_bars[:-1], window=50),
        fast_donchian=donchian_channel(intraday_bars[:-1], window=10),
        breakout=donchian_breakout_signal(intraday_bars, window=50),
        volume=volume_phase(intraday_bars),
    )