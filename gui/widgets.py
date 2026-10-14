from __future__ import annotations

from typing import Any, Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.theme import MONO_FONT_STACK, current_palette

TONE_ROLES = {
    "up": "up",
    "down": "down",
    "warn": "warn",
    "muted": "muted",
    "dim": "dim",
}

ROW_HEIGHT = 24
HEADER_HEIGHT = 26
FORM_LABEL_WIDTH = 132


def mono_font(point_size: int = 9, bold: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(list(MONO_FONT_STACK))
    font.setPointSize(point_size)
    font.setBold(bold)
    return font


def label(text: str, *, role: str | None = None, parent: QWidget | None = None) -> QLabel:
    widget = QLabel(text, parent)
    if role is not None:
        widget.setProperty("role", role)
    return widget


def section_label(text: str) -> QLabel:
    return label(text, role="section")


def button(text: str, *, role: str | None = None, checkable: bool = False) -> QPushButton:
    widget = QPushButton(text)
    if role is not None:
        widget.setProperty("role", role)
    widget.setCheckable(checkable)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


class Panel(QFrame):
    """Titled surface with an optional right-aligned header slot."""

    def __init__(self, title: str, *, note: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("PanelHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(10, 7, 10, 7)
        header_row.setSpacing(8)
        header_row.addWidget(QLabel(title, objectName="PanelTitle"))
        header_row.addStretch(1)
        self.note: QLabel | None = None
        if note is not None:
            self.note = QLabel(note, objectName="PanelNote")
            header_row.addWidget(self.note)
        self.header = header_row
        outer.addWidget(header)

        body = QWidget()
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(10, 9, 10, 10)
        self.body.setSpacing(8)
        outer.addWidget(body, 1)

    def add_header_widget(self, widget: QWidget) -> None:
        self.header.addWidget(widget)


class KpiTile(QFrame):
    def __init__(self, caption: str, *, unit: str | None = None, tone: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("KpiTile")
        if tone is not None:
            self.setProperty("tone", tone)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.setSpacing(3)
        layout.addWidget(QLabel(caption.upper(), objectName="KpiLabel"))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._value = QLabel("--", objectName="KpiValue")
        self._value.setFont(mono_font(12, bold=True))
        row.addWidget(self._value)
        if unit is not None:
            unit_label = QLabel(unit, objectName="KpiUnit")
            unit_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
            row.addWidget(unit_label)
        row.addStretch(1)
        layout.addLayout(row)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def value_text(self) -> str:
        return self._value.text()

    def set_tone(self, tone: str | None) -> None:
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)


class MetricRow(QWidget):
    def __init__(self, caption: str, value: str = "--", *, role: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)
        row.addWidget(label(caption, role="muted"))
        row.addStretch(1)
        self._value = label(value, role="value")
        self._value.setFont(mono_font())
        row.addWidget(self._value)

    def set_value(self, text: str, role: str | None = None) -> None:
        self._value.setText(text)
        if role is not None:
            self._value.setProperty("role", role)
            self._value.style().unpolish(self._value)
            self._value.style().polish(self._value)

    def value_text(self) -> str:
        return self._value.text()


class StatusPill(QFrame):
    _TONE_COLORS = {
        "up": "up",
        "down": "down",
        "warn": "warn",
        "muted": "border_strong",
    }

    def __init__(self, text: str = "", *, tone: str = "muted", parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._dot = QFrame()
        self._dot.setFixedSize(8, 8)
        row.addWidget(self._dot)
        self._text = label(text, role="muted")
        row.addWidget(self._text)
        self.set_state(text, tone)

    def set_state(self, text: str, tone: str = "muted") -> None:
        from gui.theme import current_palette

        color = current_palette()[self._TONE_COLORS.get(tone, "border_strong")]
        self._dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        self._text.setText(text)


class DataTable(QTableWidget):
    def __init__(self, headers: Sequence[str], *, numeric_columns: Iterable[int] = (),
                 parent: QWidget | None = None):
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(list(headers))
        self._numeric_columns = set(numeric_columns)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.horizontalHeader().setFixedHeight(HEADER_HEIGHT)
        self.horizontalHeader().setHighlightSections(False)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_numeric_columns(self, columns: Iterable[int]) -> None:
        self._numeric_columns = set(columns)

    def stretch_columns(self, stretch_last: bool = True, *, interactive: Iterable[int] = ()) -> None:
        header = self.horizontalHeader()
        header.setStretchLastSection(stretch_last)
        for index in range(self.columnCount()):
            mode = (
                QHeaderView.ResizeMode.Interactive
                if index in set(interactive)
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(index, mode)

    def clear_rows(self) -> None:
        self.setRowCount(0)

    def append_row(self, values: Sequence[Any], *, roles: Sequence[str | None] | None = None) -> int:
        row = self.rowCount()
        self.insertRow(row)
        for column, value in enumerate(values):
            text = "" if value is None else str(value)
            item = QTableWidgetItem(text)
            if column in self._numeric_columns:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                item.setFont(mono_font())
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            if roles is not None and column < len(roles) and roles[column] is not None:
                palette = current_palette()
                item.setForeground(QBrush(QColor(palette.get(roles[column], palette["text"]))))
            self.setItem(row, column, item)
        return row

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if self.rowCount() == 0:
            from PySide6.QtGui import QPainter

            painter = QPainter(self.viewport())
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(
                self.viewport().rect(),
                Qt.AlignmentFlag.AlignCenter,
                getattr(self, "_empty_message", "No data"),
            )
            painter.end()

    def set_empty_message(self, message: str) -> None:
        self._empty_message = message
        self.viewport().update()


class EmptyState(QWidget):
    def __init__(self, title: str, message: str, *, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.addStretch(1)
        heading = label(title, role="value")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        detail = label(message, role="emptystate")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addStretch(1)


class FormRow(QWidget):
    def __init__(self, caption: str, control: QWidget, *, hint: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        caption_label = label(caption, role="muted")
        caption_label.setFixedWidth(FORM_LABEL_WIDTH)
        row.addWidget(caption_label)
        row.addWidget(control, 1)
        outer.addLayout(row)
        if hint is not None:
            hint_row = QHBoxLayout()
            hint_row.setContentsMargins(0, 0, 0, 0)
            spacer = QWidget()
            spacer.setFixedWidth(FORM_LABEL_WIDTH)
            hint_row.addWidget(spacer)
            hint_label = label(hint, role="muted")
            hint_label.setWordWrap(True)
            hint_row.addWidget(hint_label, 1)
            outer.addLayout(hint_row)
