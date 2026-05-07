from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid import MacroRegime, simulate_price_paths


class SimulationTests(unittest.TestCase):
    def test_generates_positive_prices_with_timeline(self) -> None:
        result = simulate_price_paths(years=1, steps_per_year=30, seed=11)

        self.assertEqual(result.prices.shape, (31, 4))
        self.assertEqual(len(result.timestamps), 31)
        self.assertEqual(result.asset_symbols, ("BTC", "SP500", "SOL", "GOLD"))
        self.assertTrue(np.all(result.prices > 0.0))

    def test_stress_regime_widens_vol_and_correlation(self) -> None:
        forced_regimes = [MacroRegime.EXPANSION] * 500 + [MacroRegime.STRESS] * 500
        result = simulate_price_paths(
            forced_regimes=forced_regimes,
            steps_per_year=365,
            seed=19,
        )

        btc = result.symbol_index("BTC")
        sol = result.symbol_index("SOL")
        spx = result.symbol_index("SP500")

        expansion_vol = result.annualized_volatility(MacroRegime.EXPANSION)
        stress_vol = result.annualized_volatility(MacroRegime.STRESS)
        expansion_corr = result.realized_correlation(MacroRegime.EXPANSION)
        stress_corr = result.realized_correlation(MacroRegime.STRESS)

        self.assertGreater(stress_vol[btc], expansion_vol[btc])
        self.assertGreater(stress_vol[sol], expansion_vol[sol])
        self.assertGreater(stress_corr[btc, sol], expansion_corr[btc, sol])
        self.assertGreater(result.annualized_volatility()[sol], result.annualized_volatility()[spx])


if __name__ == "__main__":
    unittest.main()
