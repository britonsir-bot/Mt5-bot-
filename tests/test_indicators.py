from __future__ import annotations

import pytest

from core.indicators import ema, rsi, sma


def test_sma_uses_the_requested_window():
    assert sma([1.0, 2.0, 3.0, 4.0, 5.0], 3) == pytest.approx(4.0)


def test_sma_rejects_short_series():
    with pytest.raises(ValueError):
        sma([1.0, 2.0], 3)


def test_sma_rejects_non_positive_period():
    with pytest.raises(ValueError):
        sma([1.0, 2.0], 0)


def test_ema_ignores_values_before_the_window():
    history = [100.0, 101.0, 102.0, 103.0, 104.0, 1.0, 2.0, 3.0]
    assert ema(history, 3) == pytest.approx(ema(history[-3:], 3))


def test_ema_is_seeded_with_the_window_average():
    assert ema([1.0, 2.0, 3.0], 3) == pytest.approx(2.5)


def test_ema_applies_the_smoothing_factor():
    assert ema([1.0, 2.0, 3.0, 4.0], 3) == pytest.approx(3.5)


def test_ema_of_a_single_period_returns_the_last_value():
    assert ema([5.0, 7.0], 1) == pytest.approx(7.0)


def test_ema_rejects_short_series():
    with pytest.raises(ValueError):
        ema([1.0], 3)


def test_rsi_of_a_flat_series_is_neutral():
    assert rsi([1.10] * 20, 14) == pytest.approx(50.0)


def test_rsi_of_a_rising_series_is_maximal():
    assert rsi([float(value) for value in range(1, 21)], 14) == pytest.approx(100.0)


def test_rsi_of_a_falling_series_is_minimal():
    assert rsi([float(value) for value in range(20, 0, -1)], 14) == pytest.approx(0.0)


def test_rsi_uses_wilder_smoothing():
    assert rsi([10.0, 12.0, 11.0, 13.0], 2) == pytest.approx(100 - 100 / 7)


def test_rsi_stays_within_bounds():
    series = [1.0, 1.2, 1.1, 1.35, 1.30, 1.05, 1.4, 1.25, 1.5, 1.45, 1.6, 1.55]
    assert 0.0 <= rsi(series, 5) <= 100.0


def test_rsi_rejects_short_series():
    with pytest.raises(ValueError):
        rsi([1.0, 2.0], 14)


def test_rsi_rejects_non_positive_period():
    with pytest.raises(ValueError):
        rsi([1.0, 2.0, 3.0], 0)
