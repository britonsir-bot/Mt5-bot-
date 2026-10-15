"""Synthetic candle fixtures shared by the advisory-model tests.

The generator injects a learnable relationship the model can actually recover:
next-bar returns are AR(1) with a positive coefficient, so short-horizon
momentum features carry real predictive signal. That lets a test distinguish a
working pipeline (accuracy clearly above chance) from a broken one.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from core.models import Candle


def make_candles(
    n: int = 1500,
    seed: int = 7,
    autocorrelation: float = 0.6,
    noise: float = 2e-4,
) -> list[Candle]:
    rng = np.random.default_rng(seed)
    returns = np.zeros(n)
    shocks = rng.normal(0.0, noise, n)
    for index in range(1, n):
        returns[index] = autocorrelation * returns[index - 1] + shocks[index]

    close = 100.0 * np.exp(np.cumsum(returns))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) + np.abs(rng.normal(0.0, 1e-3, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.0, 1e-3, n))
    volume = rng.integers(50, 500, n)

    start = datetime(2024, 1, 1)
    return [
        Candle(
            timestamp=start + timedelta(hours=index),
            open=float(open_[index]),
            high=float(high[index]),
            low=float(low[index]),
            close=float(close[index]),
            volume=int(volume[index]),
        )
        for index in range(n)
    ]
