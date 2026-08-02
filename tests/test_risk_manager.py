from core.models import RiskProfile, TradeRequest
from core.risk_manager import RiskManager


def test_risk_manager_rejects_oversized_volume():
    manager = RiskManager()
    profile = RiskProfile.default(max_lot_size=0.50)
    request = TradeRequest(symbol="EURUSD", side="buy", volume=1.00)
    result = manager.evaluate(request, profile, open_trade_count=0)
    assert result.allowed is False
    assert "max lot size" in result.reason.lower()
