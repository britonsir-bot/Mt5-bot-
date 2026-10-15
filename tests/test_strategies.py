from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from core.models import Candle
from strategies import Backtester, SeriesProvider, load_specs, summarise
from strategies.rules import (
    Condition,
    ConditionGroup,
    UnsupportedConditionError,
    coerce_value,
    combine,
    condition_mask,
)
from strategies.series import UnknownSeriesError

START = datetime(2026, 1, 5, tzinfo=timezone.utc)


def candles_from_closes(closes, *, highs=None, lows=None, step_minutes=60, simulated=False):
    out = []
    for index, close in enumerate(closes):
        high = float(highs[index]) if highs is not None else float(close) + 0.5
        low = float(lows[index]) if lows is not None else float(close) - 0.5
        out.append(
            Candle(
                timestamp=START + timedelta(minutes=step_minutes * index),
                open=float(close),
                high=high,
                low=low,
                close=float(close),
                volume=100 + index,
                simulated=simulated,
            )
        )
    return out


def ramp(count=60, start=100.0, step=1.0):
    return [start + step * index for index in range(count)]


# ----------------------------------------------------------------------------
# series
# ----------------------------------------------------------------------------
def test_resolve_is_strict_for_unknown_fields():
    provider = SeriesProvider(candles_from_closes(ramp()))
    with pytest.raises(UnknownSeriesError):
        provider.resolve("parabolic_sar", "not_a_field")


def test_resolve_maps_known_fields():
    provider = SeriesProvider(candles_from_closes(ramp()))
    assert provider.resolve("supertrend", "direction") == "supertrend_direction"
    assert provider.resolve("ib_detect", "is_inside_bar") == "is_inside_bar"
    assert provider.resolve("parabolic_sar", "position") == "parabolic_sar_position"
    assert provider.resolve("ema_200", "value") == "ema_200"


def test_lowest_low_5_excludes_the_current_bar():
    """A close can never break a range low that includes its own bar."""
    lows = [10.0] * 10
    closes = [11.0] * 10
    candles = candles_from_closes(closes, lows=lows)
    provider = SeriesProvider(candles)
    lowest = provider.get("lowest_low_5")
    index = len(closes) - 1
    assert lowest[index] == pytest.approx(10.0)
    assert closes[index] > lowest[index]


def test_lowest_low_5_ignores_the_current_bars_low():
    candles = candles_from_closes([11.0] * 8, lows=[10.0] * 7 + [1.0])
    provider = SeriesProvider(candles)
    assert provider.get("lowest_low_5")[-1] == pytest.approx(10.0)


def test_previous_series_resolves():
    provider = SeriesProvider(candles_from_closes(ramp(10)))
    previous = provider.get("prev_close")
    assert np.isnan(previous[0])
    assert previous[5] == pytest.approx(provider.close[4])


def test_higher_timeframe_series_is_published_causally():
    provider = SeriesProvider(candles_from_closes(ramp(20)))
    htf = provider.get("ema_20_h4")
    assert np.isnan(htf[:3]).all()


def test_available_series_covers_every_config_reference():
    provider = SeriesProvider(candles_from_closes(ramp(30)))
    for spec in load_specs():
        assert spec.missing_series(provider) == (), spec.identifier


# ----------------------------------------------------------------------------
# rules
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "operator,expected",
    [("gt", False), ("gte", True), ("lt", False), ("lte", True), ("eq", True)],
)
def test_numeric_operators(operator, expected):
    provider = SeriesProvider(candles_from_closes([1.0, 2.0, 3.0, 4.0, 5.0]))
    condition = Condition("c", "price", operator, field="close", value=5.0)
    assert bool(condition_mask(condition, provider)[-1]) is expected


def test_relational_operators_discriminate():
    provider = SeriesProvider(candles_from_closes([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert bool(condition_mask(Condition("g", "price", "gt", field="close", value=4.0), provider)[-1])
    assert bool(condition_mask(Condition("l", "price", "lte", field="close", value=5.0), provider)[-1])
    assert not bool(condition_mask(Condition("x", "price", "lt", field="close", value=4.0), provider)[-1])


def test_previous_value_compares_a_series_with_its_own_history():
    provider = SeriesProvider(candles_from_closes([1.0, 2.0, 3.0, 2.0]))
    rising = Condition("r", "price", "gt", field="close", compare="prev_value")
    mask = condition_mask(rising, provider)
    assert list(mask[1:]) == [True, True, False]


def test_threshold_pct_scales_the_reference():
    provider = SeriesProvider(candles_from_closes([100.0, 99.5, 97.0]))
    condition = Condition(
        "c", "price", "lt", field="close", compare="prev_close", threshold_pct=-1.0
    )
    mask = condition_mask(condition, provider)
    assert list(mask[1:]) == [False, True]


def test_cross_above_against_a_scalar():
    provider = SeriesProvider(candles_from_closes([-2.0, -1.0, 1.0, 2.0]))
    condition = Condition("c", "price", "cross_above", field="close", value=0.0)
    mask = condition_mask(condition, provider)
    assert list(mask) == [False, False, True, False]


def test_cross_above_against_a_series():
    provider = SeriesProvider(candles_from_closes([1.0, 3.0, 2.0, 5.0]))
    provider._cache["reference"] = np.array([2.0, 2.0, 2.0, 4.0])
    condition = Condition("c", "price", "cross_above", field="close", compare_indicator="reference")
    mask = condition_mask(condition, provider)
    assert list(mask) == [False, True, False, True]


def test_between_bounds():
    provider = SeriesProvider(candles_from_closes([1.0, 5.0, 9.0]))
    condition = Condition("b", "price", "btwn", field="close", value_min=4.0, value_max=6.0)
    assert list(condition_mask(condition, provider)) == [False, True, False]


def test_calendar_day_of_week_uses_iso_weekday():
    provider = SeriesProvider(candles_from_closes([1.0] * 5, step_minutes=1440))
    condition = Condition("d", "calendar", "eq", field="day_of_week", value=1)
    mask = condition_mask(condition, provider)
    assert bool(mask[0]) is True  # 2026-01-05 is a Monday
    assert int(mask.sum()) == 1


def test_nan_never_satisfies_a_comparison():
    provider = SeriesProvider(candles_from_closes(ramp(30)))
    condition = Condition("c", "indicator", "lt", indicator="rsi_14", field="value", value=100.0)
    mask = condition_mask(condition, provider)
    assert not mask[:14].any()


def test_word_values_are_mapped_and_unknown_words_rejected():
    assert coerce_value("below") == 1.0
    assert coerce_value("above") == -1.0
    assert coerce_value(True) == 1.0
    with pytest.raises(UnsupportedConditionError):
        coerce_value("sideways")


def test_unsupported_condition_type_is_rejected():
    provider = SeriesProvider(candles_from_closes(ramp(10)))
    with pytest.raises(UnsupportedConditionError):
        condition_mask(Condition("x", "psychic", "gt", value=1.0), provider)


def test_group_operator_switches_between_and_or():
    provider = SeriesProvider(candles_from_closes([1.0, 2.0, 9.0]))
    high = Condition("h", "price", "gt", field="close", value=8.0)
    low = Condition("l", "price", "lt", field="close", value=1.5)
    assert combine(
        [condition_mask(high, provider), condition_mask(low, provider)], "AND", 3
    ).sum() == 0
    assert combine(
        [condition_mask(high, provider), condition_mask(low, provider)], "OR", 3
    ).sum() == 2


def test_empty_group_produces_no_signals():
    provider = SeriesProvider(candles_from_closes(ramp(10)))
    assert not combine([], "AND", provider.size).any()


# ----------------------------------------------------------------------------
# spec loading
# ----------------------------------------------------------------------------
def test_all_configs_load_and_are_classified():
    specs = load_specs()
    assert len(specs) == 16
    report = summarise(specs)
    assert report["evaluable"] + report["blocked_count"] == 16
    assert report["evaluable"] >= 14


def test_portfolio_strategy_is_blocked_with_a_reason():
    spec = next(s for s in load_specs() if s.identifier == "dual_momentum")
    assert spec.evaluable is False
    assert any("portfolio" in reason for reason in spec.blocking_reasons)


def test_fixed_percent_stop_reads_value_pct():
    """The configs express a fixed stop as value_pct; reading it wrong zeroed the stop."""
    spec = next(s for s in load_specs() if s.identifier == "macd_histogram")
    assert spec.risk.stop_loss.method == "fixed_pct"
    assert spec.risk.stop_loss.percent == pytest.approx(3.0)


def test_documented_stats_are_labelled_as_cited():
    spec = next(s for s in load_specs() if s.identifier == "supertrend_strategy")
    assert spec.documented.profit_factor is not None
    assert spec.documented.source
    assert spec.documented.backtest_period


# ----------------------------------------------------------------------------
# backtest
# ----------------------------------------------------------------------------
def _constant_spec(identifier: str = "probe"):
    return next(s for s in load_specs() if s.identifier == identifier)


def test_entries_fill_at_the_next_bar_open_not_the_signal_bar():
    """Causality: a signal on bar t must not fill at bar t's own price."""
    from strategies.spec import StrategySpec, StopSpec, RiskSpec
    from strategies.rules import Condition as C
    from strategies.rules import ConditionGroup as G

    entry = G("AND", (C("always", "price", "gt", field="close", value=0.0),))
    risk = RiskSpec(
        sizing_method="fixed_fraction",
        risk_per_trade_pct=1.0,
        stop_loss=StopSpec(True, "atr_multiple", 5, 2.0, 0.0),
        take_profit=StopSpec(False, "none", 14, 1.0, 0.0),
        trailing_stop=StopSpec(False, "none", 14, 1.0, 0.0),
    )
    spec = StrategySpec(
        identifier="probe", name="probe", category="test", description="",
        symbol="TEST", timeframe="H1", trade_direction="long_only", enabled=True,
        entry=entry, exit_signal=None, exit_method="time_exit", time_exit_bars=3, risk=risk,
    )
    closes = ramp(40, 100.0, 1.0)
    candles = candles_from_closes(closes)
    result = Backtester(initial_balance=10_000.0).run(spec, candles, minimum_history=10)
    assert result.metrics.trades > 0
    first = result.trades[0]
    assert first.entry_price == pytest.approx(candles[first.entry_index].open)
    assert first.entry_index >= 1


def test_metrics_are_consistent():
    spec = _constant_spec("macd_histogram")
    from core.mt5_connector import MockMt5Connector

    candles = MockMt5Connector().get_ohlc(spec.symbol, spec.timeframe, 1000)
    result = Backtester().run(spec, candles, data_source="simulated")
    metrics = result.metrics
    assert metrics.trades == len(result.trades)
    assert metrics.wins + metrics.losses == metrics.trades
    if metrics.trades:
        assert metrics.net_profit == pytest.approx(
            sum(trade.gross_pnl for trade in result.trades), abs=0.02
        )
        assert 0.0 <= metrics.win_rate_pct <= 100.0
        assert metrics.max_drawdown_pct >= 0.0
        assert len(result.equity_curve) == metrics.trades + 1


def test_low_volatility_data_is_reported_not_hidden():
    """A rule that needs a 1% daily move cannot fire on quiet data; say so."""
    spec = _constant_spec("turnaround_tuesday")
    from core.mt5_connector import MockMt5Connector

    candles = MockMt5Connector().get_ohlc(spec.symbol, spec.timeframe, 400)
    result = Backtester().run(spec, candles, data_source="simulated")
    assert result.metrics.trades == 0
    assert result.notes
    assert "per-condition bar counts" in result.notes[-1]


def test_stop_exit_never_loses_more_than_the_configured_risk():
    """A stop fills at the stop price, so a loss cannot exceed one initial R.

    A trailed stop that has moved past entry exits at a profit with reason
    ``stop``, which is why the bound is one-sided.
    """
    from core.mt5_connector import MockMt5Connector

    spec = _constant_spec("supertrend_strategy")
    candles = MockMt5Connector().get_ohlc(spec.symbol, spec.timeframe, 600)
    result = Backtester(initial_balance=10_000.0).run(spec, candles)
    stopped = [trade for trade in result.trades if trade.exit_reason == "stop"]
    assert stopped, "expected at least one stop exit"
    for trade in stopped:
        assert trade.r_multiple >= -1.05


def test_losing_trades_respect_the_risk_budget():
    from core.mt5_connector import MockMt5Connector

    spec = _constant_spec("supertrend_strategy")
    candles = MockMt5Connector().get_ohlc(spec.symbol, spec.timeframe, 600)
    result = Backtester(initial_balance=10_000.0).run(spec, candles)
    budget = 10_000.0 * spec.risk.risk_per_trade_pct / 100.0
    for trade in result.trades:
        assert trade.gross_pnl > -budget * 1.1


def test_short_history_is_refused_with_a_note():
    spec = _constant_spec("supertrend_strategy")
    candles = candles_from_closes(ramp(50))
    result = Backtester().run(spec, candles)
    assert result.metrics.trades == 0
    assert any("warm-up" in note for note in result.notes)


def test_simulated_data_is_flagged_on_the_result():
    from core.mt5_connector import MockMt5Connector

    spec = _constant_spec("supertrend_strategy")
    candles = MockMt5Connector().get_ohlc(spec.symbol, spec.timeframe, 300)
    assert all(candle.simulated for candle in candles)
    result = Backtester().run(spec, candles, data_source="simulated")
    assert result.simulated is True
    assert result.data_source == "simulated"


def test_result_is_deterministic():
    from core.mt5_connector import MockMt5Connector

    spec = _constant_spec("keltner_channel_breakout")
    candles = MockMt5Connector().get_ohlc(spec.symbol, spec.timeframe, 500)
    first = Backtester().run(spec, candles, data_source="simulated")
    second = Backtester().run(spec, candles, data_source="simulated")
    assert first.metrics == second.metrics


def test_blocked_strategies_are_not_run():
    from strategies.backtest import run_all

    specs = load_specs()
    blocked = [spec for spec in specs if not spec.evaluable]
    assert blocked
    candles = candles_from_closes(ramp(300))
    results = run_all(specs, candles, data_source="test")
    assert all(result.strategy_id not in {s.identifier for s in blocked} for result in results)
