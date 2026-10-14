from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from gui.canvas import CandlestickChart, LineChart
from gui.formatting import (
    format_clock,
    format_money,
    format_percent,
    format_price,
    format_signed,
    format_volume,
    margin_level,
)
from gui.screens import Screen, scrollable
from gui.widgets import (
    DataTable,
    KpiTile,
    MetricRow,
    Panel,
    StatusPill,
    label,
)

SCREEN_TITLE = "Dashboard"

CHART_TIMEFRAME = "M15"
CHART_CANDLES = 120
MAX_EQUITY_SAMPLES = 240


class DashboardScreen(Screen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._market_data = context["market_data_service"]
        self._account_service = context["account_service"]
        self._events = context["order_event_repository"]
        self._profile = context["risk_profile"]
        self._symbol = self._market_data.watchlist()[0]
        self._equity_samples: list[float] = []
        self._issues: list[str] = []

        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        outer.addLayout(self._build_kpis())
        outer.addLayout(self._build_middle(), 4)
        outer.addLayout(self._build_bottom(), 3)

        self._issues_label = label("", role="warn")
        self._issues_label.setWordWrap(True)
        outer.addWidget(self._issues_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scrollable(body))

    def _build_kpis(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self._kpi_balance = KpiTile("Balance", unit="USD")
        self._kpi_equity = KpiTile("Equity", unit="USD", tone="accent")
        self._kpi_pl = KpiTile("Open P/L", unit="USD")
        self._kpi_margin = KpiTile("Margin used", unit="USD")
        self._kpi_free = KpiTile("Free margin", unit="USD")
        self._kpi_level = KpiTile("Margin level", unit="%")
        for tile in (
            self._kpi_balance,
            self._kpi_equity,
            self._kpi_pl,
            self._kpi_margin,
            self._kpi_free,
            self._kpi_level,
        ):
            row.addWidget(tile, 1)
        return row

    def _build_middle(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        chart_panel = Panel("Price chart", note=f"{self._symbol}  {CHART_TIMEFRAME}")
        self._simulated_pill = StatusPill("SIMULATED", tone="warn")
        chart_panel.add_header_widget(self._simulated_pill)
        self._chart = CandlestickChart()
        chart_panel.body.addWidget(self._chart, 1)
        row.addWidget(chart_panel, 3)

        side = QVBoxLayout()
        side.setSpacing(8)

        account_panel = Panel("Account")
        self._account_rows = {
            "login": MetricRow("Login"),
            "server": MetricRow("Server"),
            "status": MetricRow("Connection"),
            "server_time": MetricRow("Server time"),
        }
        for metric in self._account_rows.values():
            account_panel.body.addWidget(metric)

        account_panel.body.addWidget(label("SESSION EQUITY", role="section"))
        self._equity_chart = LineChart("Collecting session samples")
        self._equity_chart.setMinimumHeight(120)
        account_panel.body.addWidget(self._equity_chart, 1)
        side.addWidget(account_panel, 3)

        risk_panel = Panel("Risk profile", note=self._profile.name)
        self._risk_rows = {
            "daily_loss": MetricRow("Max daily loss"),
            "drawdown": MetricRow("Max drawdown"),
            "trades": MetricRow("Max concurrent trades"),
            "lot": MetricRow("Max lot size"),
            "equity": MetricRow("Equity protection"),
            "target": MetricRow("Daily profit target"),
            "session": MetricRow("Session window"),
        }
        for metric in self._risk_rows.values():
            risk_panel.body.addWidget(metric)
        side.addWidget(risk_panel, 2)
        row.addLayout(side, 2)
        return row

    def _build_bottom(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        watch_panel = Panel("Market watch", note="mock quotes")
        self._watch = DataTable(
            ["Symbol", "Bid", "Ask", "Spread", "Volume"], numeric_columns=(1, 2, 3, 4)
        )
        self._watch.set_empty_message("No quotes")
        watch_panel.body.addWidget(self._watch, 1)
        row.addWidget(watch_panel, 1)

        events_panel = Panel("Recent order events", note="audit trail")
        self._events_table = DataTable(
            ["Time", "Symbol", "Side", "Volume", "Status", "Reason"], numeric_columns=(3,)
        )
        self._events_table.set_empty_message("No order events recorded")
        self._events_table.stretch_columns(stretch_last=True)
        events_panel.body.addWidget(self._events_table, 1)
        row.addWidget(events_panel, 1)
        return row

    def refresh(self) -> None:
        self._issues = []
        self._attempt(self._refresh_account)
        self._attempt(self._refresh_chart)
        self._attempt(self._refresh_watchlist)
        self._attempt(self._refresh_events)
        self._refresh_risk()
        self._issues_label.setText(
            "  |  ".join(self._issues) if self._issues else ""
        )

    def _attempt(self, action) -> None:
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator instead of crashing the shell
            self._issues.append(f"{action.__name__}: {exc}")

    def _refresh_account(self) -> None:
        snapshot = self._account_service.get_account_snapshot()
        self._kpi_balance.set_value(format_money(snapshot.balance))
        self._kpi_equity.set_value(format_money(snapshot.equity))
        profit = snapshot.equity - snapshot.balance
        self._kpi_pl.set_value(format_signed(profit))
        self._kpi_pl.set_tone("up" if profit > 0 else "down" if profit < 0 else None)
        self._kpi_margin.set_value(format_money(snapshot.margin))
        self._kpi_free.set_value(format_money(snapshot.free_margin))
        level = margin_level(snapshot.equity, snapshot.margin)
        self._kpi_level.set_value("--" if level is None else format_percent(level))

        self._account_rows["login"].set_value(snapshot.login)
        self._account_rows["server"].set_value(snapshot.server)
        self._account_rows["status"].set_value(
            "connected" if snapshot.connected else "disconnected",
            "up" if snapshot.connected else "down",
        )
        self._account_rows["server_time"].set_value(format_clock(snapshot.server_time))

        self._equity_samples.append(float(snapshot.equity))
        del self._equity_samples[:-MAX_EQUITY_SAMPLES]
        self._equity_chart.set_points(self._equity_samples, decimals=2)

    def _refresh_chart(self) -> None:
        candles = self._market_data.get_candles(self._symbol, CHART_TIMEFRAME, CHART_CANDLES)
        digits = self._market_data.get_latest_tick(self._symbol).digits
        self._chart.set_candles(candles, digits)
        simulated = bool(candles) and candles[-1].simulated
        self._simulated_pill.setVisible(simulated)

    def _refresh_watchlist(self) -> None:
        self._watch.clear_rows()
        for symbol in self._market_data.watchlist():
            tick = self._market_data.get_latest_tick(symbol)
            self._watch.append_row(
                [
                    tick.symbol,
                    format_price(tick.bid, tick.digits),
                    format_price(tick.ask, tick.digits),
                    format_price(tick.spread, tick.digits),
                    tick.volume,
                ]
            )

    def _refresh_events(self) -> None:
        self._events_table.clear_rows()
        rows = list(self._events.list_all())[-12:]
        for event in reversed(rows):
            role = {"accepted": "up", "rejected": "warn", "failed": "down"}.get(
                str(event["status"]), None
            )
            self._events_table.append_row(
                [
                    str(event["created_at"])[11:19],
                    event["symbol"],
                    event["side"],
                    format_volume(event["volume"]),
                    event["status"],
                    event["reason"],
                ],
                roles=(None, None, None, None, role, None),
            )

    def _refresh_risk(self) -> None:
        profile = self._profile
        self._risk_rows["daily_loss"].set_value(format_money(profile.max_daily_loss))
        self._risk_rows["drawdown"].set_value(format_money(profile.max_drawdown))
        self._risk_rows["trades"].set_value(str(profile.max_trades))
        self._risk_rows["lot"].set_value(f"{profile.max_lot_size:.2f}")
        self._risk_rows["equity"].set_value(format_money(profile.equity_protection))
        self._risk_rows["target"].set_value(format_money(profile.daily_profit_target))
        window = (
            f"{profile.allowed_start_time.strftime('%H:%M')}"
            f"-{profile.allowed_end_time.strftime('%H:%M')}"
            if profile.allowed_start_time and profile.allowed_end_time
            else "any time"
        )
        self._risk_rows["session"].set_value(window, "muted" if window == "any time" else None)
