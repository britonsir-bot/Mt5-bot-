from __future__ import annotations

import pytest

from core.models import RiskProfile, TradeRequest


def test_trade_request_defaults():
    request = TradeRequest(symbol="EURUSD", side="buy", volume=0.10)
    profile = RiskProfile.default()
    assert request.stop_loss is None
    assert request.take_profit is None
    assert request.magic_number == 0
    assert profile.max_lot_size == 1.0


def test_trade_request_normalises_symbol_and_side():
    request = TradeRequest(symbol=" eurusd ", side=" BUY ", volume=0.10)
    assert request.symbol == "EURUSD"
    assert request.side == "buy"


@pytest.mark.parametrize("side", ["buuy", "", "hold", "selll", "long"])
def test_trade_request_rejects_unknown_sides(side):
    with pytest.raises(ValueError):
        TradeRequest(symbol="EURUSD", side=side, volume=0.10)


def test_trade_request_rejects_a_blank_symbol():
    with pytest.raises(ValueError):
        TradeRequest(symbol="   ", side="buy", volume=0.10)


@pytest.mark.parametrize("volume", [0.0, -0.1])
def test_trade_request_rejects_non_positive_volume(volume):
    with pytest.raises(ValueError):
        TradeRequest(symbol="EURUSD", side="buy", volume=volume)


def test_risk_profile_does_not_advertise_an_unenforceable_limit():
    assert "risk_percent" not in RiskProfile.__slots__


def test_risk_profile_default_is_fully_populated():
    profile = RiskProfile.default(max_lot_size=0.25)
    assert profile.name == "default"
    assert profile.max_lot_size == 0.25
    assert profile.equity_protection > 0
    assert profile.daily_profit_target > 0
    assert profile.allowed_start_time is None
    assert profile.allowed_end_time is None
