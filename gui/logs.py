from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from gui.screens import NotConnectedScreen

SCREEN_TITLE = "Logs"


class LogsScreen(NotConnectedScreen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(
            context,
            title=SCREEN_TITLE,
            summary=(
                "Structured JSON records are written to application.log by the logger, "
                "but this tab does not read them yet."
            ),
            planned=(
                "Tail the active log file into a read-only text view",
                "Filter by level and by event payload keys",
                "Open the log directory and export the current view",
            ),
            parent=parent,
        )
