from __future__ import annotations

from typing import Any

DEFAULT_THEME = "dark"

DARK_STYLESHEET = """
QWidget { background-color: #1e1f22; color: #e6e6e6; }
QTabWidget::pane { border: 1px solid #31343a; }
QTabBar::tab { background: #26282c; color: #cfcfcf; padding: 6px 14px; }
QTabBar::tab:selected { background: #2f3237; color: #ffffff; }
"""

LIGHT_STYLESHEET = """
QWidget { background-color: #f5f6f8; color: #1c1c1c; }
QTabWidget::pane { border: 1px solid #c9ccd1; }
QTabBar::tab { background: #e7e9ed; color: #303030; padding: 6px 14px; }
QTabBar::tab:selected { background: #ffffff; color: #000000; }
"""

THEMES = {"dark": DARK_STYLESHEET, "light": LIGHT_STYLESHEET}


def resolve_theme(name: str | None) -> str:
    return name if name in THEMES else DEFAULT_THEME


def apply_theme(application: Any, name: str | None) -> str:
    resolved = resolve_theme(name)
    setter = getattr(application, "setStyleSheet", None)
    if callable(setter):
        setter(THEMES[resolved])
    return resolved
