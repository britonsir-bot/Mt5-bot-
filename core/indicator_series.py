"""Vectorised technical indicator series.

Ported from ``Mt5-trading-platform/utils/indicators.py`` and reimplemented on
NumPy arrays so the desktop app does not need pandas. The smoothing constants
match that implementation (``alpha = 2 / (period + 1)`` for EMAs and
``alpha = 1 / period`` for Wilder-style averages) so readings are comparable.

Warm-up periods are returned as ``nan`` rather than a filled default: callers
decide how to handle them, and the strategy engine refuses to score on them.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

DEFAULTS = {
    "ema_fast": 20,
    "ema_slow": 50,
    "ema_trend": 200,
    "adx_period": 14,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "cci_period": 20,
    "atr_period": 14,
    "bollinger_period": 20,
    "bollinger_mult": 2.0,
    "donchian_period": 20,
    "keltner_ema": 20,
    "keltner_atr": 10,
    "keltner_mult": 2.0,
    "supertrend_atr": 10,
    "supertrend_mult": 2.0,
    "williams_period": 14,
    "volume_period": 20,
    "psar_step": 0.02,
    "psar_max": 0.2,
}


def _as_array(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


def sma_series(values, period: int) -> np.ndarray:
    data = _as_array(values)
    out = np.full(data.shape, np.nan)
    if period <= 0 or data.size < period:
        return out
    cumulative = np.cumsum(np.insert(data, 0, 0.0))
    out[period - 1:] = (cumulative[period:] - cumulative[:-period]) / period
    return out


def _recursive_smooth(data: np.ndarray, alpha: float) -> np.ndarray:
    """Exponential smoothing seeded with the first finite value."""
    out = np.full(data.shape, np.nan)
    previous = np.nan
    for index, value in enumerate(data):
        if not np.isfinite(value):
            continue
        previous = value if not np.isfinite(previous) else alpha * value + (1.0 - alpha) * previous
        out[index] = previous
    return out


def ema(values, period: int) -> np.ndarray:
    if period <= 0:
        raise ValueError("period must be positive")
    return _recursive_smooth(_as_array(values), 2.0 / (period + 1.0))


def wilder(values, period: int) -> np.ndarray:
    if period <= 0:
        raise ValueError("period must be positive")
    return _recursive_smooth(_as_array(values), 1.0 / period)


def rsi(close, period: int = 14) -> np.ndarray:
    data = _as_array(close)
    out = np.full(data.shape, np.nan)
    if data.size < 2:
        return out
    delta = np.diff(data, prepend=np.nan)
    gain = np.where(np.isfinite(delta), np.clip(delta, 0.0, None), np.nan)
    loss = np.where(np.isfinite(delta), -np.clip(delta, None, 0.0), np.nan)
    average_gain = wilder(gain[1:], period)
    average_loss = wilder(loss[1:], period)
    with np.errstate(divide="ignore", invalid="ignore"):
        relative_strength = average_gain / average_loss
        values = 100.0 - (100.0 / (1.0 + relative_strength))
    values = np.where(average_loss == 0, 100.0, values)
    values = np.where(average_gain == 0, 0.0, values)
    values = np.where((average_gain == 0) & (average_loss == 0), 50.0, values)
    out[1:] = values
    # Fewer than ``period`` deltas is not a reading, it is warm-up. Blank it so a
    # strategy scoring on ``rsi < 30`` can never fire on unformed data.
    out[:period] = np.nan
    return out


def true_range(high, low, close) -> np.ndarray:
    high, low, close = _as_array(high), _as_array(low), _as_array(close)
    previous_close = np.roll(close, 1)
    previous_close[0] = np.nan
    return np.nanmax(
        np.vstack([high - low, np.abs(high - previous_close), np.abs(low - previous_close)]),
        axis=0,
    )


def atr(high, low, close, period: int = 14) -> np.ndarray:
    return wilder(true_range(high, low, close), period)


def adx(high, low, close, period: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    high, low, close = _as_array(high), _as_array(low), _as_array(close)
    up_move = np.diff(high, prepend=np.nan)
    down_move = -np.diff(low, prepend=np.nan)
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm[0] = 0.0
    minus_dm[0] = 0.0

    smoothed_range = wilder(true_range(high, low, close), period)
    smoothed_plus = wilder(plus_dm, period)
    smoothed_minus = wilder(minus_dm, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * smoothed_plus / smoothed_range
        minus_di = 100.0 * smoothed_minus / smoothed_range
        denominator = plus_di + minus_di
        dx = 100.0 * np.abs(plus_di - minus_di) / np.where(denominator == 0, np.nan, denominator)

    return wilder(dx, period), plus_di, minus_di


def macd(close, fast: int = 12, slow: int = 26, signal: int = 9):
    close = _as_array(close)
    line = ema(close, fast) - ema(close, slow)
    signal_line = _recursive_smooth(line, 2.0 / (signal + 1.0))
    return line, signal_line, line - signal_line


def vwap(high, low, close, volume, timestamps) -> np.ndarray:
    high, low, close = _as_array(high), _as_array(low), _as_array(close)
    volume = np.nan_to_num(_as_array(volume), nan=0.0)
    typical = (high + low + close) / 3.0
    out = np.full(close.shape, np.nan)
    current_day = None
    cumulative_pv = cumulative_volume = 0.0
    for index, stamp in enumerate(timestamps):
        day = _utc_day(stamp)
        if day != current_day:
            current_day = day
            cumulative_pv = cumulative_volume = 0.0
        weight = volume[index] if volume[index] > 0 else 1.0
        cumulative_pv += typical[index] * weight
        cumulative_volume += weight
        out[index] = cumulative_pv / cumulative_volume
    return out


def _utc_day(stamp) -> object:
    if isinstance(stamp, datetime):
        moment = stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).date()
    if hasattr(stamp, "date"):
        return stamp.date()
    return 0


def cci(high, low, close, period: int = 20) -> np.ndarray:
    high, low, close = _as_array(high), _as_array(low), _as_array(close)
    typical = (high + low + close) / 3.0
    mean = sma_series(typical, period)
    out = np.full(typical.shape, np.nan)
    for index in range(period - 1, typical.size):
        window = typical[index - period + 1 : index + 1]
        deviation = np.mean(np.abs(window - window.mean()))
        if deviation > 0:
            out[index] = (typical[index] - mean[index]) / (0.015 * deviation)
    return out


def volume_ratio(volume, period: int = 20) -> np.ndarray:
    volume = _as_array(volume)
    average = sma_series(volume, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(average > 0, volume / average, np.nan)


def bollinger(close, period: int = 20, multiplier: float = 2.0):
    close = _as_array(close)
    middle = sma_series(close, period)
    deviation = np.full(close.shape, np.nan)
    for index in range(period - 1, close.size):
        deviation[index] = close[index - period + 1 : index + 1].std(ddof=0)
    return middle, middle + multiplier * deviation, middle - multiplier * deviation


def donchian(high, low, period: int = 20):
    high, low = _as_array(high), _as_array(low)
    upper = np.full(high.shape, np.nan)
    lower = np.full(low.shape, np.nan)
    for index in range(period - 1, high.size):
        upper[index] = high[index - period + 1 : index + 1].max()
        lower[index] = low[index - period + 1 : index + 1].min()
    return upper, lower


def keltner(high, low, close, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0):
    middle = ema(close, ema_period)
    band = atr(high, low, close, atr_period)
    return middle, middle + multiplier * band, middle - multiplier * band


def supertrend(high, low, close, atr_period: int = 10, multiplier: float = 2.0):
    high, low, close = _as_array(high), _as_array(low), _as_array(close)
    band = atr(high, low, close, atr_period)
    midpoint = (high + low) / 2.0
    upper_basic = midpoint + multiplier * band
    lower_basic = midpoint - multiplier * band

    line = np.full(close.shape, np.nan)
    direction = np.zeros(close.shape, dtype=int)
    upper = lower = np.nan
    trend = 1
    for index in range(close.size):
        if not np.isfinite(band[index]):
            continue
        if not np.isfinite(upper):
            upper, lower = upper_basic[index], lower_basic[index]
            line[index], direction[index] = lower, 1
            continue
        upper = (
            upper_basic[index]
            if upper_basic[index] < upper or close[index - 1] > upper
            else upper
        )
        lower = (
            lower_basic[index]
            if lower_basic[index] > lower or close[index - 1] < lower
            else lower
        )
        if trend == 1 and close[index] < lower:
            trend = -1
        elif trend == -1 and close[index] > upper:
            trend = 1
        line[index] = lower if trend == 1 else upper
        direction[index] = trend
    return line, direction


def williams_r(high, low, close, period: int = 14) -> np.ndarray:
    high, low, close = _as_array(high), _as_array(low), _as_array(close)
    out = np.full(close.shape, np.nan)
    for index in range(period - 1, close.size):
        highest = high[index - period + 1 : index + 1].max()
        lowest = low[index - period + 1 : index + 1].min()
        span = highest - lowest
        if span > 0:
            out[index] = -100.0 * (highest - close[index]) / span
    return out


def heikin_ashi(open_, high, low, close):
    open_, high, low, close = _as_array(open_), _as_array(high), _as_array(low), _as_array(close)
    ha_close = (open_ + high + low + close) / 4.0
    ha_open = np.full(close.shape, np.nan)
    if close.size:
        ha_open[0] = (open_[0] + close[0]) / 2.0
        for index in range(1, close.size):
            ha_open[index] = (ha_open[index - 1] + ha_close[index - 1]) / 2.0
    ha_high = np.nanmax(np.vstack([high, ha_open, ha_close]), axis=0)
    ha_low = np.nanmin(np.vstack([low, ha_open, ha_close]), axis=0)
    return ha_open, ha_high, ha_low, ha_close


def psar(high, low, step: float = 0.02, maximum: float = 0.2) -> np.ndarray:
    high, low = _as_array(high), _as_array(low)
    out = np.full(high.shape, np.nan)
    if high.size < 2:
        return out
    trend = 1
    extreme = high[0]
    acceleration = step
    value = low[0]
    for index in range(1, high.size):
        value = value + acceleration * (extreme - value)
        if trend == 1:
            if low[index] < value:
                trend = -1
                value = extreme
                extreme = low[index]
                acceleration = step
            elif high[index] > extreme:
                extreme = high[index]
                acceleration = min(acceleration + step, maximum)
        else:
            if high[index] > value:
                trend = 1
                value = extreme
                extreme = high[index]
                acceleration = step
            elif low[index] < extreme:
                extreme = low[index]
                acceleration = min(acceleration + step, maximum)
        out[index] = value
    return out


def ichimoku(high, low, conversion: int = 9, base: int = 26, span_b: int = 52) -> dict:
    high, low = _as_array(high), _as_array(low)
    conversion_line = _midpoint(high, low, conversion)
    base_line = _midpoint(high, low, base)
    span_a = (conversion_line + base_line) / 2.0
    span_b_line = _midpoint(high, low, span_b)
    return {
        "conversion": conversion_line,
        "base": base_line,
        "span_a": span_a,
        "span_b": span_b_line,
    }


def _midpoint(high, low, period: int) -> np.ndarray:
    out = np.full(high.shape, np.nan)
    for index in range(period - 1, high.size):
        out[index] = (high[index - period + 1 : index + 1].max()
                      + low[index - period + 1 : index + 1].min()) / 2.0
    return out


def ma_ribbon(close, periods=(10, 20, 30, 40, 50)) -> dict[int, np.ndarray]:
    return {period: ema(close, period) for period in periods}


def inside_bar(high, low) -> np.ndarray:
    high, low = _as_array(high), _as_array(low)
    out = np.zeros(high.shape, dtype=bool)
    out[1:] = (high[1:] <= high[:-1]) & (low[1:] >= low[:-1])
    return out
