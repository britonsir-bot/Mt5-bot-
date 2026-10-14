from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
import uuid

from core.exceptions import ConnectorError, OrderExecutionError
from core.models import AccountSnapshot, SymbolTick, TradeRequest, TradeResult

DEFAULT_DEVIATION_POINTS = 20

_SYMBOL_FILLING_FOK = 1
_SYMBOL_FILLING_IOC = 2
_VOLUME_TOLERANCE = 1e-8


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
                "simulated": True,
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
        if self._connected:
            self._mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountSnapshot:
        self._ensure_connected()
        info = self._mt5.account_info()
        if info is None:
            raise ConnectorError("MetaTrader 5 did not return account info.")
        return AccountSnapshot(
            login=str(info.login),
            server=info.server,
            balance=float(info.balance),
            equity=float(info.equity),
            margin=float(info.margin),
            free_margin=float(info.margin_free),
            connected=True,
            server_time=datetime.now(timezone.utc),
        )

    def get_symbol_tick(self, symbol: str) -> SymbolTick:
        self._ensure_connected()
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
        self._ensure_connected()
        symbol_info = self._resolve_symbol(request.symbol)
        tick = self._mt5.symbol_info_tick(request.symbol)
        if tick is None:
            raise ConnectorError(f"Could not load tick for symbol {request.symbol}.")
        volume = self._validate_volume(request, symbol_info)

        if request.side == "buy":
            order_type = self._mt5.ORDER_TYPE_BUY
            price = float(tick.ask)
        else:
            order_type = self._mt5.ORDER_TYPE_SELL
            price = float(tick.bid)
        if price <= 0:
            raise OrderExecutionError(
                f"Refusing to send a {request.side} order for {request.symbol}: "
                f"invalid market price {price}."
            )

        payload: dict[str, Any] = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": DEFAULT_DEVIATION_POINTS,
            "magic": int(request.magic_number),
            "comment": request.comment,
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._select_filling_mode(symbol_info),
        }
        if request.stop_loss is not None:
            payload["sl"] = float(request.stop_loss)
        if request.take_profit is not None:
            payload["tp"] = float(request.take_profit)

        response = self._mt5.order_send(payload)
        if response is None:
            raise OrderExecutionError(
                f"MetaTrader 5 order_send returned no result: {self._mt5.last_error()}."
            )

        raw_response = {
            "retcode": getattr(response, "retcode", None),
            "deal": getattr(response, "deal", None),
            "order": getattr(response, "order", None),
            "volume": getattr(response, "volume", None),
            "price": getattr(response, "price", None),
            "comment": getattr(response, "comment", None),
            "request": payload,
        }
        order_id = str(raw_response["order"]) if raw_response["order"] else None
        if raw_response["retcode"] != self._mt5.TRADE_RETCODE_DONE:
            return TradeResult(
                accepted=False,
                order_id=order_id,
                message=(
                    f"MetaTrader 5 rejected the {request.side} order for "
                    f"{request.symbol}: retcode={raw_response['retcode']} "
                    f"({raw_response['comment']})."
                ),
                raw_response=raw_response,
            )
        return TradeResult(
            accepted=True,
            order_id=order_id,
            message=(
                f"{request.side} {volume} {request.symbol} executed at "
                f"{raw_response['price']}."
            ),
            raw_response=raw_response,
        )

    def _ensure_connected(self) -> None:
        if not self._connected and not self.connect():
            raise ConnectorError("Unable to initialize MetaTrader 5 session.")

    def _resolve_symbol(self, symbol: str) -> Any:
        info = self._mt5.symbol_info(symbol)
        if info is None:
            raise ConnectorError(f"Unknown symbol {symbol!r}.")
        if not getattr(info, "visible", True):
            if not self._mt5.symbol_select(symbol, True):
                raise ConnectorError(f"Could not add {symbol!r} to Market Watch.")
            info = self._mt5.symbol_info(symbol)
            if info is None:
                raise ConnectorError(f"Could not load symbol info for {symbol!r}.")
        return info

    def _validate_volume(self, request: TradeRequest, symbol_info: Any) -> float:
        volume = float(request.volume)
        minimum = float(getattr(symbol_info, "volume_min", 0) or 0)
        maximum = float(getattr(symbol_info, "volume_max", 0) or 0)
        step = float(getattr(symbol_info, "volume_step", 0) or 0)
        if minimum and volume < minimum:
            raise OrderExecutionError(
                f"Volume {volume} is below the minimum of {minimum} for {request.symbol}."
            )
        if maximum and volume > maximum:
            raise OrderExecutionError(
                f"Volume {volume} exceeds the maximum of {maximum} for {request.symbol}."
            )
        if step:
            steps = round(volume / step)
            normalised = steps * step
            if steps < 1 or abs(normalised - volume) > max(step * 1e-6, _VOLUME_TOLERANCE):
                raise OrderExecutionError(
                    f"Volume {volume} is not a multiple of the {step} lot step for "
                    f"{request.symbol}."
                )
            volume = round(normalised, 8)
        return volume

    def _select_filling_mode(self, symbol_info: Any) -> int:
        supported = int(getattr(symbol_info, "filling_mode", 0) or 0)
        if supported & _SYMBOL_FILLING_FOK:
            return int(self._mt5.ORDER_FILLING_FOK)
        if supported & _SYMBOL_FILLING_IOC:
            return int(self._mt5.ORDER_FILLING_IOC)
        return int(self._mt5.ORDER_FILLING_RETURN)


def build_connector(use_mock: bool) -> Mt5Connector:
    if use_mock:
        connector = MockMt5Connector()
        connector.connect()
        return connector
    return MetaTrader5Connector()
