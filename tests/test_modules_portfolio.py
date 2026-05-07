from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.modules.bot import SingleAssetInput
from binance_grid.modules.common import MarketBar
from binance_grid.modules.portfolio import PortfolioManagerConfig, PortfolioRiskController


def _bars_from_values(closes: list[float], *, start: datetime, step: timedelta, volume: float = 100.0) -> tuple[MarketBar, ...]:
    bars: list[MarketBar] = []
    previous = closes[0]
    for index, close in enumerate(closes):
        bars.append(MarketBar(start + index * step, previous, close + 1.0, close - 1.0, close, volume + index))
        previous = close
    return tuple(bars)


def _asset_input(start: datetime, shift: float) -> SingleAssetInput:
    intraday = list(_bars_from_values([100.0 + shift] * 50 + [99.7 + shift] * 150 + [109.0 + shift], start=start, step=timedelta(minutes=5), volume=100.0))
    for index in range(len(intraday) - 50, len(intraday)):
        bar = intraday[index]
        intraday[index] = MarketBar(bar.timestamp, bar.open, bar.high, bar.low, bar.close, 340.0)
    return SingleAssetInput(
        daily_bars=_bars_from_values([100.0 + shift + 0.35 * index for index in range(220)], start=start - timedelta(days=220), step=timedelta(days=1), volume=1_000.0),
        intraday_bars=tuple(intraday),
        dxy_values=tuple(104.0 - 0.1 * index for index in range(25)),
        spread_10y2y_values=tuple(0.40 for _ in range(25)),
        spread_2y3m_values=tuple(0.20 for _ in range(25)),
        vix_values=tuple(18.0 for _ in range(25)),
        fear_greed_values=tuple(70.0 for _ in range(25)),
    )


class ModulePortfolioTests(unittest.TestCase):
    def test_portfolio_manager_tracks_total_equity_across_assets(self) -> None:
        manager = PortfolioRiskController(("BTC", "SOL"), PortfolioManagerConfig(total_capital=40_000.0))
        snapshot = manager.step(
            {
                "BTC": _asset_input(datetime(2024, 8, 1), 0.0),
                "SOL": _asset_input(datetime(2024, 8, 1), 20.0),
            }
        )

        self.assertEqual(set(snapshot.asset_snapshots), {"BTC", "SOL"})
        self.assertGreater(snapshot.total_equity, 0.0)
        self.assertAlmostEqual(
            snapshot.total_equity,
            sum(asset_snapshot.total_equity for asset_snapshot in snapshot.asset_snapshots.values()),
        )


if __name__ == "__main__":
    unittest.main()