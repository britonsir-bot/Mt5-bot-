from __future__ import annotations

import pytest

from core.exceptions import OrderExecutionError, RiskViolationError
from core.models import RiskProfile, TradeRequest, TradeResult
from core.order_manager import OrderManager
from core.risk_manager import RiskManager

REQUEST = TradeRequest(symbol="EURUSD", side="buy", volume=0.10)
PROFILE = RiskProfile.default()
STATE = {
    "open_trade_count": 0,
    "daily_pnl": 0.0,
    "current_drawdown": 0.0,
    "equity": 10_000.0,
}


class StubConnector:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []

    def send_order(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class RecordingWriter:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def build(connector, writer=None):
    return OrderManager(
        connector=connector, risk_manager=RiskManager(), order_event_writer=writer
    )


def test_accepted_order_is_forwarded_and_recorded():
    connector = StubConnector(result=TradeResult(True, "42", "filled"))
    writer = RecordingWriter()
    result = build(connector, writer).submit_manual_trade(REQUEST, PROFILE, **STATE)
    assert result.accepted is True
    assert connector.requests == [REQUEST]
    assert [(event.status, event.reason) for event in writer.events] == [
        ("accepted", "filled")
    ]


def test_rejected_order_raises_before_reaching_the_broker():
    connector = StubConnector(result=TradeResult(True, "42", "filled"))
    writer = RecordingWriter()
    state = dict(STATE, open_trade_count=5)
    with pytest.raises(RiskViolationError):
        build(connector, writer).submit_manual_trade(REQUEST, PROFILE, **state)
    assert connector.requests == []
    assert writer.events[0].status == "rejected"


def test_connector_failure_is_recorded_before_propagating():
    connector = StubConnector(error=OrderExecutionError("broker offline"))
    writer = RecordingWriter()
    with pytest.raises(OrderExecutionError):
        build(connector, writer).submit_manual_trade(REQUEST, PROFILE, **STATE)
    assert [(event.status, event.reason) for event in writer.events] == [
        ("failed", "broker offline")
    ]


def test_broker_rejection_is_recorded_as_failed():
    connector = StubConnector(result=TradeResult(False, None, "retcode=10016"))
    writer = RecordingWriter()
    result = build(connector, writer).submit_manual_trade(REQUEST, PROFILE, **STATE)
    assert result.accepted is False
    assert writer.events[0].status == "failed"


def test_an_event_writer_is_optional():
    connector = StubConnector(result=TradeResult(True, "42", "filled"))
    result = build(connector).submit_manual_trade(REQUEST, PROFILE, **STATE)
    assert result.accepted is True
