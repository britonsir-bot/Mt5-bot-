from __future__ import annotations

from datetime import datetime

EM_DASH = "\u2014"


def format_money(value: float | None, *, decimals: int = 2) -> str:
    if value is None:
        return EM_DASH
    return f"{value:,.{decimals}f}"


def format_price(value: float | None, digits: int = 5) -> str:
    if value is None:
        return EM_DASH
    return f"{value:.{digits}f}"


def format_signed(value: float | None, *, decimals: int = 2) -> str:
    if value is None:
        return EM_DASH
    return f"{value:+,.{decimals}f}"


def format_percent(value: float | None, *, decimals: int = 2) -> str:
    if value is None:
        return EM_DASH
    return f"{value:.{decimals}f}%"


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return EM_DASH
    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_clock(value: datetime | None) -> str:
    if value is None:
        return EM_DASH
    return value.strftime("%H:%M:%S")


def format_volume(value: float | None) -> str:
    if value is None:
        return EM_DASH
    return f"{value:.2f}"


def format_limit(value: float, *, decimals: int = 2) -> str:
    """Render a limit, making explicit that zero disables the check."""
    if value <= 0:
        return "disabled"
    return f"{value:,.{decimals}f}"


def margin_level(equity: float, margin: float) -> float | None:
    if margin <= 0:
        return None
    return equity / margin * 100.0


def shorten_path(path: str, *, keep_segments: int = 2, separator: str = "/") -> str:
    """Trim a long filesystem path for display, keeping the trailing segments."""
    parts = [part for part in path.replace("\\", separator).split(separator) if part]
    if len(parts) <= keep_segments + 1:
        return path
    return ".../" + separator.join(parts[-keep_segments:])
