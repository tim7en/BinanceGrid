from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

import numpy as np


class MacroRiskRegime(StrEnum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"


@dataclass(frozen=True)
class MacroRegimeState:
    regime: MacroRiskRegime
    score: float
    dxy_score: float
    curve_score: float
    vix_score: float
    sentiment_score: float
    leverage_cap: float


def assess_macro_regime(
    dxy_values: Sequence[float],
    spread_10y2y_values: Sequence[float],
    spread_2y3m_values: Sequence[float],
    vix_values: Sequence[float],
    fear_greed_values: Sequence[float],
    *,
    lookback: int = 20,
) -> MacroRegimeState:
    if min(len(dxy_values), len(spread_10y2y_values), len(spread_2y3m_values), len(vix_values), len(fear_greed_values)) < lookback:
        raise ValueError("not enough macro observations")

    dxy_score = _trend_score(dxy_values[-lookback:], inverse=True)
    curve_score = _curve_score(spread_10y2y_values[-1], spread_2y3m_values[-1])
    vix_score = _vix_score(vix_values[-lookback:])
    sentiment_score = _sentiment_score(fear_greed_values[-lookback:])
    score = dxy_score + curve_score + vix_score + sentiment_score

    if score >= 1.25:
        regime = MacroRiskRegime.RISK_ON
        leverage_cap = 5.0
    elif score <= -1.25:
        regime = MacroRiskRegime.RISK_OFF
        leverage_cap = 2.0
    else:
        regime = MacroRiskRegime.NEUTRAL
        leverage_cap = 3.5

    return MacroRegimeState(
        regime=regime,
        score=score,
        dxy_score=dxy_score,
        curve_score=curve_score,
        vix_score=vix_score,
        sentiment_score=sentiment_score,
        leverage_cap=leverage_cap,
    )


def _trend_score(values: Sequence[float], *, inverse: bool = False) -> float:
    array = np.asarray(values, dtype=float)
    latest = float(array[-1])
    average = float(array.mean())
    if latest == average:
        score = 0.0
    elif latest > average:
        score = -0.75 if inverse else 0.75
    else:
        score = 0.75 if inverse else -0.75
    return score


def _curve_score(spread_10y2y: float, spread_2y3m: float) -> float:
    score = 0.0
    score += 0.75 if spread_10y2y > 0.0 else -0.75
    score += 0.50 if spread_2y3m > 0.0 else -0.50
    return score


def _vix_score(values: Sequence[float]) -> float:
    latest = float(values[-1])
    if latest <= 20.0:
        return 0.75
    if latest >= 28.0:
        return -0.75
    return 0.0


def _sentiment_score(values: Sequence[float]) -> float:
    latest = float(values[-1])
    if latest >= 60.0:
        return 0.50
    if latest <= 40.0:
        return -0.50
    return 0.0