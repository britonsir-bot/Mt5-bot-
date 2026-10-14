from __future__ import annotations


def sma(values: list[float], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError("not enough values for SMA")
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError("not enough values for EMA")
    window = values[-period:]
    multiplier = 2 / (period + 1)
    result = sum(window) / period
    for value in window[1:]:
        result = (value - result) * multiplier + result
    return result


def rsi(values: list[float], period: int = 14) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) <= period:
        raise ValueError("not enough values for RSI")
    deltas = [current - previous for previous, current in zip(values[:-1], values[1:])]
    average_gain = sum(max(delta, 0.0) for delta in deltas[:period]) / period
    average_loss = sum(abs(min(delta, 0.0)) for delta in deltas[:period]) / period
    for delta in deltas[period:]:
        average_gain = (average_gain * (period - 1) + max(delta, 0.0)) / period
        average_loss = (average_loss * (period - 1) + abs(min(delta, 0.0))) / period
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))
