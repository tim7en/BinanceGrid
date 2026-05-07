# Binance Grid Research Toolkit

This repository contains a small research stack for regime-aware grid trading.

It includes three core parts:

- a synthetic market generator that creates 10-year, multi-asset price paths with changing volatility and correlation regimes
- a three-state grid bot with `long`, `neutral`, and `short` operating modes
- a portfolio manager that coordinates multiple grid bots and overrides spacing, notional, and inventory limits from portfolio risk

## Market Model

The simulator creates daily price paths for four assets with distinct drift and volatility signatures:

- `BTC`: high drift, high volatility
- `SP500`: lower volatility, positive drift
- `SOL`: high-beta crypto with larger volatility and stronger risk sensitivity
- `GOLD`: lower drift, lower volatility, weaker or negative stress correlation

Each step belongs to one of four macro regimes: `expansion`, `range`, `stress`, or `mania`. The regime controls drift shifts, volatility multipliers, and cross-asset correlation.

## Grid Logic

`GridTradingBot` does not rely on a static ladder. It recomputes the grid every step using:

- directional regime: `long`, `neutral`, or `short`
- realized volatility: widens spacing when the market gets faster
- inventory skew: long mode allows more long inventory and larger dip buys; short mode mirrors that on rallies

That lets the bot remain volatility-seeking while still expressing directional bias.

## Portfolio Control

`AssetGridManager` sits above the individual bots and enforces stronger controls:

- scales inventory limits inversely to realized volatility
- penalizes highly correlated assets when capital is allocated
- widens spacing when correlation or drawdown rises
- can neutralize very high-volatility, highly correlated assets instead of letting every bot lean the same way

## Example

```python
from binance_grid import AssetGridManager, GridTradingBot, simulate_price_paths

market = simulate_price_paths(years=10, steps_per_year=365, seed=21)
bots = {symbol: GridTradingBot(symbol) for symbol in market.asset_symbols}
manager = AssetGridManager(bots)
history = manager.run_simulation(market)

last_snapshot = history[-1]
print(last_snapshot.portfolio_equity)
print(last_snapshot.controls["BTC"])
print(market.timestamps[:3])
print(market.prices[:3])
```

## Test

```powershell
python -m unittest discover -s tests
```
