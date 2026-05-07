from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.modules.common import MarketBar
from binance_grid.modules.indicators import VolumePhase, build_indicator_snapshot
from binance_grid.modules.macro_regime import MacroRiskRegime, assess_macro_regime
from binance_grid.modules.risk_control import build_grid_risk_plan


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


class ModuleRiskTests(unittest.TestCase):
    def test_grid_risk_plan_uses_atr_and_thirty_percent_initial_deployment(self) -> None:
        daily_bars = _bars_from_values(
            [100.0 + 0.35 * index for index in range(220)],
            start=datetime(2024, 1, 1),
            step=timedelta(days=1),
        )
        intraday = list(
            _bars_from_values(
                [100.0] * 50 + [99.7] * 150 + [109.0],
                start=datetime(2024, 9, 1),
                step=timedelta(minutes=5),
                volume=100.0,
            )
        )
        for index in range(len(intraday) - 50, len(intraday)):
            bar = intraday[index]
            intraday[index] = MarketBar(bar.timestamp, bar.open, bar.high, bar.low, bar.close, 360.0)

        snapshot = build_indicator_snapshot(daily_bars, tuple(intraday))
        macro_state = assess_macro_regime(
            dxy_values=[104.0 - 0.1 * index for index in range(25)],
            spread_10y2y_values=[0.40] * 25,
            spread_2y3m_values=[0.20] * 25,
            vix_values=[18.0] * 25,
            fear_greed_values=[70.0] * 25,
        )

        plan = build_grid_risk_plan(snapshot, tuple(intraday), macro_state, allocated_capital=10_000.0)

        self.assertEqual(snapshot.volume.phase, VolumePhase.EXPANSION)
        self.assertEqual(macro_state.regime, MacroRiskRegime.RISK_ON)
        self.assertGreater(plan.atr, 0.0)
        self.assertGreater(plan.realized_volatility_200, 0.0)
        self.assertTrue(2.0 <= plan.leverage <= 5.0)
        self.assertAlmostEqual(plan.initial_entry_notional, plan.total_grid_notional * 0.30)
        self.assertAlmostEqual(plan.reserve_notional, plan.total_grid_notional * 0.70)
        self.assertGreaterEqual(plan.current_price, plan.lower_range)
        self.assertLessEqual(plan.current_price, plan.upper_range)
        self.assertGreater(len(plan.buy_levels), 0)
        self.assertGreater(len(plan.sell_levels), 0)


if __name__ == "__main__":
    unittest.main()