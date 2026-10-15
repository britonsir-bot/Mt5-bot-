from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from gui.screens import NotConnectedScreen

SCREEN_TITLE = "Strategy Manager"


class StrategyScreen(NotConnectedScreen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(
            context,
            title=SCREEN_TITLE,
            summary=(
                "Strategy definitions can be registered, but rule evaluation is not "
                "implemented, so no signals are produced and nothing is traded."
            ),
            planned=(
                "Parameter editing for each registered strategy",
                "Enable and disable per strategy and per symbol",
                "Evaluation of the rule list on each incoming tick",
                "Signal history with the inputs that produced it",
            ),
            parent=parent,
        )
