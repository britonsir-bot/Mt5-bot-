from __future__ import annotations

from datetime import datetime, timezone

from core.models import SymbolTick
from core.strategy_engine import StrategyDefinition, StrategyEngine


def build_tick(symbol="EURUSD"):
    return SymbolTick(
        symbol=symbol,
        bid=1.1000,
        ask=1.1002,
        spread=0.0002,
        volume=10,
        timestamp=datetime.now(timezone.utc),
    )


def test_registered_strategies_are_tracked():
    engine = StrategyEngine()
    strategy = StrategyDefinition(name="orb", symbol="EURUSD", timeframe="M15")
    engine.register(strategy)
    assert engine.strategies() == [strategy]


def test_no_placeholder_signals_are_emitted():
    engine = StrategyEngine()
    engine.register(StrategyDefinition(name="orb", symbol="EURUSD", timeframe="M15"))
    assert engine.evaluate_tick(build_tick()) == []
    assert engine.evaluate_tick(build_tick("XAUUSD")) == []


def test_the_registry_is_not_shared_between_engines():
    first = StrategyEngine()
    first.register(StrategyDefinition(name="orb", symbol="EURUSD", timeframe="M15"))
    assert StrategyEngine().strategies() == []
