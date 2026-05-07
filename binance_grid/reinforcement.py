from __future__ import annotations

from dataclasses import dataclass

from .indicators import VolumeSignal
from .signals import CrossoverDirection, CrossoverSignal, TrendBias
from .strategy import GridBias


@dataclass(frozen=True)
class ReinforcementConfig:
    bias_weight: float = 0.85
    breakout_weight: float = 0.85
    breakout_hold_weight: float = 0.80
    crossover_weight: float = 1.15
    channel_weight: float = 0.35
    volume_weight: float = 0.40
    persistence_weight: float = 0.20
    entry_threshold: float = 1.75
    exit_threshold: float = 0.65


@dataclass(frozen=True)
class ReinforcementState:
    regime: GridBias
    long_score: float
    short_score: float
    net_score: float
    conviction: float
    applied_leverage: float


def compute_reinforcement(
    bias: TrendBias,
    crossover: CrossoverSignal,
    volume: VolumeSignal,
    previous_regime: GridBias,
    active_breakout: GridBias,
    config: ReinforcementConfig | None = None,
) -> ReinforcementState:
    config = config or ReinforcementConfig()
    long_score = 0.0
    short_score = 0.0

    if bias.ma_regime == GridBias.LONG:
        long_score += config.bias_weight
    elif bias.ma_regime == GridBias.SHORT:
        short_score += config.bias_weight

    channel_tilt = max(-1.0, min(1.0, (bias.channel_position - 0.5) * 2.0))
    long_score += config.channel_weight * max(channel_tilt, 0.0)
    short_score += config.channel_weight * max(-channel_tilt, 0.0)

    if bias.breakout_regime == GridBias.LONG and bias.breakout_triggered:
        long_score += config.breakout_weight
    elif bias.breakout_regime == GridBias.SHORT and bias.breakout_triggered:
        short_score += config.breakout_weight

    if active_breakout == GridBias.LONG:
        long_score += config.breakout_hold_weight
    elif active_breakout == GridBias.SHORT:
        short_score += config.breakout_hold_weight

    if crossover.direction == CrossoverDirection.BULLISH:
        long_score += config.crossover_weight
    elif crossover.direction == CrossoverDirection.BEARISH:
        short_score += config.crossover_weight

    if volume.confirmed:
        volume_boost = config.volume_weight * max(volume.leverage_multiplier - 1.0, 0.0)
        if crossover.direction == CrossoverDirection.BULLISH or bias.ma_regime == GridBias.LONG or active_breakout == GridBias.LONG:
            long_score += volume_boost
        if crossover.direction == CrossoverDirection.BEARISH or bias.ma_regime == GridBias.SHORT or active_breakout == GridBias.SHORT:
            short_score += volume_boost

    if previous_regime == GridBias.LONG:
        long_score += config.persistence_weight
    elif previous_regime == GridBias.SHORT:
        short_score += config.persistence_weight

    net_score = long_score - short_score
    conviction = max(long_score, short_score)
    if net_score >= config.entry_threshold:
        regime = GridBias.LONG
    elif net_score <= -config.entry_threshold:
        regime = GridBias.SHORT
    elif abs(net_score) <= config.exit_threshold:
        regime = GridBias.NEUTRAL
    else:
        regime = previous_regime

    applied_leverage = volume.leverage_multiplier if regime != GridBias.NEUTRAL and volume.confirmed else 1.0
    return ReinforcementState(
        regime=regime,
        long_score=long_score,
        short_score=short_score,
        net_score=net_score,
        conviction=conviction,
        applied_leverage=applied_leverage,
    )