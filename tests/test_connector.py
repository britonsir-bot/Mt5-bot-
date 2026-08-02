from core.account_service import AccountService
from core.mt5_connector import MockMt5Connector


def test_account_service_returns_mock_snapshot():
    service = AccountService(MockMt5Connector())
    snapshot = service.get_account_snapshot()
    assert snapshot.connected is True
    assert snapshot.login == "demo"
