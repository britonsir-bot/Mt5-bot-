from core.models import RiskProfile, TradeRequest


def test_trade_request_defaults():
    request = TradeRequest(symbol="EURUSD", side="buy", volume=0.10)
    profile = RiskProfile.default()
    assert request.stop_loss is None
    assert profile.max_lot_size == 1.0
