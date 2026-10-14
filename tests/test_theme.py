from __future__ import annotations

from gui.theme import DEFAULT_THEME, THEMES, apply_theme, resolve_theme


class FakeApplication:
    def __init__(self):
        self.stylesheets = []

    def setStyleSheet(self, stylesheet):
        self.stylesheets.append(stylesheet)


def test_unknown_theme_falls_back_to_the_default():
    assert resolve_theme("neon") == DEFAULT_THEME
    assert resolve_theme(None) == DEFAULT_THEME
    assert resolve_theme("") == DEFAULT_THEME


def test_known_themes_are_resolved():
    assert resolve_theme("light") == "light"
    assert resolve_theme("dark") == "dark"


def test_apply_theme_sets_the_stylesheet():
    application = FakeApplication()
    assert apply_theme(application, "light") == "light"
    assert application.stylesheets == [THEMES["light"]]


def test_apply_theme_without_a_stylesheet_setter():
    assert apply_theme(object(), "dark") == "dark"
