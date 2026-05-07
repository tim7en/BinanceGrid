from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from ..common import MarketBar
from ..indicators import BreakoutDirection, IndicatorSnapshot, TrendRegime, rolling_vwap
from ..macro_regime import MacroRegimeState, MacroRiskRegime


@dataclass(frozen=True)
class GridRiskPlan:
    current_price: float
    vwap_reference: float
    atr: float
    atr_pct: float
    realized_volatility_200: float
    lower_range: float
    upper_range: float
    grid_count: int
    level_spacing: float
    leverage: float
    total_grid_notional: float
    initial_entry_notional: float
    reserve_notional: float
    order_notional: float
    buy_levels: tuple[float, ...]
    sell_levels: tuple[float, ...]


def build_grid_risk_plan(
    indicator_snapshot: IndicatorSnapshot,
    intraday_bars: Sequence[MarketBar],
    macro_regime: MacroRegimeState,
    *,
    allocated_capital: float,
    atr_window: int = 20,
) -> GridRiskPlan:
    if len(intraday_bars) < max(atr_window + 1, 201):
        raise ValueError("not enough intraday bars for grid risk planning")
    if allocated_capital <= 0.0:
        raise ValueError("allocated_capital must be positive")

    current_price = intraday_bars[-1].close
    atr = _average_true_range(intraday_bars, window=atr_window)
    atr_pct = atr / max(current_price, 1e-9)
    realized_vol = realized_volatility_200(intraday_bars)
    grid_count = _estimate_grid_count(realized_vol)
    leverage = _estimate_leverage(indicator_snapshot, macro_regime, current_price)
    total_grid_notional = allocated_capital * leverage
    initial_entry_notional = total_grid_notional * 0.30
    reserve_notional = total_grid_notional - initial_entry_notional
    half_range = max(atr * (1.8 + grid_count * 0.10), current_price * realized_vol * 3.0)

    if indicator_snapshot.trend.regime == TrendRegime.BULL:
        lower_range = min(indicator_snapshot.slow_donchian.lower - atr, current_price - half_range * 1.15)
        upper_range = max(indicator_snapshot.fast_donchian.upper + atr * 0.50, current_price + half_range * 0.65)
    elif indicator_snapshot.trend.regime == TrendRegime.BEAR:
        lower_range = min(indicator_snapshot.fast_donchian.lower - atr * 0.50, current_price - half_range * 0.65)
        upper_range = max(indicator_snapshot.slow_donchian.upper + atr, current_price + half_range * 1.15)
    else:
        lower_range = current_price - half_range
        upper_range = current_price + half_range

    level_spacing = max((upper_range - lower_range) / max(grid_count, 1), atr * 0.85)
    order_notional = reserve_notional / max(grid_count, 1)
    buy_levels, sell_levels = _build_levels(current_price, lower_range, upper_range, level_spacing)
    return GridRiskPlan(
        current_price=current_price,
        vwap_reference=rolling_vwap(intraday_bars, window=min(len(intraday_bars), 50)),
        atr=atr,
        atr_pct=atr_pct,
        realized_volatility_200=realized_vol,
        lower_range=lower_range,
        upper_range=upper_range,
        grid_count=grid_count,
        level_spacing=level_spacing,
        leverage=leverage,
        total_grid_notional=total_grid_notional,
        initial_entry_notional=initial_entry_notional,
        reserve_notional=reserve_notional,
        order_notional=order_notional,
        buy_levels=buy_levels,
        sell_levels=sell_levels,
    )


def realized_volatility_200(intraday_bars: Sequence[MarketBar]) -> float:
    if len(intraday_bars) < 201:
        raise ValueError("not enough intraday bars for 200-bar volatility")

    closes = np.asarray([bar.close for bar in intraday_bars[-201:]], dtype=float)
    log_returns = np.diff(np.log(closes))
    return float(log_returns.std(ddof=1))


def _average_true_range(intraday_bars: Sequence[MarketBar], *, window: int) -> float:
    highs = np.asarray([bar.high for bar in intraday_bars], dtype=float)
    lows = np.asarray([bar.low for bar in intraday_bars], dtype=float)
    closes = np.asarray([bar.close for bar in intraday_bars], dtype=float)
    previous_closes = closes[:-1]
    true_ranges = np.maximum.reduce(
        [
            highs[1:] - lows[1:],
            np.abs(highs[1:] - previous_closes),
            np.abs(lows[1:] - previous_closes),
        ]
    )
    return float(true_ranges[-window:].mean())


def _estimate_grid_count(realized_vol: float) -> int:
    return max(6, min(28, int(round(8 + realized_vol * 1_800.0))))


def _estimate_leverage(
    indicator_snapshot: IndicatorSnapshot,
    macro_regime: MacroRegimeState,
    current_price: float,
) -> float:
    alignment_score = 0.0
    if indicator_snapshot.trend.regime != TrendRegime.NEUTRAL:
        alignment_score += 1.0
    if indicator_snapshot.breakout == BreakoutDirection.LONG and indicator_snapshot.trend.regime == TrendRegime.BULL:
        alignment_score += 1.0
    if indicator_snapshot.breakout == BreakoutDirection.SHORT and indicator_snapshot.trend.regime == TrendRegime.BEAR:
        alignment_score += 1.0
    if indicator_snapshot.volume.phase.value == "expansion":
        alignment_score += 1.0
    if indicator_snapshot.trend.regime == TrendRegime.BULL and current_price >= indicator_snapshot.vwap:
        alignment_score += 0.5
    if indicator_snapshot.trend.regime == TrendRegime.BEAR and current_price <= indicator_snapshot.vwap:
        alignment_score += 0.5
    leverage = 2.0 + min(alignment_score, 3.0)
    if macro_regime.regime == MacroRiskRegime.RISK_OFF:
        leverage = min(leverage, 2.0)
    return max(2.0, min(leverage, macro_regime.leverage_cap, 5.0))


def _build_levels(current_price: float, lower_range: float, upper_range: float, level_spacing: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    buy_levels: list[float] = []
    sell_levels: list[float] = []
    next_level = current_price - level_spacing
    while next_level >= lower_range:
        buy_levels.append(next_level)
        next_level -= level_spacing
    next_level = current_price + level_spacing
    while next_level <= upper_range:
        sell_levels.append(next_level)
        next_level += level_spacing
    return tuple(buy_levels), tuple(sell_levels)