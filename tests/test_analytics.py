from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.analytics import summarize_walkforward_snapshots
from binance_grid.coordinator import CoordinatorConfig, MarketFrame, PriceBar, RuleBasedGridCoordinator
from binance_grid.strategy import GridTradingBot
from binance_grid.walkforward import run_walk_forward_backtest


def _bars_from_closes(
    closes: list[float],
    *,
    start: datetime,
    step: timedelta,
    high_pad: float,
    low_pad: float,
    base_volume: float,
    boosted_indices: set[int] | None = None,
    boost_size: float = 0.0,
) -> tuple[PriceBar, ...]:
    boosted_indices = boosted_indices or set()
    previous = closes[0]
    bars: list[PriceBar] = []
    for index, close in enumerate(closes):
        volume = base_volume + (boost_size if index in boosted_indices else 0.0)
        bars.append(
            PriceBar(
                timestamp=start + step * index,
                open=previous,
                high=close + high_pad,
                low=close - low_pad,
                close=close,
                volume=volume,
            )
        )
        previous = close
    return tuple(bars)


class AnalyticsTests(unittest.TestCase):
    def test_walkforward_analytics_capture_grids_fills_and_fake_breakouts(self) -> None:
        start = datetime(2024, 1, 1)
        intraday_start = start + timedelta(days=220)
        symbols = ("BTC", "SP500", "SOL", "GOLD")
        histories = {}
        for offset, symbol in enumerate(symbols):
            shift = float(offset) * 4.0
            daily_closes = [100.0 + shift + 0.28 * index for index in range(221)]
            intraday_closes = [100.0 + shift] * 50 + [99.6 + shift] * 50 + [101.0 + shift + ((-0.9) if index % 2 else 0.9) + 0.05 * index for index in range(90)]
            histories[symbol] = MarketFrame(
                daily_bars=_bars_from_closes(
                    daily_closes,
                    start=start,
                    step=timedelta(days=1),
                    high_pad=1.2,
                    low_pad=1.2,
                    base_volume=1_200.0,
                ),
                five_minute_bars=_bars_from_closes(
                    intraday_closes,
                    start=intraday_start,
                    step=timedelta(minutes=5),
                    high_pad=0.8,
                    low_pad=0.8,
                    base_volume=120.0,
                    boosted_indices=set(range(120, 190)),
                    boost_size=900.0,
                ),
            )

        coordinator = RuleBasedGridCoordinator(
            {symbol: GridTradingBot(symbol) for symbol in histories},
            CoordinatorConfig(),
        )
        snapshots = run_walk_forward_backtest(coordinator, histories)
        analytics = summarize_walkforward_snapshots(snapshots)

        self.assertEqual(len(analytics.timestamps), len(snapshots))
        self.assertGreater(analytics.active_grids[-1], 0.0)
        self.assertGreater(analytics.cumulative_grid_crosses[-1], 0.0)
        self.assertGreater(analytics.cumulative_fills[-1], 0.0)
        self.assertLessEqual(analytics.cumulative_fill_rate[-1], 1.0)
        self.assertGreaterEqual(analytics.cumulative_breakouts[-1], analytics.cumulative_fake_breakouts[-1])
        self.assertLessEqual(analytics.max_drawdown, 0.0)
        self.assertAlmostEqual(analytics.total_return, analytics.cumulative_returns[-1])
        self.assertEqual(analytics.step_returns.shape, analytics.equity_curve.shape)


if __name__ == "__main__":
    unittest.main()