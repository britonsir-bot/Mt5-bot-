"""Evaluator for the declarative conditions in ``mt5_bot_strategies.yaml``.

Condition masks are computed for the whole series at once rather than per bar, so
a backtest evaluates a strategy in a handful of vectorised operations.

Every comparison involving a warm-up ``nan`` is False. That is deliberate: a
strategy must not fire before its indicators have formed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from strategies.series import SeriesProvider, UnknownSeriesError

SUPPORTED_OPERATORS = ("eq", "lt", "lte", "gt", "gte", "cross_above", "cross_below", "btwn")
CALENDAR_FIELDS = frozenset({"day_of_week", "hour"})
INDICATOR_KINDS = frozenset({"indicator", "indicator_compare", "indicator_crossover"})


class UnsupportedConditionError(ValueError):
    """Raised for a condition this evaluator cannot express."""


@dataclass(frozen=True, slots=True)
class Condition:
    identifier: str
    kind: str
    operator: str
    field: str = "value"
    indicator: str = ""
    value: Any = None
    value_min: float | None = None
    value_max: float | None = None
    compare: str = ""
    compare_indicator: str = ""
    threshold_pct: float | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Condition:
        return cls(
            identifier=str(raw.get("id", "")),
            kind=str(raw.get("type", "")),
            operator=str(raw.get("operator", "")),
            field=str(raw.get("field", "value")),
            indicator=str(raw.get("indicator", "")),
            value=raw.get("value"),
            value_min=raw.get("value_min"),
            value_max=raw.get("value_max"),
            compare=str(raw.get("compare", "")),
            compare_indicator=str(raw.get("compare_indicator", "")),
            threshold_pct=raw.get("threshold_pct"),
        )

    def left_series_name(self) -> str | None:
        """Name of the series on the left of the comparison, if any."""
        if self.kind == "calendar":
            return None
        if self.kind == "price":
            return self.field or "close"
        if self.kind in INDICATOR_KINDS and self.indicator:
            return f"{self.indicator}:{self.field}"
        return None

    def is_previous_value(self) -> bool:
        """``compare: prev_value`` means "the previous value of my own series"."""
        return self.compare == "prev_value"

    def right_series_name(self) -> str | None:
        if self.is_previous_value():
            return None
        return self.compare_indicator or self.compare or None


@dataclass(frozen=True, slots=True)
class ConditionGroup:
    operator: str
    conditions: tuple[Condition, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> ConditionGroup | None:
        if not raw:
            return None
        conditions = tuple(
            Condition.from_mapping(item) for item in raw.get("conditions", []) if isinstance(item, Mapping)
        )
        if not conditions:
            return None
        return cls(str(raw.get("operator", "AND")).upper(), conditions)

    def series_requirements(self) -> tuple[str, ...]:
        names: list[str] = []
        for condition in self.conditions:
            if condition.kind in CALENDAR_FIELDS:
                continue
            left = condition.left_series_name()
            if left:
                names.append(left)
            right = condition.right_series_name()
            if right:
                names.append(right)
        return tuple(names)


def _shift(values: np.ndarray) -> np.ndarray:
    out = np.full(values.shape, np.nan)
    out[1:] = values[:-1]
    return out


def _resolve(provider: SeriesProvider, name: str) -> np.ndarray:
    """Resolve either ``indicator:field`` or a plain series name."""
    if ":" in name:
        indicator, _, field = name.partition(":")
        return provider.get(provider.resolve(indicator, field))
    return provider.get(name)


def _calendar_series(provider: SeriesProvider, field: str) -> np.ndarray:
    if field == "day_of_week":
        return np.array([stamp.isoweekday() for stamp in provider.timestamps], dtype=float)
    if field == "hour":
        return np.array([stamp.hour for stamp in provider.timestamps], dtype=float)
    raise UnsupportedConditionError(f"unsupported calendar field {field!r}")


def _compare(operator: str, left: np.ndarray, right: Any) -> np.ndarray:
    if operator == "btwn":
        if not isinstance(right, tuple) or len(right) != 2:
            raise UnsupportedConditionError("btwn requires value_min and value_max")
        low, high = right
        return (left >= low) & (left <= high)
    if operator == "eq":
        return left == right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator in ("cross_above", "cross_below"):
        previous_left = _shift(left)
        previous_right = _shift(right) if isinstance(right, np.ndarray) else right
        if operator == "cross_above":
            return (left > right) & (previous_left <= previous_right)
        return (left < right) & (previous_left >= previous_right)
    raise UnsupportedConditionError(f"unsupported operator {operator!r}")


def condition_mask(condition: Condition, provider: SeriesProvider) -> np.ndarray:
    if condition.kind == "calendar":
        left = _calendar_series(provider, condition.field)
    elif condition.kind in INDICATOR_KINDS or condition.kind == "price":
        name = condition.left_series_name() or "close"
        left = _resolve(provider, name)
    else:
        raise UnsupportedConditionError(f"unsupported condition type {condition.kind!r}")

    right: Any
    if condition.value_min is not None or condition.value_max is not None:
        right = (
            -np.inf if condition.value_min is None else float(condition.value_min),
            np.inf if condition.value_max is None else float(condition.value_max),
        )
    else:
        right_name = condition.right_series_name()
        if condition.is_previous_value():
            right = _shift(left)
        elif right_name:
            right = _resolve(provider, right_name)
            if condition.threshold_pct is not None:
                right = right * (1.0 + float(condition.threshold_pct) / 100.0)
        else:
            right = coerce_value(condition.value)

    mask = _compare(condition.operator, left, right)
    return np.asarray(mask, dtype=bool)


def group_mask(group: ConditionGroup, provider: SeriesProvider) -> np.ndarray:
    masks = condition_masks(group, provider)
    return combine(masks, group.operator, provider.size)


# Configs express some comparisons as words rather than numbers
# (``value: below`` on a SAR position, ``value: true`` on a flag).
_VALUE_ALIASES: dict[str, float] = {
    "true": 1.0,
    "false": 0.0,
    "below": 1.0,
    "above": -1.0,
    "bullish": 1.0,
    "bearish": -1.0,
    "long": 1.0,
    "short": -1.0,
}


def coerce_value(value: Any) -> Any:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _VALUE_ALIASES:
            return _VALUE_ALIASES[key]
        raise UnsupportedConditionError(f"cannot compare a series against {value!r}")
    return value


def condition_masks(group: ConditionGroup, provider: SeriesProvider) -> list[np.ndarray]:
    return [condition_mask(condition, provider) for condition in group.conditions]


def combine(masks: Sequence[np.ndarray], operator: str, size: int) -> np.ndarray:
    if not masks:
        return np.zeros(size, dtype=bool)
    reducer = np.logical_and.reduce if operator == "AND" else np.logical_or.reduce
    return np.asarray(reducer(list(masks)), dtype=bool)


def describe_requirements(requirements: Sequence[str], provider: SeriesProvider) -> tuple[str, ...]:
    """Series names a group needs that this provider cannot build."""
    missing: list[str] = []
    for name in requirements:
        try:
            _resolve(provider, name)
        except (UnknownSeriesError, UnsupportedConditionError):
            missing.append(name)
    return tuple(dict.fromkeys(missing))
