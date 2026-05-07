from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.indicators import DonchianChannel, VolumeSignal
from binance_grid.reinforcement import compute_reinforcement
from binance_grid.signals import CrossoverDirection, CrossoverSignal, TrendBias
from binance_grid.strategy import GridBias


def _trend_bias(
    *,
    regime: GridBias,
    ma_regime: GridBias,
    breakout_regime: GridBias,
    breakout_triggered: bool,
    breakout_persisted: bool,
    fake_breakout: bool,
    channel_position: float,
) -> TrendBias:
    return TrendBias(
        regime=regime,
        ma_regime=ma_regime,
        fast_ma=220.0,
        slow_ma=200.0,
        donchian=DonchianChannel(upper=225.0, middle=212.5, lower=200.0, width=25.0),
        channel_position=channel_position,
        breakout_regime=breakout_regime,
        breakout_triggered=breakout_triggered,
        breakout_persisted=breakout_persisted,
        fake_breakout=fake_breakout,
        inside_channel=not breakout_triggered,
    )


class ReinforcementTests(unittest.TestCase):
    def test_reinforcement_requires_alignment_across_variables(self) -> None:
        bias = _trend_bias(
            regime=GridBias.LONG,
            ma_regime=GridBias.LONG,
            breakout_regime=GridBias.LONG,
            breakout_triggered=True,
            breakout_persisted=False,
            fake_breakout=False,
            channel_position=0.88,
        )
        crossover = CrossoverSignal(
            direction=CrossoverDirection.BULLISH,
            crossed=True,
            previous_fast_ma=199.0,
            previous_slow_ma=200.0,
            current_fast_ma=201.0,
            current_slow_ma=200.0,
        )
        volume = VolumeSignal(ratio=1.8, confirmed=True, leverage_multiplier=1.8)

        reinforcement = compute_reinforcement(
            bias,
            crossover,
            volume,
            previous_regime=GridBias.NEUTRAL,
            active_breakout=GridBias.LONG,
        )

        self.assertEqual(reinforcement.regime, GridBias.LONG)
        self.assertGreater(reinforcement.long_score, reinforcement.short_score)
        self.assertGreater(reinforcement.net_score, 0.0)
        self.assertGreater(reinforcement.applied_leverage, 1.0)

    def test_reinforcement_keeps_long_after_fake_breakout_reentry(self) -> None:
        bias = _trend_bias(
            regime=GridBias.LONG,
            ma_regime=GridBias.LONG,
            breakout_regime=GridBias.LONG,
            breakout_triggered=False,
            breakout_persisted=True,
            fake_breakout=True,
            channel_position=0.46,
        )
        crossover = CrossoverSignal(
            direction=CrossoverDirection.NONE,
            crossed=False,
            previous_fast_ma=201.0,
            previous_slow_ma=200.0,
            current_fast_ma=200.9,
            current_slow_ma=200.0,
        )
        volume = VolumeSignal(ratio=1.0, confirmed=False, leverage_multiplier=1.0)

        reinforcement = compute_reinforcement(
            bias,
            crossover,
            volume,
            previous_regime=GridBias.LONG,
            active_breakout=GridBias.LONG,
        )

        self.assertEqual(reinforcement.regime, GridBias.LONG)
        self.assertEqual(reinforcement.applied_leverage, 1.0)

    def test_reinforcement_flips_short_on_aligned_short_breakout(self) -> None:
        bias = _trend_bias(
            regime=GridBias.SHORT,
            ma_regime=GridBias.SHORT,
            breakout_regime=GridBias.SHORT,
            breakout_triggered=True,
            breakout_persisted=False,
            fake_breakout=False,
            channel_position=0.12,
        )
        crossover = CrossoverSignal(
            direction=CrossoverDirection.BEARISH,
            crossed=True,
            previous_fast_ma=201.0,
            previous_slow_ma=200.0,
            current_fast_ma=199.0,
            current_slow_ma=200.0,
        )
        volume = VolumeSignal(ratio=1.0, confirmed=False, leverage_multiplier=1.0)

        reinforcement = compute_reinforcement(
            bias,
            crossover,
            volume,
            previous_regime=GridBias.LONG,
            active_breakout=GridBias.SHORT,
        )

        self.assertEqual(reinforcement.regime, GridBias.SHORT)
        self.assertLess(reinforcement.net_score, 0.0)


if __name__ == "__main__":
    unittest.main()