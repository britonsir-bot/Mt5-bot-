from __future__ import annotations

from typing import Any

from gui import ai, charts, dashboard, logs, orders, risk, settings, strategy

try:
    from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget
except ImportError:  # pragma: no cover - exercised indirectly in runtime fallback
    QLabel = None
    QMainWindow = object  # type: ignore[assignment]
    QTabWidget = None


SCREEN_TITLES = [
    dashboard.SCREEN_TITLE,
    charts.SCREEN_TITLE,
    orders.SCREEN_TITLE,
    strategy.SCREEN_TITLE,
    risk.SCREEN_TITLE,
    ai.SCREEN_TITLE,
    logs.SCREEN_TITLE,
    settings.SCREEN_TITLE,
]


class MainWindow(QMainWindow):  # type: ignore[misc]
    def __init__(self, app_context: dict[str, Any]) -> None:
        if QLabel is None or QTabWidget is None:
            raise RuntimeError("PySide6 is not available in this environment.")
        super().__init__()
        self.setWindowTitle(app_context["settings"].app_name)
        tabs = QTabWidget()
        snapshot = app_context["account_service"].get_account_snapshot()
        for title in SCREEN_TITLES:
            tabs.addTab(QLabel(f"{title}\nConnected: {snapshot.connected}"), title)
        self.setCentralWidget(tabs)
