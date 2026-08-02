from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models import SymbolTick


@dataclass(slots=True)
class StrategyDefinition:
    name: str
    symbol: str
    timeframe: str
    enabled: bool = True
    rules: list[dict[str, Any]] = field(default_factory=list)


class StrategyEngine:
    def __init__(self) -> None:
        self._strategies: list[StrategyDefinition] = []

    def register(self, strategy: StrategyDefinition) -> None:
        self._strategies.append(strategy)

    def evaluate_tick(self, tick: SymbolTick) -> list[str]:
        signals: list[str] = []
        for strategy in self._strategies:
            if strategy.enabled and strategy.symbol == tick.symbol:
                signals.append(f"{strategy.name}: no-op")
        return signals
