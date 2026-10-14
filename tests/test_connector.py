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
