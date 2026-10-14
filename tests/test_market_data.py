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
