from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.modules.bot import SingleAssetInput
from binance_grid.modules.common import MarketBar
from binance_grid.modules.portfolio import (
    AssetHistory,
    MacroHistory,
    PortfolioManagerConfig,
    PortfolioRiskController,
    run_walk_forward_backtest,
    summarize_walkforward_snapshots,
)


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


def _asset_history(start: datetime, shift: float) -> AssetHistory:
    current_day = start + timedelta(days=220)
    daily_bars = _bars_from_values(
        [100.0 + shift + 0.35 * index for index in range(220)] + [180.0 + shift],
        start=start,
        step=timedelta(days=1),
        volume=1_000.0,
    )
    intraday_bars = _bars_from_values(
        [140.0 + shift] * 80 + [139.6 + shift] * 121 + [149.0 + shift] * 40,
        start=current_day,
        step=timedelta(minutes=5),
        volume=120.0,
    )
    return AssetHistory(daily_bars=daily_bars, intraday_bars=intraday_bars)


def _macro_history(length: int) -> MacroHistory:
    return MacroHistory(
        dxy_values=tuple(103.0 - 0.03 * index for index in range(length)),
        spread_10y2y_values=tuple(0.45 for _ in range(length)),
        spread_2y3m_values=tuple(0.20 for _ in range(length)),
        vix_values=tuple(18.0 for _ in range(length)),
        fear_greed_values=tuple(68.0 for _ in range(length)),
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

    def test_walkforward_ignores_same_day_daily_bar_and_future_intraday_path(self) -> None:
        start = datetime(2024, 1, 1)
        histories = {"BTC": _asset_history(start, 0.0)}
        macro_history = _macro_history(len(histories["BTC"].daily_bars))

        baseline = run_walk_forward_backtest(
            PortfolioRiskController(("BTC",), PortfolioManagerConfig(total_capital=20_000.0)),
            histories,
            macro_history,
        )

        mutated_daily = list(histories["BTC"].daily_bars)
        same_day_bar = mutated_daily[-1]
        mutated_daily[-1] = MarketBar(
            same_day_bar.timestamp,
            same_day_bar.open,
            same_day_bar.high * 10.0,
            same_day_bar.low * 0.1,
            same_day_bar.close * 10.0,
            same_day_bar.volume,
        )
        mutated_intraday = list(histories["BTC"].intraday_bars)
        for index in range(205, len(mutated_intraday)):
            bar = mutated_intraday[index]
            mutated_intraday[index] = MarketBar(
                bar.timestamp,
                bar.open,
                bar.high * 2.0,
                bar.low * 0.5,
                bar.close * 1.8,
                bar.volume,
            )
        mutated_histories = {
            "BTC": AssetHistory(
                daily_bars=tuple(mutated_daily),
                intraday_bars=tuple(mutated_intraday),
            )
        }

        mutated = run_walk_forward_backtest(
            PortfolioRiskController(("BTC",), PortfolioManagerConfig(total_capital=20_000.0)),
            mutated_histories,
            macro_history,
        )

        self.assertGreater(len(baseline), 0)
        self.assertEqual(baseline[0].timestamp, mutated[0].timestamp)
        self.assertAlmostEqual(baseline[0].total_equity, mutated[0].total_equity)

        analytics = summarize_walkforward_snapshots(baseline)
        self.assertEqual(len(analytics.timestamps), len(baseline))
        self.assertLessEqual(analytics.max_drawdown, 0.0)


if __name__ == "__main__":
    unittest.main()