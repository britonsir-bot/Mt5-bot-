from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

VALID_ORDER_SIDES = frozenset({"buy", "sell"})

TIMEFRAME_MINUTES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}
DEFAULT_TIMEFRAME = "M15"
DEFAULT_CANDLE_COUNT = 180
MAX_CANDLE_COUNT = 1000


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
    digits: int = 5


@dataclass(slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    simulated: bool = False


@dataclass(slots=True)
class TradeRequest:
    symbol: str
    side: str
    volume: float
    stop_loss: float | None = None
    take_profit: float | None = None
    magic_number: int = 0
    comment: str = ""

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.side = self.side.strip().lower()
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.side not in VALID_ORDER_SIDES:
            raise ValueError(
                f"side must be one of {sorted(VALID_ORDER_SIDES)}, got {self.side!r}"
            )
        if self.volume <= 0:
            raise ValueError("volume must be greater than zero")


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
