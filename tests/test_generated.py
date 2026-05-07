from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.generated import build_generated_histories, build_generated_macro_history, run_generated_backtest
from binance_grid.simulation import simulate_price_paths


class GeneratedBacktestTests(unittest.TestCase):
    def test_generated_histories_expand_daily_simulation_into_intraday_frames(self) -> None:
        simulation = simulate_price_paths(years=1, steps_per_year=365, seed=17)

        histories = build_generated_histories(simulation, intraday_bars_per_day=8, seed=31)

        self.assertEqual(set(histories), set(simulation.asset_symbols))
        btc = histories[simulation.asset_symbols[0]]
        self.assertEqual(len(btc.daily_bars), len(simulation.regimes))
        self.assertEqual(len(btc.intraday_bars), len(simulation.regimes) * 8)
        self.assertGreater(btc.intraday_bars[-1].timestamp, btc.intraday_bars[0].timestamp)

    def test_generated_macro_history_matches_daily_horizon(self) -> None:
        simulation = simulate_price_paths(years=1, steps_per_year=365, seed=17)

        macro_history = build_generated_macro_history(simulation, seed=41)

        self.assertEqual(len(macro_history.dxy_values), len(simulation.regimes))
        self.assertEqual(len(macro_history.vix_values), len(simulation.regimes))
        self.assertTrue(all(0.0 <= value <= 100.0 for value in macro_history.fear_greed_values))

    def test_generated_backtest_returns_are_tracked(self) -> None:
        result = run_generated_backtest(
            years=1,
            seed=19,
            intraday_seed=23,
            intraday_bars_per_day=8,
            output_dir=None,
        )

        self.assertGreater(len(result.snapshots), 0)
        self.assertEqual(len(result.analytics.timestamps), len(result.snapshots))
        self.assertAlmostEqual(
            result.analytics.total_return,
            (result.analytics.equity_curve[-1] / result.analytics.equity_curve[0]) - 1.0,
        )
        self.assertTrue(result.analytics.annualized_return == result.analytics.annualized_return)
        self.assertLessEqual(result.analytics.max_drawdown, 0.0)


if __name__ == "__main__":
    unittest.main()