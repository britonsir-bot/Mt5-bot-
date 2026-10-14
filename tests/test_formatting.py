from __future__ import annotations

from datetime import datetime

from gui.formatting import (
    EM_DASH,
    format_clock,
    format_limit,
    format_money,
    format_percent,
    format_price,
    format_signed,
    format_timestamp,
    format_volume,
    margin_level,
    shorten_path,
)


def test_format_money_groups_thousands():
    assert format_money(12345.678) == "12,345.68"


def test_format_money_handles_missing_values():
    assert format_money(None) == EM_DASH


def test_format_price_uses_the_symbol_digits():
    assert format_price(1.1005, 5) == "1.10050"
    assert format_price(157.2401, 3) == "157.240"
    assert format_price(2384.6012, 2) == "2384.60"


def test_format_signed_always_shows_the_sign():
    assert format_signed(12.5) == "+12.50"
    assert format_signed(-12.5) == "-12.50"
    assert format_signed(0.0) == "+0.00"


def test_format_percent():
    assert format_percent(1234.567) == "1234.57%"
    assert format_percent(None) == EM_DASH


def test_format_volume():
    assert format_volume(0.1) == "0.10"
    assert format_volume(None) == EM_DASH


def test_format_limit_marks_zero_as_disabled():
    assert format_limit(0.0) == "disabled"
    assert format_limit(-5.0) == "disabled"
    assert format_limit(500.0) == "500.00"


def test_timestamp_and_clock():
    moment = datetime(2026, 10, 15, 21, 44, 16)
    assert format_timestamp(moment) == "2026-10-15 21:44:16"
    assert format_clock(moment) == "21:44:16"
    assert format_timestamp(None) == EM_DASH


def test_margin_level_needs_a_used_margin():
    assert margin_level(10_000.0, 0.0) is None
    assert margin_level(10_000.0, 1_000.0) == 1000.0


def test_shorten_path_keeps_the_trailing_segments():
    assert shorten_path("/a/b/c/d/e") == ".../d/e"
    assert shorten_path("C:\\Users\\me\\AppData\\file.txt") == ".../AppData/file.txt"


def test_shorten_path_leaves_short_paths_alone():
    assert shorten_path("/tmp/x") == "/tmp/x"
    assert shorten_path("relative/file.txt") == "relative/file.txt"
