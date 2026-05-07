from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..bot import SingleAssetBotConfig, SingleAssetBotSnapshot, SingleAssetGridBot, SingleAssetInput


@dataclass(frozen=True)
class PortfolioManagerConfig:
    total_capital: float


@dataclass(frozen=True)
class PortfolioManagerSnapshot:
    total_equity: float
    total_savings: float
    asset_snapshots: dict[str, SingleAssetBotSnapshot]


class PortfolioRiskController:
    def __init__(self, asset_symbols: tuple[str, ...], config: PortfolioManagerConfig) -> None:
        if not asset_symbols:
            raise ValueError("at least one asset symbol is required")
        if config.total_capital <= 0.0:
            raise ValueError("total_capital must be positive")

        per_asset_capital = config.total_capital / len(asset_symbols)
        self.config = config
        self.bots = {
            symbol: SingleAssetGridBot(symbol, SingleAssetBotConfig(allocated_capital=per_asset_capital))
            for symbol in asset_symbols
        }

    def step(self, asset_inputs: Mapping[str, SingleAssetInput]) -> PortfolioManagerSnapshot:
        missing_symbols = set(self.bots).difference(asset_inputs)
        if missing_symbols:
            missing_display = ", ".join(sorted(missing_symbols))
            raise KeyError(f"missing inputs for: {missing_display}")

        snapshots = {
            symbol: bot.step(asset_inputs[symbol])
            for symbol, bot in self.bots.items()
        }
        total_equity = sum(snapshot.total_equity for snapshot in snapshots.values())
        total_savings = sum(snapshot.savings_balance for snapshot in snapshots.values())
        return PortfolioManagerSnapshot(
            total_equity=total_equity,
            total_savings=total_savings,
            asset_snapshots=snapshots,
        )