"""Event-driven single-symbol backtester for the declarative strategies.

Causality rules, all enforced by construction:

* An entry signal observed on bar ``t`` fills at the OPEN of bar ``t + 1``.
* A trailing stop is only moved using a CLOSED bar, and is checked on the bar
  after that, so a stop can never be tightened with information from the bar
  that is being tested.
* A stop or target that sits inside a bar's range fills at the stop price,
  which assumes the level is touched rather than modelling queue position.

Drawdown is measured on the closed-trade equity curve. Positions are sized from
``risk_per_trade_pct`` against the distance to the initial stop, which is how the
source configs specify sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

import numpy as np

from core import indicator_series as ind
from core.models import Candle
from strategies.rules import combine, condition_masks, group_mask
from strategies.series import SeriesProvider
from strategies.spec import StrategySpec

LONG_ONLY = "long_only"
SHORT_ONLY = "short_only"


@dataclass(slots=True)
class BacktestTrade:
    entry_index: int
    entry_time: datetime
    entry_price: float
    exit_index: int
    exit_time: datetime
    exit_price: float
    direction: str
    size: float
    initial_stop: float
    r_multiple: float
    gross_pnl: float
    exit_reason: str


@dataclass(slots=True)
class BacktestMetrics:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate_pct: float | None = None
    profit_factor: float | None = None
    net_profit: float = 0.0
    net_profit_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    expectancy_r: float | None = None
    average_win: float | None = None
    average_loss: float | None = None
    exposure_pct: float = 0.0


@dataclass(slots=True)
class BacktestResult:
    strategy_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    bars: int
    data_source: str
    simulated: bool
    metrics: BacktestMetrics
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    notes: tuple[str, ...] = ()


class Backtester:
    """Bar-by-bar simulator. One symbol, one open position at a time."""

    def __init__(
        self,
        *,
        initial_balance: float = 10_000.0,
        risk_per_trade_pct: float | None = None,
        spread: float = 0.0,
    ) -> None:
        self.initial_balance = float(initial_balance)
        self.risk_override = risk_per_trade_pct
        self.spread = float(spread)

    def run(
        self,
        spec: StrategySpec,
        candles: Sequence[Candle],
        *,
        data_source: str = "unknown",
        minimum_history: int = 200,
    ) -> BacktestResult:
        provider = SeriesProvider(candles)
        bars = provider.size
        notes: list[str] = []
        if bars < minimum_history:
            notes.append(f"only {bars} bars; at least {minimum_history} are needed for warm-up")
            return BacktestResult(
                spec.identifier, spec.name, spec.symbol, spec.timeframe, bars,
                data_source, _is_simulated(candles), BacktestMetrics(), [], [], tuple(notes),
            )

        entry_parts = condition_masks(spec.entry, provider) if spec.entry else []
        entry_mask = combine(entry_parts, spec.entry.operator if spec.entry else "AND", provider.size)
        if not entry_mask.any():
            notes.append(_explain_no_entry(entry_parts))
        exit_mask = (
            group_mask(spec.exit_signal, provider) if spec.exit_signal is not None else None
        )
        atr_series = ind.atr(provider.high, provider.low, provider.close, spec.risk.stop_loss.atr_period)
        trail_series = (
            ind.atr(provider.high, provider.low, provider.close, spec.risk.trailing_stop.atr_period)
            if spec.risk.trailing_stop.enabled
            else None
        )

        risk_pct = (
            self.risk_override if self.risk_override is not None else spec.risk.risk_per_trade_pct
        )
        if risk_pct <= 0:
            notes.append("risk per trade is zero; no positions were sized")
            return BacktestResult(
                spec.identifier, spec.name, spec.symbol, spec.timeframe, bars,
                data_source, _is_simulated(candles), BacktestMetrics(), [], [], tuple(notes),
            )

        allow_long = spec.trade_direction != SHORT_ONLY
        allow_short = spec.trade_direction != LONG_ONLY

        balance = self.initial_balance
        equity_curve = [balance]
        trades: list[BacktestTrade] = []
        bars_in_market = 0

        open_trade: dict[str, float | int | str] | None = None
        pending_entry: str | None = None
        pending_exit = False
        unusable_stops = 0

        for index in range(1, bars):
            # ---- 1. act on decisions taken at the previous close ----
            if open_trade is None and pending_entry is not None:
                entry_price = provider.open[index] + (self.spread if pending_entry == "long" else 0.0)
                stop_distance = _stop_distance(spec, atr_series, index, entry_price)
                if stop_distance is None or not np.isfinite(stop_distance) or stop_distance <= 0:
                    pending_entry = None
                    unusable_stops += 1
                else:
                    risk_amount = balance * risk_pct / 100.0
                    size = risk_amount / stop_distance
                    initial_stop = (
                        entry_price - stop_distance
                        if pending_entry == "long"
                        else entry_price + stop_distance
                    )
                    open_trade = {
                        "direction": pending_entry,
                        "entry_index": index,
                        "entry_time": provider.timestamps[index],
                        "entry_price": entry_price,
                        "size": size,
                        "stop": initial_stop,
                        "initial_stop": initial_stop,
                        "target": _target_price(spec, entry_price, stop_distance, pending_entry),
                    }
                    pending_entry = None
            elif open_trade is not None and pending_exit:
                trade = _close(open_trade, provider, index, provider.open[index], "signal")
                balance += trade.gross_pnl
                equity_curve.append(balance)
                trades.append(trade)
                open_trade = None
                pending_exit = False

            # ---- 2. manage an open position intrabar, then at the close ----
            if open_trade is not None:
                bars_in_market += 1
                trade = open_trade
                direction = str(trade["direction"])
                stop = float(trade["stop"])
                raw_target = trade["target"]
                target = None if raw_target is None else float(raw_target)
                exit_price: float | None = None
                reason = ""
                if direction == "long":
                    if provider.low[index] <= stop:
                        exit_price, reason = stop, "stop"
                    elif target is not None and provider.high[index] >= target:
                        exit_price, reason = target, "target"
                else:
                    if provider.high[index] >= stop:
                        exit_price, reason = stop, "stop"
                    elif target is not None and provider.low[index] <= target:
                        exit_price, reason = target, "target"

                if exit_price is None and spec.exit_method == "time_exit":
                    held = index - int(trade["entry_index"])
                    if spec.time_exit_bars is not None and held >= spec.time_exit_bars:
                        exit_price, reason = provider.close[index], "time_exit"

                if exit_price is not None:
                    closed = _close(trade, provider, index, exit_price, reason)
                    balance += closed.gross_pnl
                    equity_curve.append(balance)
                    trades.append(closed)
                    open_trade = None
                else:
                    # ---- 3. decide using this closed bar only ----
                    if trail_series is not None and np.isfinite(trail_series[index]):
                        trail_distance = trail_series[index] * spec.risk.trailing_stop.multiplier
                        if direction == "long":
                            trade["stop"] = max(float(trade["stop"]), provider.close[index] - trail_distance)
                        else:
                            trade["stop"] = min(float(trade["stop"]), provider.close[index] + trail_distance)
                    if exit_mask is not None and bool(exit_mask[index]):
                        pending_exit = True

            # ---- 4. record a new entry decision for the next bar ----
            if open_trade is None and not pending_exit and bool(entry_mask[index]):
                pending_entry = "long" if allow_long else ("short" if allow_short else None)

        if unusable_stops:
            notes.append(
                f"{unusable_stops} entries skipped: the stop distance for "
                f"{spec.risk.stop_loss.method!r} could not be computed"
            )

        if open_trade is not None:
            final = _close(open_trade, provider, bars - 1, provider.close[bars - 1], "end_of_data")
            balance += final.gross_pnl
            equity_curve.append(balance)
            trades.append(final)
            notes.append("final position closed at the last bar")

        metrics = _summarise(trades, self.initial_balance, equity_curve, bars_in_market, bars)
        return BacktestResult(
            spec.identifier, spec.name, spec.symbol, spec.timeframe, bars,
            data_source, _is_simulated(candles), metrics, trades, equity_curve, tuple(notes),
        )


def _explain_no_entry(parts: Sequence[np.ndarray]) -> str:
    """Distinguish "the data never met the rule" from "the rule is unsatisfiable"."""
    if not parts:
        return "no entry conditions"
    counts = [int(part.sum()) for part in parts]
    if all(count > 0 for count in counts):
        return (
            "entry conditions never coincided although each fires on its own "
            f"(per-condition bar counts: {counts})"
        )
    return f"entry conditions never fired on this data (per-condition bar counts: {counts})"


def _is_simulated(candles: Sequence[Candle]) -> bool:
    return bool(candles) and all(candle.simulated for candle in candles)


def _stop_distance(
    spec: StrategySpec, atr_series: np.ndarray, index: int, entry_price: float
) -> float | None:
    stop = spec.risk.stop_loss
    if not stop.enabled or stop.method == "none":
        if np.isfinite(atr_series[index]):
            return float(atr_series[index]) * 1.5
        return None
    if stop.method == "atr_multiple":
        if not np.isfinite(atr_series[index]):
            return None
        return float(atr_series[index]) * stop.multiplier
    if stop.method == "fixed_pct":
        return entry_price * stop.percent / 100.0
    return None


def _target_price(
    spec: StrategySpec, entry_price: float, stop_distance: float, direction: str
) -> float | None:
    target = spec.risk.take_profit
    if not target.enabled:
        return None
    if target.method == "atr_multiple":
        return None
    if target.method == "fixed_pct":
        distance = entry_price * target.percent / 100.0
        return entry_price + distance if direction == "long" else entry_price - distance
    return None


def _close(trade: dict, provider: SeriesProvider, index: int, price: float, reason: str) -> BacktestTrade:
    direction = str(trade["direction"])
    entry_price = float(trade["entry_price"])
    size = float(trade["size"])
    sign = 1.0 if direction == "long" else -1.0
    gross = (price - entry_price) * sign * size
    stop_distance = abs(entry_price - float(trade["initial_stop"])) or 1.0
    return BacktestTrade(
        entry_index=int(trade["entry_index"]),
        entry_time=trade["entry_time"],
        entry_price=entry_price,
        exit_index=index,
        exit_time=provider.timestamps[index],
        exit_price=float(price),
        direction=direction,
        size=size,
        initial_stop=float(trade["initial_stop"]),
        r_multiple=(price - entry_price) * sign / stop_distance,
        gross_pnl=gross,
        exit_reason=reason,
    )


def _summarise(
    trades: list[BacktestTrade],
    initial_balance: float,
    equity_curve: list[float],
    bars_in_market: int,
    bars: int,
) -> BacktestMetrics:
    metrics = BacktestMetrics()
    metrics.trades = len(trades)
    if not trades:
        metrics.net_profit = 0.0
        metrics.exposure_pct = round(bars_in_market / max(bars, 1) * 100.0, 2)
        return metrics

    profits = [trade.gross_pnl for trade in trades if trade.gross_pnl > 0]
    losses = [trade.gross_pnl for trade in trades if trade.gross_pnl <= 0]
    metrics.wins = len(profits)
    metrics.losses = len(losses)
    metrics.win_rate_pct = round(metrics.wins / metrics.trades * 100.0, 2)
    gross_profit = float(sum(profits))
    gross_loss = float(abs(sum(losses)))
    metrics.profit_factor = (
        round(gross_profit / gross_loss, 3) if gross_loss > 0 else None
    )
    metrics.net_profit = round(sum(trade.gross_pnl for trade in trades), 2)
    metrics.net_profit_pct = round(metrics.net_profit / initial_balance * 100.0, 2)
    metrics.expectancy_r = round(float(np.mean([trade.r_multiple for trade in trades])), 3)
    metrics.average_win = round(float(np.mean(profits)), 2) if profits else None
    metrics.average_loss = round(float(np.mean(losses)), 2) if losses else None
    metrics.exposure_pct = round(bars_in_market / max(bars, 1) * 100.0, 2)

    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100.0)
    metrics.max_drawdown_pct = round(worst, 2)
    return metrics


def run_all(
    specs: Sequence[StrategySpec],
    candles: Sequence[Candle],
    *,
    data_source: str,
    backtester: Backtester | None = None,
) -> list[BacktestResult]:
    engine = backtester or Backtester()
    results: list[BacktestResult] = []
    for spec in specs:
        if not spec.evaluable:
            continue
        results.append(engine.run(spec, candles, data_source=data_source))
    return results
