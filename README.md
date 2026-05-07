# Binance Grid Research Toolkit

This repository contains a small research stack for regime-aware grid trading.

It includes three core parts:

- a synthetic market generator that creates 10-year, multi-asset price paths with changing volatility and correlation regimes
- a three-state grid bot with `long`, `neutral`, and `short` operating modes
- a portfolio manager that coordinates multiple grid bots and overrides spacing, notional, and inventory limits from portfolio risk

## Foldered Architecture

The project now also exposes a foldered module layout for the workflow you described:

- `binance_grid/modules/indicators`: VWAP, 50d/200d trend regime, 5m Donchian 50 and 10, 5m volume 200/50 expansion-compression
- `binance_grid/modules/macro_regime`: DXY, curve, VIX, and crypto fear-greed scoring into a macro risk state
- `binance_grid/modules/risk_control`: ATR-sized grid ranges, 30% initial deployment, 70% reserve, grid count from 200-bar volatility, leverage from x2 to x5
- `binance_grid/modules/bot`: one-asset grid bot with daily 30/70 profit split, macro-change flatten and pause, and 50% loss pause for 10 days
- `binance_grid/modules/portfolio`: multi-asset manager that supervises multiple one-asset bots and tracks portfolio equity

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

## Plotting

The package includes a headless plotting module that saves PNG files for the synthetic market and the managed portfolio.

```powershell
python -m binance_grid.plotting --output-dir artifacts/plots
```

That command writes:

- `artifacts/plots/market_overview.png`
- `artifacts/plots/portfolio_overview.png`
- `artifacts/plots/walkforward_dashboard.png`

The walk-forward dashboard adds the execution analytics for the reinforced rule engine:

- equity curve and drawdown
- gross exposure
- active grids and grid crossings
- fill counts and cumulative fill rate
- aligned Donchian breakouts and fake breakouts

## Generated Backtest

You can run the full reinforced walk-forward setup on generated market data and track returns explicitly.

```powershell
python -m binance_grid.generated --years 3 --intraday-bars-per-day 24 --output-dir artifacts/generated
```

That command writes:

- `artifacts/generated/generated_market_overview.png`
- `artifacts/generated/generated_walkforward_dashboard.png`
- `artifacts/generated/generated_returns_summary.txt`

## Test

```powershell
python -m unittest discover -s tests
```
