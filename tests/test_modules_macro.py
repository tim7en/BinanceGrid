from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.modules.macro_regime import MacroRiskRegime, assess_macro_regime


class ModuleMacroTests(unittest.TestCase):
    def test_macro_regime_identifies_risk_on(self) -> None:
        state = assess_macro_regime(
            dxy_values=[105.0 - 0.1 * index for index in range(25)],
            spread_10y2y_values=[0.40] * 25,
            spread_2y3m_values=[0.20] * 25,
            vix_values=[18.0] * 25,
            fear_greed_values=[72.0] * 25,
        )

        self.assertEqual(state.regime, MacroRiskRegime.RISK_ON)
        self.assertGreater(state.score, 0.0)
        self.assertEqual(state.leverage_cap, 5.0)

    def test_macro_regime_identifies_risk_off(self) -> None:
        state = assess_macro_regime(
            dxy_values=[100.0 + 0.2 * index for index in range(25)],
            spread_10y2y_values=[-0.30] * 25,
            spread_2y3m_values=[-0.15] * 25,
            vix_values=[32.0] * 25,
            fear_greed_values=[25.0] * 25,
        )

        self.assertEqual(state.regime, MacroRiskRegime.RISK_OFF)
        self.assertLess(state.score, 0.0)
        self.assertEqual(state.leverage_cap, 2.0)


if __name__ == "__main__":
    unittest.main()