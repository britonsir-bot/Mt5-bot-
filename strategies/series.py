"""Derived price-series registry used by the strategy rule evaluator.

Strategy configs reference series by name (``ema_200``, ``bb_upper``,
``is_inside_bar`` …). This module resolves those names to NumPy arrays aligned
with the candle list, computing each series once and caching it.

Higher-timeframe references such as ``ema_200_h4`` are built by aggregating
``factor`` bars and then publishing the result only from the bar that completes
the higher-timeframe candle onwards. That keeps the series causal: a bar can
never read a higher-timeframe value that only became known later.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

import numpy as np

from core import indicator_series as ind
from core.models import Candle


class UnknownSeriesError(KeyError):
    """Raised when a strategy references a series the registry cannot build."""


def _agg(values: np.ndarray, factor: int, reducer: str) -> np.ndarray:
    out = np.full(values.shape, np.nan)
    for start in range(0, values.size, factor):
        block = values[start : start + factor]
        block = block[np.isfinite(block)]
        if not block.size:
            continue
        if reducer == "first":
            out[start] = block[0]
        elif reducer == "last":
            out[start] = block[-1]
        elif reducer == "max":
            out[start] = block.max()
        elif reducer == "min":
            out[start] = block.min()
        elif reducer == "sum":
            out[start] = block.sum()
    return out


def _shift_published(values: np.ndarray, factor: int) -> np.ndarray:
    """Publish a higher-timeframe value only at the bar that completes it, then carry it."""
    published = np.full(values.shape, np.nan)
    for start in range(0, values.size, factor):
        end = min(start + factor, values.size) - 1
        if np.isfinite(values[start]):
            published[end] = values[start]
    last = np.nan
    out = np.full(values.shape, np.nan)
    for index in range(values.size):
        if np.isfinite(published[index]):
            last = published[index]
        out[index] = last
    return out


class SeriesProvider:
    """Lazily builds and caches named series for one candle series."""

    def __init__(self, candles: Sequence[Candle]) -> None:
        self.candles: list[Candle] = list(candles)
        self.open = np.array([c.open for c in self.candles], dtype=float)
        self.high = np.array([c.high for c in self.candles], dtype=float)
        self.low = np.array([c.low for c in self.candles], dtype=float)
        self.close = np.array([c.close for c in self.candles], dtype=float)
        self.volume = np.array([c.volume for c in self.candles], dtype=float)
        self.timestamps: list[datetime] = [c.timestamp for c in self.candles]
        self.size = len(self.candles)
        self._cache: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def available(self) -> tuple[str, ...]:
        return tuple(sorted(_BUILDERS)) + ("prev_close", "prev_high", "prev_low", "prev_value")

    def has(self, name: str) -> bool:
        return name in _BUILDERS or name.startswith("prev_")

    def get(self, name: str) -> np.ndarray:
        key = name.lower()
        if key not in self._cache:
            if key not in _BUILDERS:
                if key.startswith("prev_"):
                    return self._previous(key[len("prev_") :])
                raise UnknownSeriesError(name)
            self._cache[key] = np.asarray(_BUILDERS[key](self), dtype=float)
        return self._cache[key]

    def resolve(self, indicator: str, field: str) -> str:
        """Map an ``indicator`` + ``field`` pair from a config onto a series name.

        Resolution is strict. Falling back to the indicator's main series for an
        unknown field would silently compare the wrong quantity, so an unmapped
        field raises and the strategy is reported as blocked instead.
        """
        indicator, field = indicator.lower(), field.lower()
        alias = _FIELD_ALIASES.get((indicator, field))
        if alias is not None:
            if self.has(alias):
                return alias
            raise UnknownSeriesError(f"{indicator}.{field}")
        if field == "value" and self.has(indicator):
            return indicator
        raise UnknownSeriesError(f"{indicator}.{field}")

    def _previous(self, base: str) -> np.ndarray:
        key = f"prev_{base}"
        if key not in self._cache:
            source = self.get(base)
            shifted = np.full(source.shape, np.nan)
            shifted[1:] = source[:-1]
            self._cache[key] = shifted
        return self._cache[key]

    def higher_timeframe(self, name: str, factor: int) -> np.ndarray:
        """Compute *name* on bars aggregated by *factor*, published causally."""
        key = f"{name}__htf{factor}"
        if key in self._cache:
            return self._cache[key]
        aggregated = SeriesProvider.__new__(SeriesProvider)
        aggregated.open = _agg(self.open, factor, "first")
        aggregated.high = _agg(self.high, factor, "max")
        aggregated.low = _agg(self.low, factor, "min")
        aggregated.close = _agg(self.close, factor, "last")
        aggregated.volume = _agg(self.volume, factor, "sum")
        aggregated.timestamps = self.timestamps
        aggregated.size = self.size
        aggregated.candles = self.candles
        aggregated._cache = {}
        values = np.full(self.size, np.nan)
        finite = np.isfinite(aggregated.close)
        if finite.any():
            reduced = np.full(self.size, np.nan)
            reduced[finite] = aggregated.get(name)[finite]
            values = _shift_published(reduced, factor)
        self._cache[key] = values
        return values


# ----------------------------------------------------------------------
# builders
# ----------------------------------------------------------------------
def _ibs(provider: SeriesProvider) -> np.ndarray:
    span = provider.high - provider.low
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(span > 0, (provider.close - provider.low) / span, np.nan)


def _down_streak(provider: SeriesProvider) -> np.ndarray:
    out = np.zeros(provider.size)
    for index in range(1, provider.size):
        out[index] = out[index - 1] + 1 if provider.close[index] < provider.close[index - 1] else 0.0
    return out


def _consecutive_heikin_ashi(provider: SeriesProvider) -> np.ndarray:
    ha_open, _, _, ha_close = ind.heikin_ashi(provider.open, provider.high, provider.low, provider.close)
    out = np.zeros(provider.size)
    for index in range(1, provider.size):
        same = (ha_close[index] >= ha_open[index]) == (ha_close[index - 1] >= ha_open[index - 1])
        out[index] = out[index - 1] + 1 if same else 1.0
    return out


def _heikin_ashi_reversal(provider: SeriesProvider) -> np.ndarray:
    ha_open, _, _, ha_close = ind.heikin_ashi(provider.open, provider.high, provider.low, provider.close)
    bullish = ha_close >= ha_open
    out = np.zeros(provider.size)
    out[1:] = (bullish[1:] != bullish[:-1]).astype(float)
    return out


def _bollinger_width(provider: SeriesProvider) -> np.ndarray:
    middle, upper, lower = ind.bollinger(provider.close)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(middle > 0, (upper - lower) / middle, np.nan)


def _rolling_min(values: np.ndarray, period: int) -> np.ndarray:
    """Minimum of the last *period* bars, INCLUDING the current bar.

    Correct for a squeeze test such as ``bb_width == min_width_125``: today's
    width really is the smallest of the last 125 bars.
    """
    out = np.full(values.shape, np.nan)
    for index in range(period - 1, values.size):
        window = values[index - period + 1 : index + 1]
        if np.isfinite(window).any():
            out[index] = np.nanmin(window)
    return out


def _rolling_previous_min(values: np.ndarray, period: int) -> np.ndarray:
    """Minimum of the *period* bars BEFORE the current bar.

    A range low is a level to break, so it must exclude today: including the
    current bar makes ``close < lowest_low_5`` unsatisfiable, because a close can
    never be below its own bar's low.
    """
    out = np.full(values.shape, np.nan)
    for index in range(period, values.size):
        window = values[index - period : index]
        if np.isfinite(window).any():
            out[index] = np.nanmin(window)
    return out


def _ichimoku_part(part: str) -> Callable[[SeriesProvider], np.ndarray]:
    return lambda provider: ind.ichimoku(provider.high, provider.low)[part]


def _parabolic_sar_position(provider: SeriesProvider) -> np.ndarray:
    """1 when the SAR sits below price (bullish), -1 when above."""
    sar = ind.psar(provider.high, provider.low)
    out = np.full(provider.size, np.nan)
    finite = np.isfinite(sar)
    out[finite] = np.where(provider.close[finite] > sar[finite], 1.0, -1.0)
    return out


# Fields that are not ``value`` still map to their own series. Anything absent
# here is unresolved on purpose: see SeriesProvider.resolve.
_FIELD_ALIASES: dict[tuple[str, str], str] = {
    ("supertrend", "direction"): "supertrend_direction",
    ("ib_detect", "is_inside_bar"): "is_inside_bar",
    ("ha_reversal", "is_reversal"): "ha_reversal",
    ("parabolic_sar", "position"): "parabolic_sar_position",
}


def _coloured_bool(values: np.ndarray) -> np.ndarray:
    return values.astype(float)


_BUILDERS: dict[str, Callable[[SeriesProvider], np.ndarray]] = {
    "open": lambda p: p.open,
    "high": lambda p: p.high,
    "low": lambda p: p.low,
    "close": lambda p: p.close,
    "volume": lambda p: p.volume,
    "tick_volume": lambda p: p.volume,
    "rsi_2": lambda p: ind.rsi(p.close, 2),
    "rsi_14": lambda p: ind.rsi(p.close, 14),
    "ibs": _ibs,
    "down_streak": _down_streak,
    "macd_histogram": lambda p: ind.macd(p.close)[2],
    "adx": lambda p: ind.adx(p.high, p.low, p.close)[0],
    "atr": lambda p: ind.atr(p.high, p.low, p.close),
    "supertrend": lambda p: ind.supertrend(p.high, p.low, p.close)[0],
    "supertrend_direction": lambda p: ind.supertrend(p.high, p.low, p.close)[1].astype(float),
    "parabolic_sar": lambda p: ind.psar(p.high, p.low),
    "williams_r": lambda p: ind.williams_r(p.high, p.low, p.close),
    "ema_10": lambda p: ind.ema(p.close, 10),
    "ema_20": lambda p: ind.ema(p.close, 20),
    "ema_30": lambda p: ind.ema(p.close, 30),
    "ema_50": lambda p: ind.ema(p.close, 50),
    "ema_100": lambda p: ind.ema(p.close, 100),
    "ema_200": lambda p: ind.ema(p.close, 200),
    "sma_5": lambda p: ind.sma_series(p.close, 5),
    "sma_200": lambda p: ind.sma_series(p.close, 200),
    "bb_mid": lambda p: ind.bollinger(p.close)[0],
    "bb_upper": lambda p: ind.bollinger(p.close)[1],
    "bb_lower": lambda p: ind.bollinger(p.close)[2],
    "bb_width": _bollinger_width,
    "min_width_125": lambda p: _rolling_min(_bollinger_width(p), 125),
    "kc_mid": lambda p: ind.keltner(p.high, p.low, p.close)[0],
    "kc_upper": lambda p: ind.keltner(p.high, p.low, p.close)[1],
    "kc_lower": lambda p: ind.keltner(p.high, p.low, p.close)[2],
    "donchian_upper": lambda p: ind.donchian(p.high, p.low)[0],
    "donchian_lower": lambda p: ind.donchian(p.high, p.low)[1],
    "lowest_low_5": lambda p: _rolling_previous_min(p.low, 5),
    "highest_high_5": lambda p: -_rolling_previous_min(-p.high, 5),
    "parabolic_sar_position": _parabolic_sar_position,
    "volume_avg": lambda p: ind.sma_series(p.volume, 20),
    "tenkan_sen": _ichimoku_part("conversion"),
    "kijun_sen": _ichimoku_part("base"),
    "senkou_span_a": _ichimoku_part("span_a"),
    "senkou_span_b": _ichimoku_part("span_b"),
    "is_inside_bar": lambda p: _coloured_bool(ind.inside_bar(p.high, p.low)),
    "ha_consecutive": _consecutive_heikin_ashi,
    "ha_reversal": _heikin_ashi_reversal,
    "ema_50_h4": lambda p: p.higher_timeframe("ema_50", 4),
    "ema_200_h4": lambda p: p.higher_timeframe("ema_200", 4),
    "ema_20_h4": lambda p: p.higher_timeframe("ema_20", 4),
    "atr_h4": lambda p: p.higher_timeframe("atr", 4),
}


def available_series() -> tuple[str, ...]:
    return tuple(sorted(_BUILDERS))


def describe_missing(names: Sequence[str]) -> tuple[str, ...]:
    """Names this registry cannot build. ``prev_x`` resolves when ``x`` can."""
    missing: list[str] = []
    for name in names:
        if name in _BUILDERS:
            continue
        if name.startswith("prev_") and name[len("prev_") :] in _BUILDERS:
            continue
        missing.append(name)
    return tuple(missing)


__all__ = [
    "SeriesProvider",
    "UnknownSeriesError",
    "available_series",
    "describe_missing",
]
