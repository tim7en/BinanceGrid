from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.coordinator import CoordinatorConfig, MarketFrame, PriceBar, RuleBasedGridCoordinator
from binance_grid.strategy import GridTradingBot
from binance_grid.walkforward import build_walk_forward_batches, run_walk_forward_backtest


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


def _make_histories() -> dict[str, MarketFrame]:
    symbols = ("BTC", "SP500", "SOL", "GOLD")
    day_zero = datetime(2024, 1, 1)
    intraday_day = day_zero + timedelta(days=200)
    daily_base = [100.0 + 0.25 * index for index in range(201)]
    intraday_base = [100.0] * 50 + [99.8] * 50 + [100.2 + 0.08 * index for index in range(60)]

    histories: dict[str, MarketFrame] = {}
    for offset, symbol in enumerate(symbols):
        symbol_shift = float(offset) * 3.0
        daily_closes = [value + symbol_shift for value in daily_base]
        intraday_closes = [value + symbol_shift for value in intraday_base]
        histories[symbol] = MarketFrame(
            daily_bars=_bars_from_closes(
                daily_closes,
                start=day_zero,
                step=timedelta(days=1),
                high_pad=1.0,
                low_pad=1.0,
                base_volume=1_000.0,
            ),
            five_minute_bars=_bars_from_closes(
                intraday_closes,
                start=intraday_day,
                step=timedelta(minutes=5),
                high_pad=0.5,
                low_pad=0.5,
                base_volume=100.0,
                boosted_indices=set(range(110, 140)),
                boost_size=500.0,
            ),
        )
    return histories


class WalkForwardTests(unittest.TestCase):
    def test_walk_forward_uses_only_completed_daily_bars(self) -> None:
        histories = _make_histories()
        batches = build_walk_forward_batches(histories, CoordinatorConfig())

        first_batch = batches[0]["BTC"]
        self.assertEqual(len(first_batch.daily_bars), 200)
        self.assertTrue(
            all(bar.timestamp.date() < first_batch.last_timestamp.date() for bar in first_batch.daily_bars)
        )

    def test_future_mutation_does_not_change_earlier_snapshots(self) -> None:
        base_histories = _make_histories()
        mutated_histories = deepcopy(base_histories)

        for symbol, frame in mutated_histories.items():
            updated_bars = list(frame.five_minute_bars)
            for index in range(145, len(updated_bars)):
                bar = updated_bars[index]
                updated_bars[index] = PriceBar(
                    timestamp=bar.timestamp,
                    open=bar.open,
                    high=bar.high + 20.0,
                    low=max(bar.low - 20.0, 1.0),
                    close=bar.close + 15.0,
                    volume=bar.volume + 1_000.0,
                )
            mutated_histories[symbol] = MarketFrame(
                daily_bars=frame.daily_bars,
                five_minute_bars=tuple(updated_bars),
            )

        coordinator_a = RuleBasedGridCoordinator({symbol: GridTradingBot(symbol) for symbol in base_histories}, CoordinatorConfig())
        coordinator_b = RuleBasedGridCoordinator({symbol: GridTradingBot(symbol) for symbol in mutated_histories}, CoordinatorConfig())

        snapshots_a = run_walk_forward_backtest(coordinator_a, base_histories)
        snapshots_b = run_walk_forward_backtest(coordinator_b, mutated_histories)
        comparison_index = 12
        btc_a = snapshots_a[comparison_index].decisions["BTC"]
        btc_b = snapshots_b[comparison_index].decisions["BTC"]

        self.assertEqual(btc_a.regime, btc_b.regime)
        self.assertAlmostEqual(btc_a.bias.fast_ma, btc_b.bias.fast_ma)
        self.assertAlmostEqual(btc_a.crossover.current_fast_ma, btc_b.crossover.current_fast_ma)
        self.assertAlmostEqual(btc_a.atr.atr, btc_b.atr.atr)
        self.assertAlmostEqual(btc_a.reinforcement.net_score, btc_b.reinforcement.net_score)
        self.assertAlmostEqual(snapshots_a[comparison_index].portfolio_equity, snapshots_b[comparison_index].portfolio_equity)


if __name__ == "__main__":
    unittest.main()