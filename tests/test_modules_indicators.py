from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.modules.common import MarketBar
from binance_grid.modules.indicators import (
    BreakoutDirection,
    TrendRegime,
    VolumePhase,
    build_indicator_snapshot,
    donchian_breakout_signal,
    moving_average_regime,
    rolling_vwap,
)


def _bars_from_values(closes: list[float], *, start: datetime, step: timedelta, volume: float = 100.0) -> tuple[MarketBar, ...]:
    bars: list[MarketBar] = []
    previous = closes[0]
    for index, close in enumerate(closes):
        bars.append(
            MarketBar(
                timestamp=start + index * step,
                open=previous,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=volume + index,
            )
        )
        previous = close
    return tuple(bars)


class ModuleIndicatorTests(unittest.TestCase):
    def test_rolling_vwap_uses_volume_weights(self) -> None:
        start = datetime(2024, 1, 1)
        bars = (
            MarketBar(start, 100.0, 101.0, 99.0, 100.0, 10.0),
            MarketBar(start + timedelta(minutes=5), 102.0, 103.0, 101.0, 102.0, 30.0),
        )

        value = rolling_vwap(bars)

        self.assertAlmostEqual(value, 101.5)

    def test_moving_average_regime_detects_bull_cross(self) -> None:
        closes = [100.0] * 150 + [90.0] * 50 + [700.0]

        state = moving_average_regime(closes)

        self.assertEqual(state.regime, TrendRegime.BULL)
        self.assertTrue(state.crossed_up)
        self.assertFalse(state.crossed_down)

    def test_donchian_breakout_detects_slow_channel_break(self) -> None:
        start = datetime(2024, 1, 1)
        closes = [100.0 + 0.1 * index for index in range(50)] + [110.0]
        bars = _bars_from_values(closes, start=start, step=timedelta(minutes=5))

        breakout = donchian_breakout_signal(bars, window=50)

        self.assertEqual(breakout, BreakoutDirection.LONG)

    def test_indicator_snapshot_reports_volume_expansion(self) -> None:
        daily_bars = _bars_from_values([100.0 + 0.3 * index for index in range(220)], start=datetime(2024, 1, 1), step=timedelta(days=1))
        intraday = list(_bars_from_values([100.0] * 50 + [99.8] * 149 + [110.0], start=datetime(2024, 9, 1), step=timedelta(minutes=5), volume=100.0))
        for index in range(len(intraday) - 50, len(intraday)):
            bar = intraday[index]
            intraday[index] = MarketBar(bar.timestamp, bar.open, bar.high, bar.low, bar.close, 350.0)

        snapshot = build_indicator_snapshot(daily_bars, tuple(intraday))

        self.assertEqual(snapshot.trend.regime, TrendRegime.BULL)
        self.assertEqual(snapshot.breakout, BreakoutDirection.LONG)
        self.assertEqual(snapshot.volume.phase, VolumePhase.EXPANSION)


if __name__ == "__main__":
    unittest.main()