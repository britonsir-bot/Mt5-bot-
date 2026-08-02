from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any


@dataclass(slots=True)
class AccountProfile:
    profile_name: str
    login: str
    server: str
    terminal_path: str


@dataclass(slots=True)
class AccountSnapshot:
    login: str
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    connected: bool
    server_time: datetime


@dataclass(slots=True)
class SymbolTick:
    symbol: str
    bid: float
    ask: float
    spread: float
    volume: int
    timestamp: datetime


@dataclass(slots=True)
class TradeRequest:
    symbol: str
    side: str
    volume: float
    stop_loss: float | None = None
    take_profit: float | None = None
    magic_number: int = 0
    comment: str = ""


@dataclass(slots=True)
class TradeResult:
    accepted: bool
    order_id: str | None
    message: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskProfile:
    name: str
    max_daily_loss: float
    max_drawdown: float
    max_trades: int
    max_lot_size: float
    risk_percent: float
    daily_profit_target: float
    equity_protection: float
    allowed_start_time: time | None = None
    allowed_end_time: time | None = None

    @classmethod
    def default(cls, max_lot_size: float = 1.0) -> "RiskProfile":
        return cls(
            name="default",
            max_daily_loss=500.0,
            max_drawdown=1000.0,
            max_trades=5,
            max_lot_size=max_lot_size,
            risk_percent=1.0,
            daily_profit_target=1000.0,
            equity_protection=1000.0,
        )


@dataclass(slots=True)
class RiskCheckResult:
    allowed: bool
    reason: str


@dataclass(slots=True)
class OrderEvent:
    symbol: str
    side: str
    volume: float
    status: str
    reason: str
    created_at: datetime
