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
    """Registry for strategy definitions.

    Rule evaluation is not implemented in this scaffold, so ``evaluate_tick``
    returns no signals rather than a placeholder signal that a caller might act on.
    """

    def __init__(self) -> None:
        self._strategies: list[StrategyDefinition] = []

    def register(self, strategy: StrategyDefinition) -> None:
        self._strategies.append(strategy)

    def strategies(self) -> list[StrategyDefinition]:
        return list(self._strategies)

    def evaluate_tick(self, tick: SymbolTick) -> list[str]:
        return []
