from __future__ import annotations

from core.models import SymbolTick
from core.mt5_connector import Mt5Connector


class MarketDataService:
    def __init__(self, connector: Mt5Connector) -> None:
        self._connector = connector
        self._latest_ticks: dict[str, SymbolTick] = {}

    def get_latest_tick(self, symbol: str) -> SymbolTick:
        tick = self._connector.get_symbol_tick(symbol)
        self._latest_ticks[symbol] = tick
        return tick

    def get_cached_tick(self, symbol: str) -> SymbolTick | None:
        return self._latest_ticks.get(symbol)
