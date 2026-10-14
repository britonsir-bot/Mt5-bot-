from __future__ import annotations

import pytest

from core.exceptions import ConnectorError, OrderExecutionError
from core.models import TradeRequest
from core.mt5_connector import MetaTrader5Connector

FULL_REQUEST = TradeRequest(
    symbol="EURUSD",
    side="buy",
    volume=0.10,
    stop_loss=1.0900,
    take_profit=1.1100,
    magic_number=7,
    comment="entry",
)


def connect(install_fake_mt5, **options):
    fake = install_fake_mt5(**options)
    return MetaTrader5Connector(), fake


def test_get_account_info_maps_broker_fields(install_fake_mt5):
    connector, _ = connect(install_fake_mt5)
    snapshot = connector.get_account_info()
    assert snapshot.login == "999888"
    assert snapshot.server == "ICMarkets-Live"
    assert snapshot.free_margin == pytest.approx(5000.0)
    assert snapshot.connected is True


def test_get_symbol_tick_reports_a_session_failure_not_a_symbol_failure(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, initialize_result=False)
    with pytest.raises(ConnectorError) as excinfo:
        connector.get_symbol_tick("EURUSD")
    assert "session" in str(excinfo.value).lower()


def test_get_symbol_tick_normalises_the_tick(install_fake_mt5):
    connector, _ = connect(install_fake_mt5)
    tick = connector.get_symbol_tick("EURUSD")
    assert (tick.bid, tick.ask) == (1.1000, 1.1002)
    assert tick.spread == pytest.approx(0.0002)
    assert tick.volume == 120


def test_send_order_builds_a_deal_request(install_fake_mt5):
    connector, fake = connect(install_fake_mt5, retcode=10009, order=555, price=1.1002)
    result = connector.send_order(FULL_REQUEST)
    payload = fake.sent_orders[0]
    assert payload["action"] == fake.TRADE_ACTION_DEAL
    assert payload["symbol"] == "EURUSD"
    assert payload["type"] == fake.ORDER_TYPE_BUY
    assert payload["price"] == pytest.approx(1.1002)
    assert payload["volume"] == pytest.approx(0.10)
    assert payload["sl"] == pytest.approx(1.0900)
    assert payload["tp"] == pytest.approx(1.1100)
    assert payload["magic"] == 7
    assert payload["comment"] == "entry"
    assert payload["type_time"] == fake.ORDER_TIME_GTC
    assert payload["type_filling"] == fake.ORDER_FILLING_FOK
    assert result.accepted is True
    assert result.order_id == "555"


def test_send_order_omits_absent_protection_levels(install_fake_mt5):
    connector, fake = connect(install_fake_mt5)
    connector.send_order(TradeRequest(symbol="EURUSD", side="sell", volume=0.10))
    payload = fake.sent_orders[0]
    assert "sl" not in payload
    assert "tp" not in payload


def test_a_sell_order_is_priced_at_the_bid(install_fake_mt5):
    connector, fake = connect(install_fake_mt5)
    connector.send_order(TradeRequest(symbol="EURUSD", side="sell", volume=0.10))
    payload = fake.sent_orders[0]
    assert payload["type"] == fake.ORDER_TYPE_SELL
    assert payload["price"] == pytest.approx(1.1000)


def test_send_order_requires_a_session(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, initialize_result=False)
    with pytest.raises(ConnectorError) as excinfo:
        connector.send_order(FULL_REQUEST)
    assert "session" in str(excinfo.value).lower()


def test_rejected_order_is_reported_with_the_retcode(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, retcode=10016, order=0, comment="Invalid stops")
    result = connector.send_order(FULL_REQUEST)
    assert result.accepted is False
    assert "10016" in result.message
    assert "Invalid stops" in result.message
    assert result.order_id is None


def test_missing_order_result_raises(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, order_result_none=True)
    with pytest.raises(OrderExecutionError):
        connector.send_order(FULL_REQUEST)


def test_volume_must_align_with_the_lot_step(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, volume_step=0.01)
    with pytest.raises(OrderExecutionError):
        connector.send_order(TradeRequest(symbol="EURUSD", side="buy", volume=0.105))


def test_volume_below_the_minimum_is_rejected(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, volume_min=0.10)
    with pytest.raises(OrderExecutionError):
        connector.send_order(TradeRequest(symbol="EURUSD", side="buy", volume=0.05))


def test_volume_above_the_maximum_is_rejected(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, volume_max=1.0)
    with pytest.raises(OrderExecutionError):
        connector.send_order(TradeRequest(symbol="EURUSD", side="buy", volume=5.0))


def test_ioc_filling_is_used_when_fok_is_unsupported(install_fake_mt5):
    connector, fake = connect(install_fake_mt5, filling_mode=2)
    connector.send_order(FULL_REQUEST)
    assert fake.sent_orders[0]["type_filling"] == fake.ORDER_FILLING_IOC


def test_return_filling_is_used_when_no_flag_is_advertised(install_fake_mt5):
    connector, fake = connect(install_fake_mt5, filling_mode=0)
    connector.send_order(FULL_REQUEST)
    assert fake.sent_orders[0]["type_filling"] == fake.ORDER_FILLING_RETURN


def test_a_hidden_symbol_is_added_to_market_watch(install_fake_mt5):
    connector, fake = connect(install_fake_mt5, visible=False)
    connector.send_order(FULL_REQUEST)
    assert fake.selected == [("EURUSD", True)]


def test_an_unknown_symbol_is_reported(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, symbol_info_none=True)
    with pytest.raises(ConnectorError):
        connector.send_order(FULL_REQUEST)


def test_a_missing_tick_is_reported(install_fake_mt5):
    connector, _ = connect(install_fake_mt5, tick_available=False)
    with pytest.raises(ConnectorError):
        connector.send_order(FULL_REQUEST)


def test_disconnect_only_shuts_down_an_active_session(install_fake_mt5):
    connector, fake = connect(install_fake_mt5)
    connector.disconnect()
    assert fake.shutdown_calls == 0
    connector.connect()
    connector.disconnect()
    assert fake.shutdown_calls == 1
