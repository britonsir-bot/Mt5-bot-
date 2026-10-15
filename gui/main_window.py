from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui import ai, dashboard, logs, orders, risk, settings, strategy, terminal
from gui.theme import apply_theme as apply_theme_to_application
from gui.theme import current_palette, current_theme
from gui.widgets import StatusPill, button, label, mono_font

SCREEN_BUILDERS = (
    (dashboard.SCREEN_TITLE, dashboard.DashboardScreen),
    (terminal.SCREEN_TITLE, terminal.MarketTerminalScreen),
    (orders.SCREEN_TITLE, orders.OrdersScreen),
    (strategy.SCREEN_TITLE, strategy.StrategyScreen),
    (risk.SCREEN_TITLE, risk.RiskScreen),
    (ai.SCREEN_TITLE, ai.AiScreen),
    (logs.SCREEN_TITLE, logs.LogsScreen),
    (settings.SCREEN_TITLE, settings.SettingsScreen),
)

SCREEN_TITLES = [title for title, _ in SCREEN_BUILDERS]

CLOCK_INTERVAL_MS = 1000


class MainWindow(QMainWindow):
    def __init__(self, app_context: dict[str, Any]) -> None:
        super().__init__()
        self.context = app_context
        self.context["set_theme"] = self.apply_theme

        self.setWindowTitle(f"{app_context['settings'].app_name} \u2014 Trading Terminal")
        self.setMinimumSize(1120, 700)

        central = QWidget()
        column = QVBoxLayout(central)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._build_header())
        column.addWidget(self._build_tabs(), 1)
        column.addWidget(self._build_footer())
        self.setCentralWidget(central)

        self._clock = QTimer(self)
        self._clock.setInterval(CLOCK_INTERVAL_MS)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start()

        self._source_label.setText(self._source_text())
        self._refresh_account_state()
        self.refresh_current()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderBar")
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        mark, _, remainder = self.context["settings"].app_name.partition(" ")
        row.addWidget(QLabel(mark, objectName="BrandMark"))
        if remainder:
            row.addWidget(QLabel(remainder, objectName="BrandName"))
        row.addWidget(QLabel("|", objectName="BrandSeparator"))
        row.addWidget(QLabel("Trading Terminal", objectName="BrandSubtitle"))

        row.addStretch(1)
        row.addWidget(QLabel("ACCOUNT", objectName="NavLabel"))
        self._account_pill = StatusPill("", tone="muted")
        row.addWidget(self._account_pill)
        self._account_label = label("", role="dim")
        self._account_label.setFont(mono_font(8))
        row.addWidget(self._account_label)
        row.addWidget(self._divider())
        self._clock_label = label("", role="dim")
        self._clock_label.setFont(mono_font(8))
        row.addWidget(self._clock_label)
        row.addWidget(self._divider())
        self._refresh_button = button("Refresh", role="primary")
        self._refresh_button.clicked.connect(self.refresh_current)
        row.addWidget(self._refresh_button)
        return header

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self._screens: dict[int, Any] = {}
        for index, (title, builder) in enumerate(SCREEN_BUILDERS):
            self._screens[index] = builder(self.context)
            tabs.addTab(self._screens[index], title)
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs
        return tabs

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("FooterBar")
        row = QHBoxLayout(footer)
        row.setContentsMargins(12, 5, 12, 5)
        row.setSpacing(8)
        row.addWidget(QLabel("Professional trading terminal", objectName="FooterText"))
        row.addStretch(1)
        self._source_label = QLabel("", objectName="FooterText")
        row.addWidget(self._source_label)
        row.addWidget(self._divider())
        self._status_label = QLabel("", objectName="FooterText")
        row.addWidget(self._status_label)
        return footer

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setObjectName("HeaderDivider")
        line.setFixedWidth(1)
        line.setFixedHeight(16)
        return line

    def refresh_current(self) -> None:
        self._refresh_screen(self._tabs.currentIndex())
        self._refresh_account_state()
        self._tick_clock()

    def _refresh_screen(self, index: int) -> None:
        screen = self._screens.get(index)
        if screen is None:
            return
        title = self._tabs.tabText(index)
        try:
            screen.refresh()
        except Exception as exc:  # noqa: BLE001 - reported in the status bar instead of crashing
            self._set_status(f"{title}: {exc}", tone="down")
        else:
            self._set_status(f"{title} refreshed {datetime.now().strftime('%H:%M:%S')}")

    def _on_tab_changed(self, index: int) -> None:
        self._refresh_screen(index)

    def apply_theme(self, name: str | None) -> None:
        resolved = apply_theme_to_application(QApplication.instance(), name)
        for screen in self._screens.values():
            screen.refresh()
        self._source_label.setText(self._source_text())
        self._refresh_account_state()
        self._set_status(f"Theme set to {resolved}")

    def _tick_clock(self) -> None:
        self._clock_label.setText(datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))

    def _source_text(self) -> str:
        mode = "SANDBOX" if self.context["settings"].use_mock_connector else "LIVE"
        return f"Data source: {mode}  \u00b7  Theme: {current_theme()}"

    def _refresh_account_state(self) -> None:
        try:
            snapshot = self.context["account_service"].get_account_snapshot()
        except Exception as exc:  # noqa: BLE001 - the header must still render
            self._account_pill.set_state("unavailable", "down")
            self._account_label.setText(str(exc))
            return
        self._account_pill.set_state(
            "connected" if snapshot.connected else "disconnected",
            "up" if snapshot.connected else "down",
        )
        self._account_label.setText(f"{snapshot.login} @ {snapshot.server}")

    def _set_status(self, text: str, tone: str = "muted") -> None:
        self._status_label.setText(text)
        color_key = {"down": "down", "warn": "warn", "up": "up", "muted": "text_muted"}[tone]
        self._status_label.setStyleSheet(
            f"color: {current_palette()[color_key]}; font-size: 11px;"
        )
