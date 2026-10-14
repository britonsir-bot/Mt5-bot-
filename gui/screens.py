from __future__ import annotations

from typing import Any, Sequence

from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from gui.widgets import EmptyState, Panel, label, section_label


class Screen(QWidget):
    """Base class for a tab body.

    ``refresh`` pulls current values from the application services and updates the
    widgets in place. It may raise; the window reports the failure in the status bar.
    """

    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context

    def refresh(self) -> None:
        return


def scrollable(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(content)
    return area


class NotConnectedScreen(Screen):
    """Honest placeholder for a panel whose backing logic does not exist yet."""

    def __init__(
        self,
        context: dict[str, Any],
        *,
        title: str,
        summary: str,
        planned: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(context, parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        panel = Panel(title, note="not connected")
        panel.body.addWidget(EmptyState(title, summary))
        panel.body.addWidget(section_label("PLANNED"))
        for item in planned:
            panel.body.addWidget(_bullet(item))
        panel.body.addStretch(1)
        outer.addWidget(panel)


def _bullet(text: str) -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(7)
    marker = label("\u00b7", role="muted")
    marker.setFixedWidth(6)
    row.addWidget(marker)
    body = label(text, role="muted")
    body.setWordWrap(True)
    row.addWidget(body, 1)
    return holder
