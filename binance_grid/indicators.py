from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class DonchianChannel:
    upper: float
    middle: float
    lower: float
    width: float


@dataclass(frozen=True)
class AtrMetrics:
    atr: float
    atr_pct: float


@dataclass(frozen=True)
class VolumeSignal:
    ratio: float
    confirmed: bool
    leverage_multiplier: float


def annualized_realized_volatility(closes: Sequence[float], periods_per_year: int) -> float:
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    if len(closes) < 3:
        return 0.0

    array = np.asarray(closes, dtype=float)
    returns = np.diff(np.log(array))
    if len(returns) < 2:
        return 0.0
    return float(returns.std(ddof=1) * math.sqrt(periods_per_year))


def simple_moving_average(values: Sequence[float], window: int) -> float:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        raise ValueError("not enough values for moving average")

    array = np.asarray(values[-window:], dtype=float)
    return float(array.mean())


def donchian_channel(highs: Sequence[float], lows: Sequence[float], window: int) -> DonchianChannel:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(highs) < window or len(lows) < window:
        raise ValueError("not enough values for donchian channel")

    high_array = np.asarray(highs[-window:], dtype=float)
    low_array = np.asarray(lows[-window:], dtype=float)
    upper = float(high_array.max())
    lower = float(low_array.min())
    middle = (upper + lower) / 2.0
    return DonchianChannel(upper=upper, middle=middle, lower=lower, width=upper - lower)


def average_true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    window: int,
) -> AtrMetrics:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows, and closes must have equal length")
    if len(closes) < window + 1:
        raise ValueError("not enough values for ATR")

    high_array = np.asarray(highs, dtype=float)
    low_array = np.asarray(lows, dtype=float)
    close_array = np.asarray(closes, dtype=float)
    previous_close = close_array[:-1]
    true_ranges = np.maximum.reduce(
        [
            high_array[1:] - low_array[1:],
            np.abs(high_array[1:] - previous_close),
            np.abs(low_array[1:] - previous_close),
        ]
    )
    atr = float(true_ranges[-window:].mean())
    last_close = float(close_array[-1])
    return AtrMetrics(atr=atr, atr_pct=atr / max(last_close, 1e-9))


def volume_confirmation(
    volumes: Sequence[float],
    *,
    fast_window: int = 20,
    slow_window: int = 50,
    leverage_cap: float = 3.0,
    confirmation_threshold: float = 1.20,
) -> VolumeSignal:
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("volume windows must be positive")
    if slow_window < fast_window:
        raise ValueError("slow window must be at least fast window")
    if len(volumes) < slow_window:
        raise ValueError("not enough values for volume confirmation")

    array = np.asarray(volumes, dtype=float)
    fast_average = float(array[-fast_window:].mean())
    slow_average = float(array[-slow_window:].mean())
    ratio = fast_average / max(slow_average, 1e-9)
    confirmed = ratio >= confirmation_threshold
    leverage_multiplier = min(leverage_cap, max(1.0, ratio)) if confirmed else 1.0
    return VolumeSignal(
        ratio=ratio,
        confirmed=confirmed,
        leverage_multiplier=leverage_multiplier,
    )