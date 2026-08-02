from __future__ import annotations

from core.models import AccountSnapshot
from core.mt5_connector import Mt5Connector


class AccountService:
    def __init__(self, connector: Mt5Connector) -> None:
        self._connector = connector

    def get_account_snapshot(self) -> AccountSnapshot:
        return self._connector.get_account_info()
