from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.indicators import average_true_range, donchian_channel, simple_moving_average, volume_confirmation


class IndicatorTests(unittest.TestCase):
    def test_simple_moving_average_uses_tail_window(self) -> None:
        value = simple_moving_average([1.0, 2.0, 3.0, 10.0, 11.0], window=3)

        self.assertAlmostEqual(value, 8.0)

    def test_donchian_channel_tracks_upper_and_lower_bounds(self) -> None:
        channel = donchian_channel(
            highs=[100.0, 102.0, 106.0, 104.0],
            lows=[95.0, 97.0, 98.0, 96.0],
            window=3,
        )

        self.assertEqual(channel.upper, 106.0)
        self.assertEqual(channel.lower, 96.0)
        self.assertEqual(channel.middle, 101.0)
        self.assertEqual(channel.width, 10.0)

    def test_average_true_range_returns_absolute_and_relative_values(self) -> None:
        metrics = average_true_range(
            highs=[10.0, 11.0, 13.0, 14.0, 16.0],
            lows=[9.0, 9.5, 10.0, 11.0, 13.0],
            closes=[9.5, 10.5, 12.0, 13.0, 15.0],
            window=3,
        )

        self.assertAlmostEqual(metrics.atr, 3.0)
        self.assertAlmostEqual(metrics.atr_pct, 3.0 / 15.0)

    def test_volume_confirmation_scales_leverage_up_to_cap(self) -> None:
        volumes = [100.0] * 40 + [180.0] * 10
        signal = volume_confirmation(volumes, fast_window=10, slow_window=50, leverage_cap=3.0, confirmation_threshold=1.2)

        self.assertTrue(signal.confirmed)
        self.assertGreater(signal.ratio, 1.2)
        self.assertGreater(signal.leverage_multiplier, 1.0)
        self.assertLessEqual(signal.leverage_multiplier, 3.0)


if __name__ == "__main__":
    unittest.main()