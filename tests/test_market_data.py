from __future__ import annotations

from core.market_data import MarketDataService
from core.mt5_connector import MockMt5Connector


def test_cache_is_empty_before_the_first_read():
    service = MarketDataService(MockMt5Connector())
    assert service.get_cached_tick("EURUSD") is None


def test_latest_tick_populates_the_cache():
    service = MarketDataService(MockMt5Connector())
    tick = service.get_latest_tick("EURUSD")
    assert service.get_cached_tick("EURUSD") is tick
    assert tick.symbol == "EURUSD"


def test_cache_is_keyed_per_symbol():
    service = MarketDataService(MockMt5Connector())
    service.get_latest_tick("EURUSD")
    assert service.get_cached_tick("XAUUSD") is None


def test_watchlist_is_exposed():
    service = MarketDataService(MockMt5Connector())
    assert "EURUSD" in service.watchlist()
    assert len(service.watchlist()) >= 5


def test_candles_are_cached_per_symbol_and_timeframe():
    service = MarketDataService(MockMt5Connector())
    assert service.get_cached_candles("EURUSD", "M15") is None
    candles = service.get_candles("EURUSD", "M15", 30)
    assert service.get_cached_candles("EURUSD", "M15") is candles
    assert service.get_cached_candles("EURUSD", "H1") is None
    assert len(candles) == 30
