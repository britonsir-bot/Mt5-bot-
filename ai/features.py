"""Causal feature engineering for the advisory direction model.

Every feature for bar ``t`` is computed from bar ``t`` and earlier bars only, so
a feature row can never encode the outcome it is paired with. The label looks
forward instead (``label[t] = 1`` when ``close[t + horizon] > close[t]``); that
asymmetry is what makes the model a forecast rather than a memo. Indicator
warm-up rows are dropped rather than filled, because a value derived from
unformed indicators is not a reading and would otherwise leak a constant into
the model.

Feature vector (in :attr:`FeatureEngineer.FEATURE_NAMES` order):

    return_1            close[t] / close[t-1] - 1
    return_3            close[t] / close[t-3] - 1
    return_6            close[t] / close[t-6] - 1
    return_12           close[t] / close[t-12] - 1
    rsi_14              Wilder RSI(14) / 100
    macd_histogram      MACD(12, 26, 9) histogram / close
    atr_pct             ATR(14) / close
    ema_distance_fast   (close - EMA(20)) / ATR(14)
    ema_distance_slow   (close - EMA(50)) / ATR(14)
    adx_14              ADX(14) / 100
    bollinger_width     (upper - lower) / middle, Bollinger(20, 2.0)
    volume_ratio        volume / SMA(volume, 20)
    range_pct           (high - low) / close
    body_pct            (close - open) / close
    upper_wick_pct      (high - max(open, close)) / close
    lower_wick_pct      (min(open, close) - low) / close
    close_location      (close - low) / (high - low) - 0.5
    hour_sin            sin(2 * pi * hour / 24)
    hour_cos            cos(2 * pi * hour / 24)
    weekday_sin         sin(2 * pi * weekday / 7)
    weekday_cos         cos(2 * pi * weekday / 7)
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from core import indicator_series as indicators
from core.models import Candle

_RETURN_LOOKBACKS: tuple[int, ...] = (1, 3, 6, 12)


def _pct_change(close: np.ndarray, lookback: int) -> np.ndarray:
    """Trailing percentage change; the first ``lookback`` bars stay ``nan``."""
    out = np.full(close.shape, np.nan)
    if close.size > lookback:
        previous = close[:-lookback]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[lookback:] = close[lookback:] / previous - 1.0
    return out


class FeatureEngineer:
    """Builds the feature matrix and forward labels from a candle sequence.

    The class is stateless: the same candles always produce the same matrix,
    which is what lets tests mutate future bars and assert that earlier rows do
    not move.
    """

    FEATURE_NAMES: tuple[str, ...] = (
        "return_1",
        "return_3",
        "return_6",
        "return_12",
        "rsi_14",
        "macd_histogram",
        "atr_pct",
        "ema_distance_fast",
        "ema_distance_slow",
        "adx_14",
        "bollinger_width",
        "volume_ratio",
        "range_pct",
        "body_pct",
        "upper_wick_pct",
        "lower_wick_pct",
        "close_location",
        "hour_sin",
        "hour_cos",
        "weekday_sin",
        "weekday_cos",
    )

    def feature_matrix(self, candles: Sequence[Candle]) -> np.ndarray:
        """Return a ``(n_bars, n_features)`` causal feature matrix.

        Rows are never trimmed here; warm-up rows carry ``nan`` so callers that
        need alignment (leakage tests, walk-forward) can see exactly which bars
        are usable.
        """
        n_bars = len(candles)
        n_features = len(self.FEATURE_NAMES)
        if n_bars == 0:
            return np.empty((0, n_features), dtype=float)

        open_ = np.array([candle.open for candle in candles], dtype=float)
        high = np.array([candle.high for candle in candles], dtype=float)
        low = np.array([candle.low for candle in candles], dtype=float)
        close = np.array([candle.close for candle in candles], dtype=float)
        volume = np.array([float(candle.volume) for candle in candles], dtype=float)
        hours = np.array([candle.timestamp.hour for candle in candles], dtype=float)
        weekdays = np.array([float(candle.timestamp.weekday()) for candle in candles])

        with np.errstate(divide="ignore", invalid="ignore"):
            rsi = indicators.rsi(close, 14) / 100.0
            _, _, macd_histogram = indicators.macd(close)
            macd_histogram = macd_histogram / close
            atr = indicators.atr(high, low, close, 14)
            ema_fast = indicators.ema(close, 20)
            ema_slow = indicators.ema(close, 50)
            adx_values, _, _ = indicators.adx(high, low, close, 14)
            middle, upper, lower = indicators.bollinger(close, 20, 2.0)
            volume_ratio = indicators.volume_ratio(volume, 20)

        atr_safe = np.where(atr > 0, atr, np.nan)
        ema_distance_fast = (close - ema_fast) / atr_safe
        ema_distance_slow = (close - ema_slow) / atr_safe
        middle_safe = np.where(middle > 0, middle, np.nan)
        bollinger_width = (upper - lower) / middle_safe

        bar_range = high - low
        range_pct = bar_range / close
        body_pct = (close - open_) / close
        upper_wick_pct = (high - np.maximum(open_, close)) / close
        lower_wick_pct = (np.minimum(open_, close) - low) / close
        close_location = np.where(bar_range > 0, (close - low) / bar_range - 0.5, 0.0)

        hour_angle = 2.0 * np.pi * hours / 24.0
        weekday_angle = 2.0 * np.pi * weekdays / 7.0

        columns = [
            _pct_change(close, _RETURN_LOOKBACKS[0]),
            _pct_change(close, _RETURN_LOOKBACKS[1]),
            _pct_change(close, _RETURN_LOOKBACKS[2]),
            _pct_change(close, _RETURN_LOOKBACKS[3]),
            rsi,
            macd_histogram,
            atr / close,
            ema_distance_fast,
            ema_distance_slow,
            adx_values / 100.0,
            bollinger_width,
            volume_ratio,
            range_pct,
            body_pct,
            upper_wick_pct,
            lower_wick_pct,
            close_location,
            np.sin(hour_angle),
            np.cos(hour_angle),
            np.sin(weekday_angle),
            np.cos(weekday_angle),
        ]
        return np.column_stack(columns).astype(float, copy=False)

    def build_with_indices(
        self, candles: Sequence[Candle], horizon: int = 1
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(X, y, indices)`` aligned row-for-row.

        ``indices`` holds the original bar index of each surviving row. Rows are
        dropped when any feature is non-finite (indicator warm-up) or when the
        forward bar needed for the label does not exist yet (the final
        ``horizon`` bars), so ``X`` and ``y`` can never drift out of step.
        """
        horizon = int(horizon)
        if horizon < 1:
            raise ValueError("horizon must be at least 1")

        n_bars = len(candles)
        features = self.feature_matrix(candles)
        close = np.array([candle.close for candle in candles], dtype=float)

        if n_bars <= horizon:
            return (
                features[:0],
                np.empty(0, dtype=int),
                np.empty(0, dtype=int),
            )

        has_label = np.zeros(n_bars, dtype=bool)
        has_label[: n_bars - horizon] = True
        finite = np.isfinite(features).all(axis=1)
        mask = has_label & finite

        future_close = np.full(n_bars, np.nan)
        future_close[: n_bars - horizon] = close[horizon:]

        indices = np.flatnonzero(mask)
        X = features[mask]
        y = (future_close[mask] > close[mask]).astype(int)
        return X, y, indices

    def build(
        self, candles: Sequence[Candle], horizon: int = 1
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return the ``(X, y)`` pair used for training."""
        X, y, _ = self.build_with_indices(candles, horizon)
        return X, y
