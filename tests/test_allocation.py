from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.allocation import AllocationConfig, allocate_market_capital


class AllocationTests(unittest.TestCase):
    def test_allocation_starts_from_100k_and_four_markets(self) -> None:
        allocation = allocate_market_capital(
            AllocationConfig(),
            leverage_multiplier=1.0,
            grid_levels_per_side=6,
        )

        self.assertEqual(allocation.account_balance, 100_000.0)
        self.assertEqual(allocation.margin_budget, 25_000.0)
        self.assertEqual(allocation.target_notional_limit, 25_000.0)
        self.assertAlmostEqual(allocation.order_notional, 25_000.0 / 24.0)

    def test_allocation_respects_50k_market_cap_even_with_higher_leverage(self) -> None:
        allocation = allocate_market_capital(
            AllocationConfig(),
            leverage_multiplier=3.0,
            grid_levels_per_side=5,
        )

        self.assertEqual(allocation.leverage_multiplier, 3.0)
        self.assertEqual(allocation.target_notional_limit, 50_000.0)
        self.assertAlmostEqual(allocation.order_notional, 50_000.0 / 20.0)


if __name__ == "__main__":
    unittest.main()