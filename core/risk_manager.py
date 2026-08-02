from __future__ import annotations

from datetime import UTC, datetime

from core.models import RiskCheckResult, RiskProfile, TradeRequest


class RiskManager:
    def evaluate(
        self,
        request: TradeRequest,
        profile: RiskProfile,
        open_trade_count: int,
        daily_pnl: float = 0.0,
        current_drawdown: float = 0.0,
        now: datetime | None = None,
    ) -> RiskCheckResult:
        current_time = (now or datetime.now(UTC)).time()

        if request.volume <= 0:
            return RiskCheckResult(False, "Trade volume must be greater than zero.")
        if request.volume > profile.max_lot_size:
            return RiskCheckResult(
                False,
                f"Requested volume exceeds max lot size of {profile.max_lot_size}.",
            )
        if open_trade_count >= profile.max_trades:
            return RiskCheckResult(False, "Maximum number of concurrent trades reached.")
        if daily_pnl <= -abs(profile.max_daily_loss):
            return RiskCheckResult(False, "Max daily loss has been reached.")
        if current_drawdown >= profile.max_drawdown:
            return RiskCheckResult(False, "Max drawdown protection has been triggered.")
        if (
            profile.allowed_start_time
            and profile.allowed_end_time
            and not profile.allowed_start_time <= current_time <= profile.allowed_end_time
        ):
            return RiskCheckResult(False, "Trading is outside the allowed time window.")
        return RiskCheckResult(True, "Approved")
