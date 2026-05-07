from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationConfig:
    starting_balance: float = 100_000.0
    market_count: int = 4
    max_notional_per_market: float = 50_000.0
    max_leverage: float = 3.0
    order_slices_per_side: int = 4


@dataclass(frozen=True)
class MarketAllocation:
    account_balance: float
    margin_budget: float
    leverage_multiplier: float
    target_notional_limit: float
    order_notional: float


def allocate_market_capital(
    config: AllocationConfig,
    *,
    leverage_multiplier: float,
    grid_levels_per_side: int,
    account_balance: float | None = None,
) -> MarketAllocation:
    if config.market_count <= 0:
        raise ValueError("market_count must be positive")
    if grid_levels_per_side <= 0:
        raise ValueError("grid_levels_per_side must be positive")

    effective_balance = config.starting_balance if account_balance is None else account_balance
    margin_budget = effective_balance / config.market_count
    applied_leverage = min(config.max_leverage, max(1.0, leverage_multiplier))
    target_notional_limit = min(config.max_notional_per_market, margin_budget * applied_leverage)
    order_notional = min(
        target_notional_limit / 2.0,
        target_notional_limit / (grid_levels_per_side * config.order_slices_per_side),
    )
    return MarketAllocation(
        account_balance=effective_balance,
        margin_budget=margin_budget,
        leverage_multiplier=applied_leverage,
        target_notional_limit=target_notional_limit,
        order_notional=order_notional,
    )