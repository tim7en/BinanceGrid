from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.signals import CrossoverDirection, detect_moving_average_crossover, determine_daily_bias, resolve_trade_regime
from binance_grid.strategy import GridBias


class SignalTests(unittest.TestCase):
    def test_daily_bias_uses_50_200_and_donchian_location(self) -> None:
        closes = [100.0 + index * 0.4 for index in range(220)]
        highs = [value + 1.0 for value in closes]
        lows = [value - 1.0 for value in closes]

        bias = determine_daily_bias(closes, highs, lows)

        self.assertEqual(bias.regime, GridBias.LONG)
        self.assertEqual(bias.ma_regime, GridBias.LONG)
        self.assertGreater(bias.fast_ma, bias.slow_ma)
        self.assertGreaterEqual(bias.channel_position, 0.5)

    def test_breakout_persists_while_moving_averages_stay_aligned(self) -> None:
        closes = [100.0 + index * 0.3 for index in range(219)] + [170.0, 166.0]
        highs = [value + 1.0 for value in closes]
        lows = [value - 1.0 for value in closes]

        breakout_bias = determine_daily_bias(closes[:-1], highs[:-1], lows[:-1])
        persisted_bias = determine_daily_bias(
            closes,
            highs,
            lows,
            previous_breakout=breakout_bias.breakout_regime,
        )

        self.assertEqual(breakout_bias.breakout_regime, GridBias.LONG)
        self.assertTrue(breakout_bias.breakout_triggered)
        self.assertEqual(persisted_bias.regime, GridBias.LONG)
        self.assertTrue(persisted_bias.breakout_persisted)
        self.assertTrue(persisted_bias.inside_channel)

    def test_fake_breakout_is_counted_when_persistent_break_fails(self) -> None:
        closes = [100.0 + index * 0.3 for index in range(219)] + [170.0, 165.0]
        highs = [value + 1.0 for value in closes]
        lows = [value - 1.0 for value in closes]

        breakout_bias = determine_daily_bias(closes[:-1], highs[:-1], lows[:-1])
        failed_bias = determine_daily_bias(
            closes,
            highs,
            lows,
            previous_breakout=breakout_bias.breakout_regime,
        )

        self.assertEqual(breakout_bias.breakout_regime, GridBias.LONG)
        self.assertTrue(failed_bias.fake_breakout)
        self.assertTrue(failed_bias.inside_channel)

    def test_detect_moving_average_crossover_flags_bullish_cross(self) -> None:
        closes = [100.0] * 50 + [99.9] * 50 + [105.0]

        signal = detect_moving_average_crossover(closes)

        self.assertTrue(signal.crossed)
        self.assertEqual(signal.direction, CrossoverDirection.BULLISH)
        self.assertLessEqual(signal.previous_fast_ma, signal.previous_slow_ma)
        self.assertGreater(signal.current_fast_ma, signal.current_slow_ma)

    def test_regime_resolution_respects_higher_timeframe_bias(self) -> None:
        closes = [100.0 + index * 0.4 for index in range(220)]
        highs = [value + 1.0 for value in closes]
        lows = [value - 1.0 for value in closes]
        bias = determine_daily_bias(closes, highs, lows)
        bullish_cross = detect_moving_average_crossover([100.0] * 50 + [99.9] * 50 + [105.0])
        bearish_cross = detect_moving_average_crossover([100.0] * 50 + [100.1] * 50 + [95.0])

        self.assertEqual(resolve_trade_regime(bias, bullish_cross, GridBias.NEUTRAL), GridBias.LONG)
        self.assertEqual(resolve_trade_regime(bias, bearish_cross, GridBias.LONG), GridBias.NEUTRAL)


if __name__ == "__main__":
    unittest.main()