from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone

import pytest

from core.models import RiskProfile, TradeRequest
from core.risk_manager import RiskManager

DEFAULT_REQUEST = TradeRequest(symbol="EURUSD", side="buy", volume=0.10)
DEFAULT_STATE = {
    "open_trade_count": 0,
    "daily_pnl": 0.0,
    "current_drawdown": 0.0,
    "equity": 10_000.0,
}


def evaluate(profile, request=DEFAULT_REQUEST, **overrides):
    state = dict(DEFAULT_STATE)
    state.update(overrides)
    return RiskManager().evaluate(request, profile, **state)


def session_profile(start, end, **overrides):
    profile = RiskProfile.default(**overrides)
    profile.allowed_start_time = start
    profile.allowed_end_time = end
    return profile


def test_approves_a_request_within_every_limit():
    assert evaluate(RiskProfile.default()).allowed is True


def test_rejects_oversized_volume():
    profile = RiskProfile.default(max_lot_size=0.50)
    request = TradeRequest(symbol="EURUSD", side="buy", volume=1.00)
    result = evaluate(profile, request)
    assert result.allowed is False
    assert "max lot size" in result.reason.lower()


def test_rejects_non_positive_volume():
    request = TradeRequest(symbol="EURUSD", side="buy", volume=0.10)
    request.volume = 0.0
    result = evaluate(RiskProfile.default(), request)
    assert result.allowed is False
    assert "greater than zero" in result.reason


def test_rejects_when_concurrent_trade_limit_is_reached():
    result = evaluate(RiskProfile.default(), open_trade_count=5)
    assert result.allowed is False
    assert "concurrent trades" in result.reason


def test_rejects_when_max_daily_loss_is_reached():
    result = evaluate(RiskProfile.default(), daily_pnl=-500.0)
    assert result.allowed is False
    assert "daily loss" in result.reason


def test_rejects_when_max_drawdown_is_triggered():
    result = evaluate(RiskProfile.default(), current_drawdown=1000.0)
    assert result.allowed is False
    assert "drawdown" in result.reason


def test_rejects_when_equity_protection_is_breached():
    result = evaluate(RiskProfile.default(), equity=900.0)
    assert result.allowed is False
    assert "equity protection" in result.reason.lower()


def test_equity_protection_of_zero_disables_the_check():
    profile = RiskProfile.default()
    profile.equity_protection = 0.0
    assert evaluate(profile, equity=0.0).allowed is True


def test_rejects_when_daily_profit_target_is_reached():
    result = evaluate(RiskProfile.default(), daily_pnl=1000.0)
    assert result.allowed is False
    assert "profit target" in result.reason


def test_daily_profit_target_of_zero_disables_the_check():
    profile = RiskProfile.default()
    profile.daily_profit_target = 0.0
    assert evaluate(profile, daily_pnl=50_000.0).allowed is True


def test_session_window_allows_inside_and_rejects_outside():
    profile = session_profile(time(8, 0), time(17, 0))
    assert evaluate(profile, now=datetime(2026, 10, 15, 12, 0, tzinfo=UTC)).allowed is True
    assert evaluate(profile, now=datetime(2026, 10, 15, 20, 0, tzinfo=UTC)).allowed is False


def test_overnight_session_window_authorises_every_hour_inside_it():
    profile = session_profile(time(22, 0), time(2, 0))
    for hour in (22, 23, 0, 1, 2):
        moment = datetime(2026, 10, 15, hour, 0, tzinfo=UTC)
        assert evaluate(profile, now=moment).allowed is True, hour


def test_overnight_session_window_rejects_hours_outside_it():
    profile = session_profile(time(22, 0), time(2, 0))
    for hour in (3, 12, 21):
        moment = datetime(2026, 10, 15, hour, 0, tzinfo=UTC)
        assert evaluate(profile, now=moment).allowed is False, hour


def test_timezone_aware_window_is_evaluated_without_raising():
    profile = session_profile(time(8, 0, tzinfo=UTC), time(17, 0, tzinfo=UTC))
    assert evaluate(profile, now=datetime(2026, 10, 15, 12, 0, tzinfo=UTC)).allowed is True
    assert evaluate(profile, now=datetime(2026, 10, 15, 20, 0, tzinfo=UTC)).allowed is False


def test_timezone_aware_window_converts_now_into_the_window_timezone():
    singapore = timezone(timedelta(hours=8))
    profile = session_profile(time(8, 0, tzinfo=singapore), time(17, 0, tzinfo=singapore))
    assert evaluate(profile, now=datetime(2026, 10, 15, 4, 0, tzinfo=UTC)).allowed is True
    assert evaluate(profile, now=datetime(2026, 10, 15, 23, 0, tzinfo=UTC)).allowed is False


def test_naive_moment_against_aware_window_does_not_raise():
    profile = session_profile(time(8, 0, tzinfo=UTC), time(17, 0, tzinfo=UTC))
    assert evaluate(profile, now=datetime(2026, 10, 15, 12, 0)).allowed is True


@pytest.mark.parametrize("name", ["open_trade_count", "daily_pnl", "current_drawdown", "equity"])
def test_account_state_arguments_are_mandatory(name):
    state = dict(DEFAULT_STATE)
    state.pop(name)
    with pytest.raises(TypeError):
        RiskManager().evaluate(DEFAULT_REQUEST, RiskProfile.default(), **state)
