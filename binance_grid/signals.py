from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from .indicators import DonchianChannel, donchian_channel, simple_moving_average
from .strategy import GridBias


class CrossoverDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NONE = "none"


@dataclass(frozen=True)
class TrendBias:
    regime: GridBias
    ma_regime: GridBias
    fast_ma: float
    slow_ma: float
    donchian: DonchianChannel
    channel_position: float
    breakout_regime: GridBias
    breakout_triggered: bool
    breakout_persisted: bool
    fake_breakout: bool
    inside_channel: bool


@dataclass(frozen=True)
class CrossoverSignal:
    direction: CrossoverDirection
    crossed: bool
    previous_fast_ma: float
    previous_slow_ma: float
    current_fast_ma: float
    current_slow_ma: float


def determine_daily_bias(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    fast_window: int = 50,
    slow_window: int = 200,
    donchian_window: int = 20,
    previous_breakout: GridBias = GridBias.NEUTRAL,
) -> TrendBias:
    if len(closes) < max(slow_window, donchian_window + 1):
        raise ValueError("not enough daily closes for bias calculation")

    fast_ma = simple_moving_average(closes, fast_window)
    slow_ma = simple_moving_average(closes, slow_window)
    channel = donchian_channel(highs[:-1], lows[:-1], donchian_window)
    price = float(closes[-1])
    channel_position = (price - channel.lower) / max(channel.width, 1e-9)
    inside_channel = channel.lower <= price <= channel.upper

    if fast_ma > slow_ma:
        ma_regime = GridBias.LONG
    elif fast_ma < slow_ma:
        ma_regime = GridBias.SHORT
    else:
        ma_regime = GridBias.NEUTRAL

    breakout_triggered = False
    breakout_persisted = False
    fake_breakout = False
    if price > channel.upper and ma_regime == GridBias.LONG:
        breakout_regime = GridBias.LONG
        breakout_triggered = True
    elif price < channel.lower and ma_regime == GridBias.SHORT:
        breakout_regime = GridBias.SHORT
        breakout_triggered = True
    elif previous_breakout == GridBias.LONG:
        breakout_regime = GridBias.LONG
        breakout_persisted = True
    elif previous_breakout == GridBias.SHORT:
        breakout_regime = GridBias.SHORT
        breakout_persisted = True
    else:
        breakout_regime = GridBias.NEUTRAL

    if previous_breakout == GridBias.LONG and inside_channel:
        fake_breakout = True
    elif previous_breakout == GridBias.SHORT and inside_channel:
        fake_breakout = True

    if breakout_regime != GridBias.NEUTRAL:
        regime = breakout_regime
    elif ma_regime == GridBias.LONG and channel_position >= 0.5:
        regime = GridBias.LONG
    elif ma_regime == GridBias.SHORT and channel_position <= 0.5:
        regime = GridBias.SHORT
    else:
        regime = GridBias.NEUTRAL

    return TrendBias(
        regime=regime,
        ma_regime=ma_regime,
        fast_ma=fast_ma,
        slow_ma=slow_ma,
        donchian=channel,
        channel_position=channel_position,
        breakout_regime=breakout_regime,
        breakout_triggered=breakout_triggered,
        breakout_persisted=breakout_persisted,
        fake_breakout=fake_breakout,
        inside_channel=inside_channel,
    )


def detect_moving_average_crossover(
    closes: Sequence[float],
    *,
    fast_window: int = 50,
    slow_window: int = 100,
) -> CrossoverSignal:
    if len(closes) < slow_window + 1:
        raise ValueError("not enough intraday closes for crossover detection")

    previous_fast_ma = simple_moving_average(closes[:-1], fast_window)
    previous_slow_ma = simple_moving_average(closes[:-1], slow_window)
    current_fast_ma = simple_moving_average(closes, fast_window)
    current_slow_ma = simple_moving_average(closes, slow_window)

    bullish = previous_fast_ma <= previous_slow_ma and current_fast_ma > current_slow_ma
    bearish = previous_fast_ma >= previous_slow_ma and current_fast_ma < current_slow_ma
    if bullish:
        direction = CrossoverDirection.BULLISH
    elif bearish:
        direction = CrossoverDirection.BEARISH
    else:
        direction = CrossoverDirection.NONE

    return CrossoverSignal(
        direction=direction,
        crossed=direction != CrossoverDirection.NONE,
        previous_fast_ma=previous_fast_ma,
        previous_slow_ma=previous_slow_ma,
        current_fast_ma=current_fast_ma,
        current_slow_ma=current_slow_ma,
    )


def resolve_trade_regime(
    bias: TrendBias,
    crossover: CrossoverSignal,
    previous_regime: GridBias,
) -> GridBias:
    if crossover.direction == CrossoverDirection.BULLISH:
        return GridBias.LONG if bias.regime == GridBias.LONG else GridBias.NEUTRAL
    if crossover.direction == CrossoverDirection.BEARISH:
        return GridBias.SHORT if bias.regime == GridBias.SHORT else GridBias.NEUTRAL
    if bias.regime == previous_regime:
        return previous_regime
    return GridBias.NEUTRAL