from __future__ import annotations

from string import Template
from typing import Any

DEFAULT_THEME = "dark"

UI_FONT_STACK = (
    "Inter",
    "Segoe UI",
    "Ubuntu",
    "DejaVu Sans",
    "Helvetica Neue",
    "Arial",
)
MONO_FONT_STACK = (
    "JetBrains Mono",
    "Cascadia Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Menlo",
    "monospace",
)
UI_FONT_POINT_SIZE = 9

DARK_PALETTE = {
    "bg": "#0a0f1a",
    "surface": "#101827",
    "surface_alt": "#0d1421",
    "header": "#141e33",
    "border": "#1e2a42",
    "border_strong": "#2c3c5c",
    "grid": "#16203a",
    "text": "#e6edf7",
    "text_dim": "#93a4c0",
    "text_muted": "#64789a",
    "accent": "#2f7ff0",
    "accent_hover": "#4a93f7",
    "accent_soft": "#1b3358",
    "accent_text": "#ffffff",
    "up": "#2ea86a",
    "up_soft": "#16301f",
    "down": "#e05252",
    "down_soft": "#33191c",
    "warn": "#cf9b2f",
    "warn_soft": "#332a12",
}

LIGHT_PALETTE = {
    "bg": "#eef1f6",
    "surface": "#ffffff",
    "surface_alt": "#f6f8fb",
    "header": "#e4e9f1",
    "border": "#d2dae5",
    "border_strong": "#b4c0d2",
    "grid": "#e4e9f1",
    "text": "#15202f",
    "text_dim": "#4f5d74",
    "text_muted": "#78859a",
    "accent": "#1f6fdb",
    "accent_hover": "#1a5fbe",
    "accent_soft": "#dbe8fa",
    "accent_text": "#ffffff",
    "up": "#1f8a53",
    "up_soft": "#e2f2e8",
    "down": "#c03a3a",
    "down_soft": "#fbe6e6",
    "warn": "#9c7411",
    "warn_soft": "#faf1d8",
}

PALETTES = {"dark": DARK_PALETTE, "light": LIGHT_PALETTE}

_STYLESHEET = Template(
    """
QWidget {
    background-color: $bg;
    color: $text;
    font-size: 12px;
}
QMainWindow, QDialog {
    background-color: $bg;
}
QToolTip {
    background-color: $header;
    color: $text;
    border: 1px solid $border_strong;
    padding: 4px 6px;
}

QFrame#HeaderBar {
    background-color: $header;
    border: none;
    border-bottom: 1px solid $border;
}
QFrame#HeaderDivider {
    background-color: $border;
    border: none;
}
QFrame#FooterBar {
    background-color: $header;
    border: none;
    border-top: 1px solid $border;
}
QLabel#BrandMark {
    color: $accent;
    font-size: 16px;
    font-weight: 700;
}
QLabel#BrandName {
    color: $text;
    font-size: 15px;
    font-weight: 600;
}
QLabel#BrandSeparator {
    color: $border_strong;
    font-size: 15px;
}
QLabel#BrandSubtitle {
    color: $text_dim;
    font-size: 13px;
}
QLabel#FooterText {
    color: $text_muted;
    font-size: 11px;
}
QLabel#NavLabel {
    color: $text_muted;
    font-size: 10px;
    font-weight: 600;
}

QTabWidget::pane {
    border: none;
    background-color: $bg;
}
QTabBar {
    background-color: $surface_alt;
}
QTabBar::tab {
    background-color: $surface_alt;
    color: $text_dim;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 2px solid transparent;
    padding: 7px 16px;
}
QTabBar::tab:selected {
    background-color: $surface;
    color: $text;
    border-bottom: 2px solid $accent;
}
QTabBar::tab:hover:!selected {
    color: $text;
}

QFrame#Panel {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 3px;
}
QFrame#PanelHeader {
    background-color: $surface;
    border: none;
    border-bottom: 1px solid $border;
}
QLabel#PanelTitle {
    color: $text_dim;
    font-size: 11px;
    font-weight: 600;
}
QLabel#PanelNote {
    color: $text_muted;
    font-size: 11px;
}

QFrame#KpiTile {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 3px;
}
QFrame#KpiTile[tone="up"] {
    border-left: 2px solid $up;
}
QFrame#KpiTile[tone="down"] {
    border-left: 2px solid $down;
}
QFrame#KpiTile[tone="accent"] {
    border-left: 2px solid $accent;
}
QLabel#KpiLabel {
    color: $text_muted;
    font-size: 10px;
    font-weight: 600;
}
QLabel#KpiValue {
    color: $text;
    font-size: 17px;
    font-weight: 600;
}
QLabel#KpiUnit {
    color: $text_muted;
    font-size: 10px;
}

QLabel[role="dim"] {
    color: $text_dim;
}
QLabel[role="muted"] {
    color: $text_muted;
    font-size: 11px;
}
QLabel[role="value"] {
    color: $text;
    font-weight: 600;
}
QLabel[role="up"] {
    color: $up;
}
QLabel[role="down"] {
    color: $down;
}
QLabel[role="warn"] {
    color: $warn;
}
QLabel[role="section"] {
    color: $text_muted;
    font-size: 10px;
    font-weight: 600;
}
QLabel[role="emptystate"] {
    color: $text_muted;
    font-size: 12px;
}

QTableWidget, QTableView {
    background-color: $surface;
    alternate-background-color: $surface_alt;
    gridline-color: $border;
    border: none;
    color: $text;
    selection-background-color: $accent_soft;
    selection-color: $text;
    outline: none;
}
QTableWidget::item, QTableView::item {
    border: none;
    padding: 3px 8px;
}
QHeaderView {
    background-color: $surface_alt;
}
QHeaderView::section {
    background-color: $surface_alt;
    color: $text_muted;
    border: none;
    border-bottom: 1px solid $border;
    border-right: 1px solid $border;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 600;
}
QHeaderView::section:last {
    border-right: none;
}
QTableCornerButton::section {
    background-color: $surface_alt;
    border: none;
    border-bottom: 1px solid $border;
}

QPushButton {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 3px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: $header;
}
QPushButton:pressed {
    background-color: $surface;
}
QPushButton:disabled {
    color: $text_muted;
    border-color: $border;
}
QPushButton[role="primary"] {
    background-color: $accent;
    color: $accent_text;
    border: 1px solid $accent;
    font-weight: 600;
}
QPushButton[role="primary"]:hover {
    background-color: $accent_hover;
}
QPushButton[role="buy"] {
    background-color: $up;
    color: $accent_text;
    border: 1px solid $up;
    font-weight: 600;
}
QPushButton[role="sell"] {
    background-color: $down;
    color: $accent_text;
    border: 1px solid $down;
    font-weight: 600;
}
QPushButton[role="toggle"] {
    background-color: $surface_alt;
    color: $text_muted;
    border: 1px solid $border;
    padding: 4px 10px;
}
QPushButton[role="toggle"]:checked {
    background-color: $accent_soft;
    color: $text;
    border: 1px solid $accent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit, QDateEdit, QPlainTextEdit {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 3px;
    padding: 5px 8px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QTimeEdit:focus, QPlainTextEdit:focus {
    border: 1px solid $accent;
}
QLineEdit:read-only, QLineEdit[readOnly="true"] {
    color: $text_dim;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled,
QTimeEdit:disabled, QDateEdit:disabled, QPlainTextEdit:disabled {
    color: $text_muted;
    background-color: $surface_alt;
    border: 1px solid $border;
}
QCheckBox:disabled {
    color: $text_muted;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button {
    background-color: $header;
    border: none;
    width: 14px;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox QAbstractItemView {
    background-color: $surface;
    border: 1px solid $border_strong;
    selection-background-color: $accent_soft;
    selection-color: $text;
}
QCheckBox {
    color: $text_dim;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid $border_strong;
    border-radius: 2px;
    background-color: $surface_alt;
}
QCheckBox::indicator:checked {
    background-color: $accent;
    border: 1px solid $accent;
}

QSplitter::handle {
    background-color: $border;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

QScrollBar:vertical {
    background-color: $surface_alt;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: $border_strong;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar:horizontal {
    background-color: $surface_alt;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: $border_strong;
    min-width: 24px;
    border-radius: 5px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    background: none;
    border: none;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}

QScrollArea {
    border: none;
    background-color: $bg;
}
QStatusBar {
    background-color: $header;
    color: $text_muted;
    border-top: 1px solid $border;
}
"""
)

THEMES = {
    name: _STYLESHEET.substitute(palette).strip() + "\n"
    for name, palette in PALETTES.items()
}

_state: dict[str, Any] = {"palette": DARK_PALETTE, "theme": DEFAULT_THEME}


def resolve_theme(name: str | None) -> str:
    return name if name in THEMES else DEFAULT_THEME


def current_palette() -> dict[str, str]:
    return _state["palette"]


def current_theme() -> str:
    return _state["theme"]


def apply_theme(application: Any, name: str | None) -> str:
    resolved = resolve_theme(name)
    _state["theme"] = resolved
    _state["palette"] = PALETTES[resolved]
    setter = getattr(application, "setStyleSheet", None)
    if callable(setter):
        setter(THEMES[resolved])
    _install_application_font(application)
    return resolved


def _install_application_font(application: Any) -> None:
    setter = getattr(application, "setFont", None)
    if not callable(setter):
        return
    try:
        from PySide6.QtGui import QFont
    except ImportError:  # pragma: no cover - Qt is required for the desktop shell
        return
    font = QFont()
    font.setFamilies(list(UI_FONT_STACK))
    font.setPointSize(UI_FONT_POINT_SIZE)
    setter(font)
