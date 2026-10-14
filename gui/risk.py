from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from core.models import TradeRequest
from gui.formatting import format_limit, format_money
from gui.screens import Screen, scrollable
from gui.widgets import MetricRow, Panel, button, label

SCREEN_TITLE = "Risk"

PROBE_VOLUME = 0.10

MONEY_LIMITS = (
    ("max_daily_loss", "Max daily loss"),
    ("max_drawdown", "Max drawdown"),
    ("equity_protection", "Equity protection floor"),
    ("daily_profit_target", "Daily profit target"),
)


class RiskScreen(Screen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._profile = context["risk_profile"]
        self._risk_manager = context["risk_manager"]
        self._account_service = context["account_service"]

        body = QWidget()
        outer = QHBoxLayout(body)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        outer.addWidget(self._build_editor(), 3)
        outer.addLayout(self._build_side(), 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scrollable(body))
        # Load the live profile immediately: applying an editor that has never been
        # populated would write the spin-box defaults over the running limits.
        self.refresh()

    def _build_editor(self) -> Panel:
        panel = Panel("Limits", note="zero disables a check")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        self._money_spins: dict[str, QDoubleSpinBox] = {}
        row = 0
        for field, caption in MONEY_LIMITS:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 10_000_000.0)
            spin.setDecimals(2)
            spin.setSingleStep(50.0)
            spin.setGroupSeparatorShown(True)
            self._money_spins[field] = spin
            grid.addWidget(label(caption, role="muted"), row, 0)
            grid.addWidget(spin, row, 1)
            row += 1

        self._max_trades = QSpinBox()
        self._max_trades.setRange(0, 1000)
        grid.addWidget(label("Max concurrent trades", role="muted"), row, 0)
        grid.addWidget(self._max_trades, row, 1)
        row += 1

        self._max_lot = QDoubleSpinBox()
        self._max_lot.setRange(0.0, 1000.0)
        self._max_lot.setDecimals(2)
        self._max_lot.setSingleStep(0.10)
        grid.addWidget(label("Max lot size", role="muted"), row, 0)
        grid.addWidget(self._max_lot, row, 1)
        row += 1

        self._session_enabled = QCheckBox("Restrict trading to a session window")
        self._session_enabled.toggled.connect(self._on_session_toggled)
        grid.addWidget(self._session_enabled, row, 0, 1, 2)
        row += 1

        self._session_start = QTimeEdit()
        self._session_start.setDisplayFormat("HH:mm")
        self._session_end = QTimeEdit()
        self._session_end.setDisplayFormat("HH:mm")
        grid.addWidget(label("Session start", role="muted"), row, 0)
        grid.addWidget(self._session_start, row, 1)
        row += 1
        grid.addWidget(label("Session end", role="muted"), row, 0)
        grid.addWidget(self._session_end, row, 1)
        row += 1

        panel.body.addLayout(grid)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self._apply_button = button("Apply", role="primary")
        self._revert_button = button("Revert")
        self._apply_button.clicked.connect(self._apply)
        self._revert_button.clicked.connect(self.refresh)
        actions.addWidget(self._apply_button)
        actions.addWidget(self._revert_button)
        actions.addStretch(1)
        panel.body.addLayout(actions)

        self._status = label("", role="muted")
        self._status.setWordWrap(True)
        panel.body.addWidget(self._status)
        panel.body.addStretch(1)
        return panel

    def _build_side(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(8)

        summary = Panel("Effective limits")
        self._summary_rows = {
            "max_daily_loss": MetricRow("Max daily loss"),
            "max_drawdown": MetricRow("Max drawdown"),
            "equity_protection": MetricRow("Equity protection"),
            "daily_profit_target": MetricRow("Profit target"),
            "max_trades": MetricRow("Max trades"),
            "max_lot_size": MetricRow("Max lot size"),
            "session": MetricRow("Session"),
        }
        for metric in self._summary_rows.values():
            summary.body.addWidget(metric)
        column.addWidget(summary)

        probe = Panel("Evaluate a sample order", note="risk engine")
        probe.body.addWidget(
            label(
                f"Runs the configured limits against a {PROBE_VOLUME:.2f} lot EURUSD buy "
                "using the current account equity. Open positions, daily P/L and drawdown "
                "are passed as zero because they are not tracked.",
                role="muted",
            )
        )
        self._probe_button = button("Evaluate")
        self._probe_button.clicked.connect(self._probe)
        probe.body.addWidget(self._probe_button)
        self._probe_result = label("", role="muted")
        self._probe_result.setWordWrap(True)
        probe.body.addWidget(self._probe_result)
        column.addWidget(probe)

        storage = Panel("Persistence", note="not connected")
        storage.body.addWidget(
            label(
                "Limits live in memory for this session. The database stores account "
                "profiles and order events only, so the profile is not saved between "
                "restarts.",
                role="muted",
            )
        )
        column.addWidget(storage)
        column.addStretch(1)
        return column

    def refresh(self) -> None:
        profile = self._profile
        for field, _ in MONEY_LIMITS:
            self._money_spins[field].setValue(float(getattr(profile, field)))
        self._max_trades.setValue(int(profile.max_trades))
        self._max_lot.setValue(float(profile.max_lot_size))

        has_window = bool(profile.allowed_start_time and profile.allowed_end_time)
        self._session_enabled.setChecked(has_window)
        self._session_start.setTime(
            QTime(profile.allowed_start_time.hour, profile.allowed_start_time.minute)
            if has_window
            else QTime(0, 0)
        )
        self._session_end.setTime(
            QTime(profile.allowed_end_time.hour, profile.allowed_end_time.minute)
            if has_window
            else QTime(23, 59)
        )
        self._session_start.setEnabled(has_window)
        self._session_end.setEnabled(has_window)
        self._update_summary()

    def _on_session_toggled(self, enabled: bool) -> None:
        self._session_start.setEnabled(enabled)
        self._session_end.setEnabled(enabled)

    def _apply(self) -> None:
        profile = self._profile
        for field, _ in MONEY_LIMITS:
            setattr(profile, field, float(self._money_spins[field].value()))
        profile.max_trades = int(self._max_trades.value())
        profile.max_lot_size = float(self._max_lot.value())
        if self._session_enabled.isChecked():
            profile.allowed_start_time = self._session_start.time().toPython()
            profile.allowed_end_time = self._session_end.time().toPython()
        else:
            profile.allowed_start_time = None
            profile.allowed_end_time = None
        self._update_summary()
        self._status.setProperty("role", "up")
        self._status.setText("Applied to the running session. Not persisted between restarts.")
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)

    def _update_summary(self) -> None:
        profile = self._profile
        self._summary_rows["max_daily_loss"].set_value(
            format_limit(profile.max_daily_loss), "muted" if profile.max_daily_loss <= 0 else None
        )
        self._summary_rows["max_drawdown"].set_value(
            format_limit(profile.max_drawdown), "muted" if profile.max_drawdown <= 0 else None
        )
        self._summary_rows["equity_protection"].set_value(
            format_money(profile.equity_protection),
            "muted" if profile.equity_protection <= 0 else None,
        )
        self._summary_rows["daily_profit_target"].set_value(
            format_money(profile.daily_profit_target),
            "muted" if profile.daily_profit_target <= 0 else None,
        )
        self._summary_rows["max_trades"].set_value(str(profile.max_trades))
        self._summary_rows["max_lot_size"].set_value(f"{profile.max_lot_size:.2f}")
        window = (
            f"{profile.allowed_start_time.strftime('%H:%M')}-"
            f"{profile.allowed_end_time.strftime('%H:%M')}"
            if profile.allowed_start_time and profile.allowed_end_time
            else "any time"
        )
        self._summary_rows["session"].set_value(window, "muted" if window == "any time" else None)

    def _probe(self) -> None:
        try:
            snapshot = self._account_service.get_account_snapshot()
            request = TradeRequest(symbol="EURUSD", side="buy", volume=PROBE_VOLUME)
            decision = self._risk_manager.evaluate(
                request,
                self._profile,
                open_trade_count=0,
                daily_pnl=0.0,
                current_drawdown=0.0,
                equity=snapshot.equity,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            self._set_probe(f"Could not evaluate: {exc}", "down")
            return
        self._set_probe(
            f"{'Approved' if decision.allowed else 'Rejected'}: {decision.reason}",
            "up" if decision.allowed else "warn",
        )

    def _set_probe(self, text: str, tone: str) -> None:
        self._probe_result.setText(text)
        self._probe_result.setProperty("role", tone)
        self._probe_result.style().unpolish(self._probe_result)
        self._probe_result.style().polish(self._probe_result)
