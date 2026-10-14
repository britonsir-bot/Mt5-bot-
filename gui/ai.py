from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from gui.screens import NotConnectedScreen

SCREEN_TITLE = "AI Assistant"


class AiScreen(NotConnectedScreen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(
            context,
            title=SCREEN_TITLE,
            summary=(
                "The advisory service returns a fixed neutral trend. No model is trained, "
                "loaded or evaluated, so there is nothing to display."
            ),
            planned=(
                "Dataset selection and feature construction from stored candles",
                "Model training runs with holdout metrics",
                "Forecast display with confidence intervals and the training window",
                "Explicit labelling of every advisory as non-actionable",
            ),
            parent=parent,
        )
