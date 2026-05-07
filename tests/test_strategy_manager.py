from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid import AssetGridManager, GridBias, GridConfig, GridTradingBot, simulate_price_paths


class StrategyAndManagerTests(unittest.TestCase):
    def test_long_bias_accumulates_more_inventory_than_short_bias(self) -> None:
        config = GridConfig(
            base_spacing_bps=80.0,
            min_spacing_bps=80.0,
            max_spacing_bps=80.0,
            base_order_notional=1_000.0,
            inventory_notional_limit=4_000.0,
        )
        long_bot = GridTradingBot("BTC", config)
        short_bot = GridTradingBot("BTC", config)
        start = datetime(2020, 1, 1)
        prices = [100.0, 99.0, 100.8, 99.1, 101.0, 100.0, 102.0]

        for index, price in enumerate(prices):
            timestamp = start + timedelta(days=index)
            long_snapshot = long_bot.step(timestamp, price, annualized_vol=0.60, regime=GridBias.LONG)
            short_snapshot = short_bot.step(timestamp, price, annualized_vol=0.60, regime=GridBias.SHORT)

        long_control = long_bot.make_control(prices[-1], annualized_vol=0.60, regime=GridBias.LONG)
        short_control = short_bot.make_control(prices[-1], annualized_vol=0.60, regime=GridBias.SHORT)

        self.assertGreater(long_snapshot.inventory, short_snapshot.inventory)
        self.assertGreater(long_control.buy_order_notional, long_control.sell_order_notional)
        self.assertGreater(long_control.long_notional_limit, long_control.short_notional_limit)
        self.assertLess(short_control.buy_order_notional, short_control.sell_order_notional)
        self.assertLess(short_control.long_notional_limit, short_control.short_notional_limit)

    def test_manager_penalizes_high_beta_correlated_assets(self) -> None:
        bots = {
            symbol: GridTradingBot(symbol)
            for symbol in ("BTC", "SP500", "SOL", "GOLD")
        }
        manager = AssetGridManager(bots)
        start = datetime(2020, 1, 1)
        steps = 70
        angles = np.linspace(0.0, 5.0 * np.pi, steps)
        price_map = {
            "BTC": 100.0 + np.linspace(0.0, 18.0, steps) + 8.0 * np.sin(angles),
            "SP500": 100.0 + np.linspace(0.0, 7.0, steps) + 1.8 * np.sin(angles + 0.1),
            "SOL": 100.0 + np.linspace(0.0, 22.0, steps) + 14.0 * np.sin(angles + 0.05),
            "GOLD": 100.0 + np.linspace(0.0, 4.0, steps) - 1.2 * np.sin(angles + 0.2),
        }

        for index in range(steps):
            manager.step(
                start + timedelta(days=index),
                {symbol: float(values[index]) for symbol, values in price_map.items()},
            )

        controls = manager.review_asset_controls()
        self.assertLess(controls["SOL"].inventory_limit_notional, controls["SP500"].inventory_limit_notional)
        self.assertLess(controls["SOL"].order_notional, controls["SP500"].order_notional)
        self.assertLessEqual(
            max(control.weight for control in controls.values()),
            manager.config.max_single_asset_weight + 1e-9,
        )

    def test_manager_runs_on_simulated_market(self) -> None:
        market = simulate_price_paths(years=1, steps_per_year=40, seed=23)
        bots = {symbol: GridTradingBot(symbol) for symbol in market.asset_symbols}
        manager = AssetGridManager(bots)

        snapshots = manager.run_simulation(market)

        self.assertEqual(len(snapshots), len(market.regimes))
        self.assertGreater(snapshots[-1].portfolio_equity, 0.0)
        self.assertTrue(all(snapshot.gross_exposure >= 0.0 for snapshot in snapshots))


if __name__ == "__main__":
    unittest.main()
