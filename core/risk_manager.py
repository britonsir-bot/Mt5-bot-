from __future__ import annotations

from datetime import UTC, date, datetime, time, tzinfo

from core.models import RiskCheckResult, RiskProfile, TradeRequest

_SESSION_ANCHOR = date(2000, 1, 1)


def _wall_clock_in(moment: datetime, reference: tzinfo) -> time:
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=reference)
    return aware.astimezone(reference).time()


def _session_time_in(value: time, reference: tzinfo) -> time:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=reference)
    return datetime.combine(_SESSION_ANCHOR, aware).astimezone(reference).time()


class RiskManager:
    """Evaluates a trade request against a risk profile.

    All account-state arguments are required so a caller cannot silently skip a
    limit by omitting one. A threshold of zero disables the corresponding check.
    Session windows are compared as wall-clock times in the window's timezone,
    falling back to the wall clock of ``now`` when the window carries no timezone.
    """

    def evaluate(
        self,
        request: TradeRequest,
        profile: RiskProfile,
        *,
        open_trade_count: int,
        daily_pnl: float,
        current_drawdown: float,
        equity: float,
        now: datetime | None = None,
    ) -> RiskCheckResult:
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
        if profile.equity_protection > 0 and equity <= profile.equity_protection:
            return RiskCheckResult(False, "Equity protection level has been reached.")
        if profile.daily_profit_target > 0 and daily_pnl >= profile.daily_profit_target:
            return RiskCheckResult(
                False, "Daily profit target has been reached; trading is halted for the day."
            )
        if profile.allowed_start_time and profile.allowed_end_time:
            moment = now or datetime.now(UTC)
            if not self._within_session(
                moment, profile.allowed_start_time, profile.allowed_end_time
            ):
                return RiskCheckResult(False, "Trading is outside the allowed time window.")
        return RiskCheckResult(True, "Approved")

    @staticmethod
    def _within_session(moment: datetime, start: time, end: time) -> bool:
        reference = start.tzinfo or end.tzinfo
        if reference is None:
            current = moment.replace(tzinfo=None).time()
            window_start = start.replace(tzinfo=None)
            window_end = end.replace(tzinfo=None)
        else:
            current = _wall_clock_in(moment, reference)
            window_start = _session_time_in(start, reference)
            window_end = _session_time_in(end, reference)
        if window_start <= window_end:
            return window_start <= current <= window_end
        return current >= window_start or current <= window_end
