"""Strategy specifications loaded from the vendored MT5 bot config.

Source of the vendored files: the ``britonsir-bot/mt5-trading-strategies``
repository (``mt5_bot_strategies.yaml`` and ``strategy_library.yaml``). Run
``load_specs`` / ``load_documented_stats`` to re-read them.

The ``documented`` block on each spec is IMPORTANT to read correctly: those
numbers are the ones the YAML cites from external literature and vendor
research. They are not measurements taken in this repository and must never be
presented as results produced here. Only ``BacktestResult`` holds numbers this
codebase actually computed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from strategies.rules import Condition, ConditionGroup
from strategies.series import SeriesProvider, UnknownSeriesError, describe_missing

CATALOGUE_DIR = Path(__file__).resolve().parent / "catalogue"
BOT_CONFIG = CATALOGUE_DIR / "mt5_bot_strategies.yaml"
LIBRARY_CONFIG = CATALOGUE_DIR / "strategy_library.yaml"

PORTFOLIO_ONLY_KEYS = frozenset({"ranking", "safe_haven", "rotation", "universe"})
SUPPORTED_EXIT_METHODS = frozenset({"time_exit", "signal_exit"})


class StrategyConfigError(ValueError):
    """Raised when a strategy config cannot be parsed."""


@dataclass(frozen=True, slots=True)
class StopSpec:
    enabled: bool
    method: str
    atr_period: int
    multiplier: float
    percent: float

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> StopSpec:
        raw = raw or {}
        params = raw.get("params") or {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            method=str(raw.get("method") or "none"),
            atr_period=int(params.get("atr_period", 14)),
            multiplier=float(params.get("multiplier", 1.0)),
            # The configs express a fixed stop as ``value_pct`` beside ``method``.
            # Reading only ``params.percent`` silently produced a zero stop, which
            # discarded every entry without a trace.
            percent=float(
                raw.get("value_pct")
                or raw.get("percent")
                or params.get("percent")
                or 0.0
            ),
        )


@dataclass(frozen=True, slots=True)
class RiskSpec:
    sizing_method: str
    risk_per_trade_pct: float
    stop_loss: StopSpec
    take_profit: StopSpec
    trailing_stop: StopSpec

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> RiskSpec:
        raw = raw or {}
        sizing = raw.get("position_sizing") or {}
        return cls(
            sizing_method=str(sizing.get("method") or "fixed_fraction"),
            risk_per_trade_pct=float(sizing.get("risk_per_trade_pct") or 0.0),
            stop_loss=StopSpec.from_mapping(raw.get("stop_loss")),
            take_profit=StopSpec.from_mapping(raw.get("take_profit")),
            trailing_stop=StopSpec.from_mapping(raw.get("trailing_stop")),
        )


@dataclass(frozen=True, slots=True)
class DocumentedStats:
    """Numbers cited by the config. Not measured here."""

    win_rate_pct: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None
    backtest_period: str = ""
    confidence: str = ""
    source: str = ""


@dataclass(frozen=True, slots=True)
class StrategySpec:
    identifier: str
    name: str
    category: str
    description: str
    symbol: str
    timeframe: str
    trade_direction: str
    enabled: bool
    entry: ConditionGroup | None
    exit_signal: ConditionGroup | None
    exit_method: str
    time_exit_bars: int | None
    risk: RiskSpec
    documented: DocumentedStats = field(default_factory=DocumentedStats)
    blocking_reasons: tuple[str, ...] = ()

    @property
    def evaluable(self) -> bool:
        return not self.blocking_reasons

    def requirements(self) -> tuple[str, ...]:
        names: list[str] = []
        if self.entry is not None:
            names.extend(self.entry.series_requirements())
        if self.exit_signal is not None:
            names.extend(self.exit_signal.series_requirements())
        return tuple(names)

    def missing_series(self, provider: SeriesProvider) -> tuple[str, ...]:
        missing: list[str] = []
        for name in self.requirements():
            try:
                if ":" in name:
                    indicator, _, series_field = name.partition(":")
                    provider.resolve(indicator, series_field)
                else:
                    provider.get(name)
            except (UnknownSeriesError, KeyError):
                missing.append(name)
        return tuple(dict.fromkeys(missing))


def _portfolio_reasons(raw_entry: dict[str, Any], raw_exit: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key in list(raw_entry) + list(raw_exit):
        if key in PORTFOLIO_ONLY_KEYS:
            reasons.append(f"needs portfolio-level handling ({key})")
    method = str(raw_exit.get("method") or "")
    if method and method not in SUPPORTED_EXIT_METHODS:
        reasons.append(f"unsupported exit method ({method})")
    return reasons


def _build_spec(raw: dict[str, Any], documented: DocumentedStats) -> StrategySpec:
    entry_raw = raw.get("entry_conditions") or {}
    exit_raw = raw.get("exit_conditions") or {}
    entry = ConditionGroup.from_mapping(entry_raw)

    exit_signal = ConditionGroup.from_mapping(exit_raw.get("signal_exit"))
    time_exit = exit_raw.get("time_exit") or {}
    method = str(exit_raw.get("method") or "")

    reasons = _portfolio_reasons(entry_raw, exit_raw)
    if entry is None:
        reasons.append("no declarative entry conditions")
    elif spec_missing := describe_missing(
        [name for name in entry.series_requirements() if ":" not in name]
    ):
        reasons.append("no series for " + ", ".join(spec_missing))

    return StrategySpec(
        identifier=str(raw.get("id") or raw.get("name") or "unknown"),
        name=str(raw.get("name") or raw.get("id") or "unknown"),
        category=str(raw.get("category") or "uncategorised"),
        description=" ".join(str(raw.get("description") or "").split()),
        symbol=str(raw.get("symbol") or ""),
        timeframe=str(raw.get("timeframe") or ""),
        trade_direction=str(raw.get("trade_direction") or "long_only"),
        enabled=bool(raw.get("enabled", True)),
        entry=entry,
        exit_signal=exit_signal,
        exit_method=method,
        time_exit_bars=int(time_exit.get("bars")) if time_exit.get("bars") else None,
        risk=RiskSpec.from_mapping(raw.get("risk_management")),
        documented=documented,
        blocking_reasons=tuple(reasons),
    )


def load_documented_stats(path: Path | None = None) -> dict[str, DocumentedStats]:
    payload = yaml.safe_load((path or LIBRARY_CONFIG).read_text(encoding="utf-8")) or {}
    stats: dict[str, DocumentedStats] = {}
    for item in payload.get("strategies", []) or []:
        evidence = item.get("evidence") or {}
        identifier = str(item.get("id") or "")
        if not identifier:
            continue
        stats[identifier] = DocumentedStats(
            win_rate_pct=_maybe_float(item.get("expected_win_rate_pct")),
            profit_factor=_maybe_float(item.get("profit_factor")),
            max_drawdown_pct=_maybe_float(item.get("max_drawdown_pct")),
            sharpe_ratio=_maybe_float(evidence.get("sharpe_ratio")),
            backtest_period=str(item.get("backtest_period") or ""),
            confidence=str(item.get("confidence") or ""),
            source=" ".join(str(evidence.get("source") or "").split()),
        )
    return stats


def _maybe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def load_specs(
    path: Path | None = None, documented: dict[str, DocumentedStats] | None = None
) -> list[StrategySpec]:
    """Load every executable strategy from the vendored bot config."""
    payload = yaml.safe_load((path or BOT_CONFIG).read_text(encoding="utf-8")) or {}
    catalogue = load_documented_stats() if documented is None else documented
    specs: list[StrategySpec] = []
    for raw in payload.get("strategies", []) or []:
        identifier = str(raw.get("id") or "")
        specs.append(_build_spec(raw, catalogue.get(identifier, DocumentedStats())))
    return specs


def ml_settings(path: Path | None = None) -> dict[str, Any]:
    """The config's own ML meta-filter settings, used to size the AI defaults."""
    payload = yaml.safe_load((path or BOT_CONFIG).read_text(encoding="utf-8")) or {}
    return dict(payload.get("ml") or {})


def summarise(specs: list[StrategySpec]) -> dict[str, Any]:
    evaluable = [spec for spec in specs if spec.evaluable]
    return {
        "total": len(specs),
        "evaluable": len(evaluable),
        "blocked_count": len(specs) - len(evaluable),
        "evaluable_ids": [spec.identifier for spec in evaluable],
        "blocked": {
            spec.identifier: list(spec.blocking_reasons) for spec in specs if not spec.evaluable
        },
        "documented_positive": [
            spec.identifier
            for spec in specs
            if spec.documented.profit_factor is not None and spec.documented.profit_factor > 1.0
        ],
    }
