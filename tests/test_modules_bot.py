from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binance_grid.modules.bot import BotStatus, SingleAssetBotConfig, SingleAssetGridBot, SingleAssetInput
from binance_grid.modules.common import MarketBar


def _bars_from_values(
    closes: list[float],
    *,
    start: datetime,
    step: timedelta,
    volume: float = 100.0,
) -> tuple[MarketBar, ...]:
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


def _market_input(*, day_start: datetime, daily_closes: list[float], intraday_closes: list[float], fear_greed: float = 70.0, dxy_start: float = 104.0) -> SingleAssetInput:
    intraday = list(_bars_from_values(intraday_closes, start=day_start, step=timedelta(minutes=5), volume=100.0))
    for index in range(len(intraday) - min(50, len(intraday)), len(intraday)):
        bar = intraday[index]
        intraday[index] = MarketBar(bar.timestamp, bar.open, bar.high, bar.low, bar.close, 350.0)
    return SingleAssetInput(
        daily_bars=_bars_from_values(daily_closes, start=day_start - timedelta(days=len(daily_closes)), step=timedelta(days=1), volume=1_000.0),
        intraday_bars=tuple(intraday),
        dxy_values=tuple(dxy_start - 0.1 * index for index in range(25)),
        spread_10y2y_values=tuple(0.40 for _ in range(25)),
        spread_2y3m_values=tuple(0.20 for _ in range(25)),
        vix_values=tuple(18.0 for _ in range(25)),
        fear_greed_values=tuple(fear_greed for _ in range(25)),
    )


class ModuleBotTests(unittest.TestCase):
    def test_bot_transfers_daily_profits_to_savings_and_compounding(self) -> None:
        bot = SingleAssetGridBot("BTC", SingleAssetBotConfig(allocated_capital=10_000.0))
        daily_closes = [100.0 + 0.35 * index for index in range(220)]

        day_one = _market_input(
            day_start=datetime(2024, 8, 1),
            daily_closes=daily_closes,
            intraday_closes=[100.0] * 50 + [99.7] * 150 + [109.0],
        )
        day_two = _market_input(
            day_start=datetime(2024, 8, 2),
            daily_closes=daily_closes + [110.0],
            intraday_closes=[109.0] * 120 + [120.0] * 81,
        )
        day_three = _market_input(
            day_start=datetime(2024, 8, 3),
            daily_closes=daily_closes + [111.0, 112.0],
            intraday_closes=[120.0] * 201,
        )

        bot.step(day_one)
        day_two_snapshot = bot.step(day_two)
        day_three_snapshot = bot.step(day_three)

        self.assertEqual(day_two_snapshot.status, BotStatus.ACTIVE)
        self.assertGreater(day_three_snapshot.savings_balance, 0.0)
        self.assertGreater(day_three_snapshot.working_capital, 10_000.0)

    def test_bot_pauses_and_flattens_on_macro_regime_change(self) -> None:
        bot = SingleAssetGridBot("BTC", SingleAssetBotConfig(allocated_capital=10_000.0))
        daily_closes = [100.0 + 0.35 * index for index in range(220)]
        active_input = _market_input(
            day_start=datetime(2024, 8, 1),
            daily_closes=daily_closes,
            intraday_closes=[100.0] * 50 + [99.7] * 150 + [109.0],
        )
        risk_off_input = SingleAssetInput(
            daily_bars=active_input.daily_bars,
            intraday_bars=active_input.intraday_bars,
            dxy_values=tuple(100.0 + 0.2 * index for index in range(25)),
            spread_10y2y_values=tuple(-0.30 for _ in range(25)),
            spread_2y3m_values=tuple(-0.15 for _ in range(25)),
            vix_values=tuple(32.0 for _ in range(25)),
            fear_greed_values=tuple(25.0 for _ in range(25)),
        )

        bot.step(active_input)
        paused_snapshot = bot.step(risk_off_input)

        self.assertEqual(paused_snapshot.status, BotStatus.PAUSED)
        self.assertEqual(paused_snapshot.reason, "macro_change")
        self.assertAlmostEqual(paused_snapshot.inventory, 0.0)

    def test_bot_pauses_for_ten_days_after_fifty_percent_loss(self) -> None:
        bot = SingleAssetGridBot("BTC", SingleAssetBotConfig(allocated_capital=10_000.0))
        daily_closes = [100.0 + 0.35 * index for index in range(220)]
        active_input = _market_input(
            day_start=datetime(2024, 8, 1),
            daily_closes=daily_closes,
            intraday_closes=[100.0] * 50 + [99.7] * 150 + [109.0],
        )
        loss_input = _market_input(
            day_start=datetime(2024, 8, 2),
            daily_closes=daily_closes + [50.0],
            intraday_closes=[45.0] * 201,
        )

        bot.step(active_input)
        paused_snapshot = bot.step(loss_input)

        self.assertEqual(paused_snapshot.status, BotStatus.PAUSED)
        self.assertEqual(paused_snapshot.reason, "loss_pause")
        self.assertIsNotNone(paused_snapshot.pause_until)


if __name__ == "__main__":
    unittest.main()