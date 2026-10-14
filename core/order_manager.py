from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from core.exceptions import Mt5BotError, RiskViolationError
from core.models import OrderEvent, RiskProfile, TradeRequest, TradeResult
from core.mt5_connector import Mt5Connector
from core.risk_manager import RiskManager


class OrderEventWriter(Protocol):
    def record(self, event: OrderEvent) -> None: ...


class OrderManager:
    def __init__(
        self,
        connector: Mt5Connector,
        risk_manager: RiskManager,
        order_event_writer: OrderEventWriter | None = None,
    ) -> None:
        self._connector = connector
        self._risk_manager = risk_manager
        self._order_event_writer = order_event_writer

    def submit_manual_trade(
        self,
        request: TradeRequest,
        risk_profile: RiskProfile,
        *,
        open_trade_count: int,
        daily_pnl: float,
        current_drawdown: float,
        equity: float,
    ) -> TradeResult:
        decision = self._risk_manager.evaluate(
            request=request,
            profile=risk_profile,
            open_trade_count=open_trade_count,
            daily_pnl=daily_pnl,
            current_drawdown=current_drawdown,
            equity=equity,
        )
        if not decision.allowed:
            self._record_event(request, "rejected", decision.reason)
            raise RiskViolationError(decision.reason)

        try:
            result = self._connector.send_order(request)
        except Mt5BotError as exc:
            self._record_event(request, "failed", str(exc))
            raise

        status = "accepted" if result.accepted else "failed"
        self._record_event(request, status, result.message)
        return result

    def _record_event(self, request: TradeRequest, status: str, reason: str) -> None:
        if self._order_event_writer is None:
            return
        self._order_event_writer.record(
            OrderEvent(
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                status=status,
                reason=reason,
                created_at=datetime.now(timezone.utc),
            )
        )
