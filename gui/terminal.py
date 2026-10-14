from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.exceptions import Mt5BotError, RiskViolationError
from core.models import DEFAULT_TIMEFRAME, TIMEFRAME_MINUTES, TradeRequest
from gui.canvas import CandlestickChart
from gui.formatting import format_percent, format_price, format_signed
from gui.screens import Screen
from gui.widgets import (
    DataTable,
    MetricRow,
    Panel,
    StatusPill,
    button,
    label,
    mono_font,
)

SCREEN_TITLE = "Market Terminal"

TIMEFRAMES = tuple(TIMEFRAME_MINUTES)
CHART_CANDLES = 160


class MarketTerminalScreen(Screen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._market_data = context["market_data_service"]
        self._account_service = context["account_service"]
        self._order_manager = context["order_manager"]
        self._profile = context["risk_profile"]
        self._sandbox = bool(context["settings"].use_mock_connector)
        self._symbol = self._market_data.watchlist()[0]
        self._timeframe = DEFAULT_TIMEFRAME
        self._digits = 5
        self._issues: list[str] = []

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        outer.addWidget(self._build_watchlist(), 2)
        outer.addWidget(self._build_centre(), 5)
        outer.addWidget(self._build_ticket(), 3)

    def _build_watchlist(self) -> Panel:
        panel = Panel("Watchlist", note="select to load")
        self._watch = DataTable(["Symbol", "Bid", "Ask"], numeric_columns=(1, 2))
        self._watch.set_empty_message("No quotes")
        self._watch.stretch_columns(stretch_last=True)
        self._watch.itemSelectionChanged.connect(self._on_symbol_selected)
        panel.body.addWidget(self._watch, 1)
        return panel

    def _build_centre(self) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        panel = Panel("Price chart")
        self._simulated_pill = StatusPill("SIMULATED", tone="warn")
        panel.add_header_widget(self._simulated_pill)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(4)
        self._timeframe_group = QButtonGroup(self)
        self._timeframe_group.setExclusive(True)
        for name in TIMEFRAMES:
            toggle = button(name, role="toggle", checkable=True)
            toggle.setChecked(name == self._timeframe)
            toggle.clicked.connect(lambda _checked, value=name: self._set_timeframe(value))
            self._timeframe_group.addButton(toggle)
            toggle_row.addWidget(toggle)
        toggle_row.addStretch(1)
        panel.body.addLayout(toggle_row)

        self._chart = CandlestickChart()
        panel.body.addWidget(self._chart, 1)

        quotes = QHBoxLayout()
        quotes.setSpacing(14)
        self._quote_rows = {
            "bid": MetricRow("Bid"),
            "ask": MetricRow("Ask"),
            "spread": MetricRow("Spread"),
            "high": MetricRow("Period high"),
            "low": MetricRow("Period low"),
            "change": MetricRow("Change"),
        }
        for metric in self._quote_rows.values():
            quotes.addWidget(metric, 1)
        panel.body.addLayout(quotes)
        column.addWidget(panel, 1)

        self._issues_label = label("", role="warn")
        self._issues_label.setWordWrap(True)
        column.addWidget(self._issues_label)
        return holder

    def _build_ticket(self) -> Panel:
        panel = Panel("Order ticket", note="sandbox" if self._sandbox else "live")

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        self._ticket_symbol = label(self._symbol, role="value")
        self._ticket_symbol.setFont(mono_font(10, bold=True))
        grid.addWidget(label("Instrument", role="muted"), 0, 0)
        grid.addWidget(self._ticket_symbol, 0, 1)

        self._volume = QDoubleSpinBox()
        self._volume.setDecimals(2)
        self._volume.setRange(0.01, 100.0)
        self._volume.setSingleStep(0.01)
        self._volume.setValue(0.10)
        grid.addWidget(label("Volume (lots)", role="muted"), 1, 0)
        grid.addWidget(self._volume, 1, 1)

        self._stop_loss = QDoubleSpinBox()
        self._stop_loss.setRange(0.0, 1_000_000.0)
        self._stop_loss.setSpecialValueText("none")
        self._take_profit = QDoubleSpinBox()
        self._take_profit.setRange(0.0, 1_000_000.0)
        self._take_profit.setSpecialValueText("none")
        grid.addWidget(label("Stop loss", role="muted"), 2, 0)
        grid.addWidget(self._stop_loss, 2, 1)
        grid.addWidget(label("Take profit", role="muted"), 3, 0)
        grid.addWidget(self._take_profit, 3, 1)

        self._comment = QLineEdit()
        self._comment.setPlaceholderText("optional")
        grid.addWidget(label("Comment", role="muted"), 4, 0)
        grid.addWidget(self._comment, 4, 1)
        panel.body.addLayout(grid)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self._buy_button = button("Buy", role="buy")
        self._sell_button = button("Sell", role="sell")
        self._buy_button.clicked.connect(lambda: self._submit("buy"))
        self._sell_button.clicked.connect(lambda: self._submit("sell"))
        actions.addWidget(self._buy_button, 1)
        actions.addWidget(self._sell_button, 1)
        panel.body.addLayout(actions)

        self._result_label = label("", role="muted")
        self._result_label.setWordWrap(True)
        panel.body.addWidget(self._result_label)

        panel.body.addWidget(_separator())

        if self._sandbox:
            notice = (
                "Sandbox mode: orders are simulated and never reach a broker. "
                "Open positions, daily P/L and drawdown are not tracked, so those three "
                "risk limits cannot be evaluated."
            )
            self._buy_button.setEnabled(True)
            self._sell_button.setEnabled(True)
        else:
            notice = (
                "Live order entry is disabled. Position, daily P/L and drawdown tracking "
                "are not implemented, so the risk limits could not be evaluated before "
                "sending an order."
            )
            self._buy_button.setEnabled(False)
            self._sell_button.setEnabled(False)
        notice_label = label(notice, role="warn" if self._sandbox else "down")
        notice_label.setWordWrap(True)
        panel.body.addWidget(notice_label)
        panel.body.addStretch(1)
        return panel

    def _set_timeframe(self, timeframe: str) -> None:
        self._timeframe = timeframe
        self.refresh()

    def _on_symbol_selected(self) -> None:
        rows = self._watch.selectionModel().selectedRows()
        if not rows:
            return
        symbol = self._watch.item(rows[0].row(), 0)
        if symbol is None or symbol.text() == self._symbol:
            return
        self._symbol = symbol.text()
        self._ticket_symbol.setText(self._symbol)
        self.refresh()

    def refresh(self) -> None:
        self._issues = []
        self._attempt(self._refresh_watchlist)
        self._attempt(self._refresh_chart)
        self._attempt(self._refresh_quotes)
        self._issues_label.setText("  |  ".join(self._issues) if self._issues else "")

    def _attempt(self, action) -> None:
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator instead of crashing the shell
            self._issues.append(f"{action.__name__}: {exc}")

    def _refresh_watchlist(self) -> None:
        self._watch.blockSignals(True)
        self._watch.clear_rows()
        for symbol in self._market_data.watchlist():
            tick = self._market_data.get_latest_tick(symbol)
            row = self._watch.append_row(
                [
                    tick.symbol,
                    format_price(tick.bid, tick.digits),
                    format_price(tick.ask, tick.digits),
                ]
            )
            if tick.symbol == self._symbol:
                self._watch.selectRow(row)
        self._watch.blockSignals(False)

    def _refresh_chart(self) -> None:
        candles = self._market_data.get_candles(self._symbol, self._timeframe, CHART_CANDLES)
        tick = self._market_data.get_latest_tick(self._symbol)
        self._digits = tick.digits
        self._chart.set_candles(candles, self._digits)
        self._simulated_pill.setVisible(bool(candles) and candles[-1].simulated)
        for spin in (self._stop_loss, self._take_profit):
            spin.setDecimals(self._digits)
            spin.setSingleStep(10 ** -self._digits * 100)

    def _refresh_quotes(self) -> None:
        tick = self._market_data.get_latest_tick(self._symbol)
        candles = self._market_data.get_candles(self._symbol, self._timeframe, CHART_CANDLES)
        self._quote_rows["bid"].set_value(format_price(tick.bid, tick.digits))
        self._quote_rows["ask"].set_value(format_price(tick.ask, tick.digits))
        self._quote_rows["spread"].set_value(format_price(tick.spread, tick.digits))
        if candles:
            high = max(candle.high for candle in candles)
            low = min(candle.low for candle in candles)
            change = candles[-1].close - candles[0].open
            percent = change / candles[0].open * 100.0 if candles[0].open else 0.0
            self._quote_rows["high"].set_value(format_price(high, tick.digits))
            self._quote_rows["low"].set_value(format_price(low, tick.digits))
            self._quote_rows["change"].set_value(
                f"{format_signed(change, decimals=tick.digits)}  ({format_percent(percent)})",
                "up" if change > 0 else "down" if change < 0 else None,
            )
        else:
            for key in ("high", "low", "change"):
                self._quote_rows[key].set_value("--", "muted")

    def _submit(self, side: str) -> None:
        try:
            request = TradeRequest(
                symbol=self._symbol,
                side=side,
                volume=float(self._volume.value()),
                stop_loss=float(self._stop_loss.value()) or None,
                take_profit=float(self._take_profit.value()) or None,
                comment=self._comment.text().strip(),
            )
            snapshot = self._account_service.get_account_snapshot()
            result = self._order_manager.submit_manual_trade(
                request,
                self._profile,
                open_trade_count=0,
                daily_pnl=0.0,
                current_drawdown=0.0,
                equity=snapshot.equity,
            )
        except RiskViolationError as exc:
            self._set_result(f"Rejected by risk manager: {exc}", "warn")
        except Mt5BotError as exc:
            self._set_result(f"Execution failed: {exc}", "down")
        except ValueError as exc:
            self._set_result(f"Invalid request: {exc}", "down")
        else:
            tone = "up" if result.accepted else "down"
            prefix = "Simulated" if result.raw_response.get("simulated") else "Live"
            self._set_result(f"{prefix}: {result.message}", tone)
        self._attempt(self._refresh_watchlist)

    def _set_result(self, text: str, tone: str) -> None:
        self._result_label.setText(text)
        self._result_label.setProperty("role", tone)
        self._result_label.style().unpolish(self._result_label)
        self._result_label.style().polish(self._result_label)


def _separator() -> QWidget:
    line = QFrame()
    line.setObjectName("HeaderDivider")
    line.setFixedHeight(1)
    return line
