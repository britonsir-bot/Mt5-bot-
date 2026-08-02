from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
import uuid

from core.exceptions import ConnectorError
from core.models import AccountSnapshot, SymbolTick, TradeRequest, TradeResult


class Mt5Connector(Protocol):
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def get_account_info(self) -> AccountSnapshot: ...
    def get_symbol_tick(self, symbol: str) -> SymbolTick: ...
    def send_order(self, request: TradeRequest) -> TradeResult: ...


class MockMt5Connector:
    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountSnapshot:
        if not self._connected:
            self.connect()
        return AccountSnapshot(
            login="demo",
            server="MockBroker-Demo",
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            free_margin=10000.0,
            connected=True,
            server_time=datetime.now(timezone.utc),
        )

    def get_symbol_tick(self, symbol: str) -> SymbolTick:
        if not self._connected:
            self.connect()
        return SymbolTick(
            symbol=symbol,
            bid=1.1000,
            ask=1.1002,
            spread=0.0002,
            volume=100,
            timestamp=datetime.now(timezone.utc),
        )

    def send_order(self, request: TradeRequest) -> TradeResult:
        if not self._connected:
            self.connect()
        order_id = f"MOCK-{uuid.uuid4().hex[:10]}"
        return TradeResult(
            accepted=True,
            order_id=order_id,
            message=f"Mock {request.side} order accepted for {request.symbol}",
            raw_response={
                "symbol": request.symbol,
                "side": request.side,
                "volume": request.volume,
                "order_id": order_id,
            },
        )


class MetaTrader5Connector:
    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError as exc:
            raise ConnectorError(
                "MetaTrader5 package is not available in this environment."
            ) from exc
        self._mt5 = mt5
        self._connected = False

    def connect(self) -> bool:
        self._connected = bool(self._mt5.initialize())
        return self._connected

    def disconnect(self) -> None:
        self._mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountSnapshot:
        if not self._connected and not self.connect():
            raise ConnectorError("Unable to initialize MetaTrader 5 session.")
        info = self._mt5.account_info()
        if info is None:
            raise ConnectorError("MetaTrader 5 did not return account info.")
        now = datetime.now(timezone.utc)
        return AccountSnapshot(
            login=str(info.login),
            server=info.server,
            balance=float(info.balance),
            equity=float(info.equity),
            margin=float(info.margin),
            free_margin=float(info.margin_free),
            connected=True,
            server_time=now,
        )

    def get_symbol_tick(self, symbol: str) -> SymbolTick:
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise ConnectorError(f"Could not load tick for symbol {symbol}.")
        return SymbolTick(
            symbol=symbol,
            bid=float(tick.bid),
            ask=float(tick.ask),
            spread=float(tick.ask - tick.bid),
            volume=int(getattr(tick, "volume", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    def send_order(self, request: TradeRequest) -> TradeResult:
        raise ConnectorError(
            "Live order execution is not implemented in this scaffold yet."
        )


def build_connector(use_mock: bool) -> Mt5Connector:
    if use_mock:
        connector = MockMt5Connector()
        connector.connect()
        return connector
    return MetaTrader5Connector()
