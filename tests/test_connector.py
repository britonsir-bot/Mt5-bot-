from __future__ import annotations

from core.account_service import AccountService
from core.models import TradeRequest
from core.mt5_connector import MockMt5Connector, build_connector


def test_account_service_returns_mock_snapshot():
    service = AccountService(MockMt5Connector())
    snapshot = service.get_account_snapshot()
    assert snapshot.connected is True
    assert snapshot.login == "demo"


def test_mock_connector_self_connects_on_demand():
    connector = MockMt5Connector()
    assert connector.is_connected() is False
    connector.get_symbol_tick("EURUSD")
    assert connector.is_connected() is True


def test_mock_orders_are_flagged_as_simulated():
    result = MockMt5Connector().send_order(
        TradeRequest(symbol="EURUSD", side="buy", volume=0.10)
    )
    assert result.accepted is True
    assert result.raw_response["simulated"] is True


def test_build_connector_returns_a_connected_mock():
    connector = build_connector(use_mock=True)
    assert connector.is_connected() is True


def test_mock_quotes_are_per_symbol_and_stable():
    connector = MockMt5Connector()
    eurusd = connector.get_symbol_tick("EURUSD")
    gold = connector.get_symbol_tick("XAUUSD")
    assert eurusd.bid != gold.bid
    assert (eurusd.digits, gold.digits) == (5, 2)
    assert connector.get_symbol_tick("EURUSD").bid == eurusd.bid


def test_mock_quotes_fall_back_for_unknown_symbols():
    tick = MockMt5Connector().get_symbol_tick("ZZZUSD")
    assert tick.digits == 5
    assert tick.ask > tick.bid > 0


def test_mock_ohlc_is_deterministic_and_flagged_simulated():
    first = MockMt5Connector().get_ohlc("EURUSD", "M15", 50)
    second = MockMt5Connector().get_ohlc("EURUSD", "M15", 50)
    assert len(first) == 50
    assert [candle.close for candle in first] == [candle.close for candle in second]
    assert all(candle.simulated for candle in first)
    assert all(candle.low <= candle.open <= candle.high for candle in first)
    assert all(candle.low <= candle.close <= candle.high for candle in first)


def test_mock_ohlc_ends_at_the_quoted_price():
    connector = MockMt5Connector()
    candles = connector.get_ohlc("EURUSD", "M15", 20)
    assert candles[-1].close == connector.get_symbol_tick("EURUSD").bid


def test_mock_ohlc_is_ordered_oldest_first():
    candles = MockMt5Connector().get_ohlc("EURUSD", "H1", 10)
    stamps = [candle.timestamp for candle in candles]
    assert stamps == sorted(stamps)
