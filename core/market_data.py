from __future__ import annotations

from core.models import (
    DEFAULT_CANDLE_COUNT,
    DEFAULT_TIMEFRAME,
    Candle,
    SymbolTick,
)
from core.mt5_connector import WATCHLIST, Mt5Connector


class MarketDataService:
    def __init__(self, connector: Mt5Connector) -> None:
        self._connector = connector
        self._latest_ticks: dict[str, SymbolTick] = {}
        self._candles: dict[tuple[str, str], list[Candle]] = {}

    def get_latest_tick(self, symbol: str) -> SymbolTick:
        tick = self._connector.get_symbol_tick(symbol)
        self._latest_ticks[symbol] = tick
        return tick

    def get_cached_tick(self, symbol: str) -> SymbolTick | None:
        return self._latest_ticks.get(symbol)

    def watchlist(self) -> tuple[str, ...]:
        return WATCHLIST

    def get_candles(
        self,
        symbol: str,
        timeframe: str = DEFAULT_TIMEFRAME,
        count: int = DEFAULT_CANDLE_COUNT,
    ) -> list[Candle]:
        candles = self._connector.get_ohlc(symbol, timeframe, count)
        self._candles[(symbol, timeframe)] = candles
        return candles

    def get_cached_candles(
        self, symbol: str, timeframe: str = DEFAULT_TIMEFRAME
    ) -> list[Candle] | None:
        return self._candles.get((symbol, timeframe))
