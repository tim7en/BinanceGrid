from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import math
from typing import Sequence

import numpy as np


class MacroRegime(StrEnum):
    EXPANSION = "expansion"
    RANGE = "range"
    STRESS = "stress"
    MANIA = "mania"


@dataclass(frozen=True)
class AssetProfile:
    symbol: str
    start_price: float
    annual_drift: float
    annual_vol: float
    risk_exposure: float
    vol_sensitivity: float


@dataclass(frozen=True)
class RegimeSpec:
    regime: MacroRegime
    annual_drift_shift: float
    risk_premium_shift: float
    vol_multiplier: float
    beta_vol_boost: float
    correlation: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class MarketConfiguration:
    assets: tuple[AssetProfile, ...]
    regimes: tuple[RegimeSpec, ...]
    transition_matrix: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class SimulationResult:
    timestamps: tuple[datetime, ...]
    asset_symbols: tuple[str, ...]
    prices: np.ndarray
    log_returns: np.ndarray
    regimes: tuple[MacroRegime, ...]
    steps_per_year: int

    def symbol_index(self, symbol: str) -> int:
        return self.asset_symbols.index(symbol)

    def series(self, symbol: str) -> np.ndarray:
        return self.prices[:, self.symbol_index(symbol)].copy()

    def annualized_volatility(self, regime: MacroRegime | None = None) -> np.ndarray:
        data = self._slice_returns(regime)
        if len(data) < 2:
            return np.zeros(len(self.asset_symbols), dtype=float)
        return data.std(axis=0, ddof=1) * math.sqrt(self.steps_per_year)

    def realized_correlation(self, regime: MacroRegime | None = None) -> np.ndarray:
        data = self._slice_returns(regime)
        if len(data) < 2:
            return np.eye(len(self.asset_symbols), dtype=float)
        return np.corrcoef(data, rowvar=False)

    def _slice_returns(self, regime: MacroRegime | None) -> np.ndarray:
        if regime is None:
            return self.log_returns
        mask = np.array([active_regime == regime for active_regime in self.regimes], dtype=bool)
        return self.log_returns[mask]


def default_market_configuration() -> MarketConfiguration:
    assets = (
        AssetProfile("BTC", 30_000.0, 0.22, 0.72, 1.40, 1.10),
        AssetProfile("SP500", 4_000.0, 0.08, 0.18, 0.90, 0.25),
        AssetProfile("SOL", 35.0, 0.28, 1.05, 1.85, 1.65),
        AssetProfile("GOLD", 1_800.0, 0.035, 0.14, -0.35, 0.10),
    )
    regimes = (
        RegimeSpec(
            regime=MacroRegime.EXPANSION,
            annual_drift_shift=0.02,
            risk_premium_shift=0.03,
            vol_multiplier=0.75,
            beta_vol_boost=0.02,
            correlation=(
                (1.00, 0.35, 0.45, 0.05),
                (0.35, 1.00, 0.25, -0.05),
                (0.45, 0.25, 1.00, 0.00),
                (0.05, -0.05, 0.00, 1.00),
            ),
        ),
        RegimeSpec(
            regime=MacroRegime.RANGE,
            annual_drift_shift=0.00,
            risk_premium_shift=0.00,
            vol_multiplier=1.00,
            beta_vol_boost=0.05,
            correlation=(
                (1.00, 0.22, 0.32, 0.02),
                (0.22, 1.00, 0.18, 0.00),
                (0.32, 0.18, 1.00, 0.05),
                (0.02, 0.00, 0.05, 1.00),
            ),
        ),
        RegimeSpec(
            regime=MacroRegime.STRESS,
            annual_drift_shift=-0.03,
            risk_premium_shift=-0.09,
            vol_multiplier=1.60,
            beta_vol_boost=0.35,
            correlation=(
                (1.00, 0.65, 0.72, -0.12),
                (0.65, 1.00, 0.55, -0.20),
                (0.72, 0.55, 1.00, -0.10),
                (-0.12, -0.20, -0.10, 1.00),
            ),
        ),
        RegimeSpec(
            regime=MacroRegime.MANIA,
            annual_drift_shift=0.015,
            risk_premium_shift=0.08,
            vol_multiplier=1.35,
            beta_vol_boost=0.55,
            correlation=(
                (1.00, 0.48, 0.74, 0.00),
                (0.48, 1.00, 0.30, -0.08),
                (0.74, 0.30, 1.00, -0.02),
                (0.00, -0.08, -0.02, 1.00),
            ),
        ),
    )
    transition_matrix = (
        (0.90, 0.06, 0.01, 0.03),
        (0.10, 0.72, 0.12, 0.06),
        (0.06, 0.16, 0.72, 0.06),
        (0.16, 0.16, 0.06, 0.62),
    )
    return MarketConfiguration(assets=assets, regimes=regimes, transition_matrix=transition_matrix)


def simulate_price_paths(
    configuration: MarketConfiguration | None = None,
    *,
    years: int = 10,
    steps_per_year: int = 365,
    seed: int | None = 7,
    start_time: datetime | None = None,
    forced_regimes: Sequence[MacroRegime] | None = None,
) -> SimulationResult:
    configuration = configuration or default_market_configuration()
    rng = np.random.default_rng(seed)
    regime_lookup = {spec.regime: spec for spec in configuration.regimes}

    if forced_regimes is None:
        steps = years * steps_per_year
        regimes = _sample_regime_path(configuration, steps, rng)
    else:
        regimes = tuple(forced_regimes)
        steps = len(regimes)

    if steps < 2:
        raise ValueError("simulation requires at least two time steps")

    asset_symbols = tuple(asset.symbol for asset in configuration.assets)
    prices = np.empty((steps + 1, len(configuration.assets)), dtype=float)
    log_returns = np.empty((steps, len(configuration.assets)), dtype=float)
    prices[0] = np.array([asset.start_price for asset in configuration.assets], dtype=float)

    dt = 1.0 / steps_per_year
    now = start_time or datetime(2016, 1, 1)
    step_size = timedelta(days=365 / steps_per_year)
    timestamps = tuple(now + index * step_size for index in range(steps + 1))

    for index, regime in enumerate(regimes):
        spec = regime_lookup[regime]
        correlation = _nearest_positive_definite(np.array(spec.correlation, dtype=float))
        shock = np.linalg.cholesky(correlation) @ rng.standard_normal(len(configuration.assets))
        drift = np.array(
            [
                asset.annual_drift
                + spec.annual_drift_shift
                + asset.risk_exposure * spec.risk_premium_shift
                for asset in configuration.assets
            ],
            dtype=float,
        )
        volatility = np.array(
            [
                asset.annual_vol
                * spec.vol_multiplier
                * (1.0 + asset.vol_sensitivity * spec.beta_vol_boost)
                for asset in configuration.assets
            ],
            dtype=float,
        )
        log_returns[index] = (drift - 0.5 * volatility**2) * dt + volatility * math.sqrt(dt) * shock
        prices[index + 1] = np.maximum(prices[index] * np.exp(log_returns[index]), 1e-9)

    return SimulationResult(
        timestamps=timestamps,
        asset_symbols=asset_symbols,
        prices=prices,
        log_returns=log_returns,
        regimes=regimes,
        steps_per_year=steps_per_year,
    )


def _sample_regime_path(
    configuration: MarketConfiguration,
    steps: int,
    rng: np.random.Generator,
) -> tuple[MacroRegime, ...]:
    regimes = tuple(spec.regime for spec in configuration.regimes)
    regime_index = {regime: index for index, regime in enumerate(regimes)}
    current = MacroRegime.RANGE
    sampled: list[MacroRegime] = []

    for _ in range(steps):
        sampled.append(current)
        transition = np.array(configuration.transition_matrix[regime_index[current]], dtype=float)
        next_index = int(rng.choice(len(regimes), p=transition / transition.sum()))
        current = regimes[next_index]

    return tuple(sampled)


def _nearest_positive_definite(matrix: np.ndarray) -> np.ndarray:
    symmetric = (matrix + matrix.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, 1e-8, None)
    rebuilt = eigenvectors @ np.diag(clipped) @ eigenvectors.T
    scale = np.sqrt(np.diag(rebuilt))
    normalized = rebuilt / np.outer(scale, scale)
    np.fill_diagonal(normalized, 1.0)
    return normalized
