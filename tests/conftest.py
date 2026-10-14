from __future__ import annotations

import logging
import os
import sys
import types

import pytest

TRADE_RETCODE_DONE = 10009


class _SymbolInfo:
    def __init__(self, visible, filling_mode, volume_min, volume_max, volume_step):
        self.visible = visible
        self.filling_mode = filling_mode
        self.volume_min = volume_min
        self.volume_max = volume_max
        self.volume_step = volume_step


class _Tick:
    def __init__(self, bid, ask):
        self.bid = bid
        self.ask = ask
        self.volume = 120


class _AccountInfo:
    login = 999888
    server = "ICMarkets-Live"
    balance = 5000.0
    equity = 5100.0
    margin = 100.0
    margin_free = 5000.0


class _OrderResult:
    def __init__(self, retcode, order, deal, price, comment):
        self.retcode = retcode
        self.order = order
        self.deal = deal
        self.price = price
        self.comment = comment


class _FakeMt5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = TRADE_RETCODE_DONE

    _METHODS = (
        "initialize",
        "shutdown",
        "account_info",
        "symbol_info",
        "symbol_select",
        "symbol_info_tick",
        "order_send",
        "last_error",
    )

    def __init__(self, options: dict) -> None:
        self.initialize_result = options.get("initialize_result", True)
        self.symbol_info_none = options.get("symbol_info_none", False)
        self.order_result_none = options.get("order_result_none", False)
        self.select_result = options.get("select_result", True)
        self.initialized = False
        self.shutdown_calls = 0
        self.selected: list[tuple[str, bool]] = []
        self.sent_orders: list[dict] = []
        self._symbol = _SymbolInfo(
            visible=options.get("visible", True),
            filling_mode=options.get("filling_mode", 1),
            volume_min=options.get("volume_min", 0.01),
            volume_max=options.get("volume_max", 100.0),
            volume_step=options.get("volume_step", 0.01),
        )
        self._tick = (
            None
            if options.get("tick_available", True) is False
            else _Tick(options.get("bid", 1.1000), options.get("ask", 1.1002))
        )
        self._order_result = (
            None
            if self.order_result_none
            else _OrderResult(
                retcode=options.get("retcode", TRADE_RETCODE_DONE),
                order=options.get("order", 555),
                deal=options.get("order", 555),
                price=options.get("price", 1.1002),
                comment=options.get("comment", "ok"),
            )
        )

    def initialize(self, *args, **kwargs):
        self.initialized = bool(self.initialize_result)
        return self.initialize_result

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.initialized = False

    def account_info(self):
        return _AccountInfo() if self.initialized else None

    def symbol_info(self, symbol):
        return None if self.symbol_info_none else self._symbol

    def symbol_select(self, symbol, enable):
        self.selected.append((symbol, enable))
        return self.select_result

    def symbol_info_tick(self, symbol):
        return self._tick

    def order_send(self, payload):
        self.sent_orders.append(payload)
        return self._order_result

    def last_error(self):
        return (1, "fake-error")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("MT5_"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def reset_application_logger():
    yield
    logger = logging.getLogger("mt5_bot")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


@pytest.fixture
def install_fake_mt5(monkeypatch):
    def _install(**options):
        fake = _FakeMt5(options)
        module = types.ModuleType("MetaTrader5")
        for name, value in vars(_FakeMt5).items():
            if name.isupper():
                setattr(module, name, value)
        for name in _FakeMt5._METHODS:
            setattr(module, name, getattr(fake, name))
        module.fake = fake
        monkeypatch.setitem(sys.modules, "MetaTrader5", module)
        return fake

    return _install
