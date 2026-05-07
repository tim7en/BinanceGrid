from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.coordinator import CoordinatorConfig, MarketFrame, PriceBar, RuleBasedGridCoordinator
from binance_grid.strategy import GridBias, GridTradingBot


def _bars_from_closes(
    closes: list[float],
    *,
    start: datetime,
    step: timedelta,
    high_pad: float = 1.0,
    low_pad: float = 1.0,
    base_volume: float = 100.0,
    last_volume_boost: float = 0.0,
) -> tuple[PriceBar, ...]:
    bars: list[PriceBar] = []
    previous = closes[0]
    for index, close in enumerate(closes):
        volume = base_volume + (last_volume_boost if index >= len(closes) - 20 else 0.0)
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


class CoordinatorTests(unittest.TestCase):
    def test_coordinator_applies_bias_crossover_volume_and_atr_controls(self) -> None:
        symbols = ("BTC", "SP500", "SOL", "GOLD")
        bots = {symbol: GridTradingBot(symbol) for symbol in symbols}
        coordinator = RuleBasedGridCoordinator(bots, CoordinatorConfig())
        start = datetime(2024, 1, 1)

        daily_closes = [100.0 + index * 0.4 for index in range(220)]
        intraday_closes = [100.0] * 50 + [99.9] * 50 + [105.0]
        frames = {
            symbol: MarketFrame(
                daily_bars=_bars_from_closes(daily_closes, start=start, step=timedelta(days=1)),
                five_minute_bars=_bars_from_closes(
                    intraday_closes,
                    start=start,
                    step=timedelta(minutes=5),
                    high_pad=0.6,
                    low_pad=0.6,
                    base_volume=100.0,
                    last_volume_boost=600.0,
                ),
            )
            for symbol in symbols
        }

        snapshot = coordinator.step(frames)
        btc = snapshot.decisions["BTC"]
        btc_bot = bots["BTC"]
        expected_spacing = min(
            btc_bot.config.max_spacing_bps / 10_000.0,
            max(btc_bot.config.min_spacing_bps / 10_000.0, btc.atr.atr_pct / btc_bot.config.levels_per_side),
        )

        self.assertEqual(len(snapshot.decisions), 4)
        self.assertEqual(btc.bias.regime, GridBias.LONG)
        self.assertEqual(btc.regime, GridBias.LONG)
        self.assertTrue(btc.volume.confirmed)
        self.assertEqual(btc.allocation.account_balance, 100_000.0)
        self.assertEqual(btc.allocation.margin_budget, 25_000.0)
        self.assertEqual(btc.allocation.target_notional_limit, 50_000.0)
        self.assertGreater(btc.atr.atr_pct, 0.0)
        self.assertAlmostEqual(btc.grid_spacing_pct, expected_spacing)
        self.assertAlmostEqual(btc.bot_snapshot.spacing_pct, expected_spacing)
        self.assertLessEqual(btc.allocation.target_notional_limit, 50_000.0)
        self.assertGreater(snapshot.portfolio_equity, 0.0)

    def test_breakout_persistence_keeps_long_until_aligned_short_reversal(self) -> None:
        bot = GridTradingBot("BTC")
        coordinator = RuleBasedGridCoordinator({"BTC": bot}, CoordinatorConfig())
        start = datetime(2024, 1, 1)

        long_breakout_daily = [100.0 + index * 0.3 for index in range(219)] + [170.0]
        fake_reentry_daily = long_breakout_daily + [165.0]
        short_reversal_daily = [200.0 - index * 0.25 for index in range(220)] + [120.0]

        bullish_intraday = [100.0] * 50 + [99.9] * 50 + [105.0]
        neutral_intraday = [105.0] * 101
        bearish_intraday = [105.0] * 50 + [105.2] * 50 + [98.0]

        long_snapshot = coordinator.step(
            {
                "BTC": MarketFrame(
                    daily_bars=_bars_from_closes(long_breakout_daily, start=start, step=timedelta(days=1)),
                    five_minute_bars=_bars_from_closes(
                        bullish_intraday,
                        start=start + timedelta(days=220),
                        step=timedelta(minutes=5),
                        high_pad=0.6,
                        low_pad=0.6,
                        base_volume=100.0,
                        last_volume_boost=600.0,
                    ),
                )
            }
        )
        reentry_snapshot = coordinator.step(
            {
                "BTC": MarketFrame(
                    daily_bars=_bars_from_closes(fake_reentry_daily, start=start, step=timedelta(days=1)),
                    five_minute_bars=_bars_from_closes(
                        neutral_intraday,
                        start=start + timedelta(days=221),
                        step=timedelta(minutes=5),
                        high_pad=0.6,
                        low_pad=0.6,
                        base_volume=100.0,
                    ),
                )
            }
        )
        short_snapshot = coordinator.step(
            {
                "BTC": MarketFrame(
                    daily_bars=_bars_from_closes(short_reversal_daily, start=start, step=timedelta(days=1)),
                    five_minute_bars=_bars_from_closes(
                        bearish_intraday,
                        start=start + timedelta(days=260),
                        step=timedelta(minutes=5),
                        high_pad=0.6,
                        low_pad=0.6,
                        base_volume=100.0,
                        last_volume_boost=600.0,
                    ),
                )
            }
        )

        decision_long = long_snapshot.decisions["BTC"]
        decision_reentry = reentry_snapshot.decisions["BTC"]
        decision_short = short_snapshot.decisions["BTC"]

        self.assertEqual(decision_long.active_breakout, GridBias.LONG)
        self.assertEqual(decision_long.regime, GridBias.LONG)
        self.assertTrue(decision_long.bias.breakout_triggered)

        self.assertEqual(decision_reentry.active_breakout, GridBias.LONG)
        self.assertEqual(decision_reentry.regime, GridBias.LONG)
        self.assertTrue(decision_reentry.bias.fake_breakout)
        self.assertTrue(decision_reentry.fake_breakout_triggered)
        self.assertEqual(decision_reentry.cumulative_fake_breakouts, 1)

        self.assertEqual(decision_short.active_breakout, GridBias.SHORT)
        self.assertEqual(decision_short.regime, GridBias.SHORT)
        self.assertTrue(decision_short.bias.breakout_triggered)


if __name__ == "__main__":
    unittest.main()