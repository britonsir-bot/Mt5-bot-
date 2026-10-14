from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

from gui.formatting import shorten_path
from gui.screens import Screen, scrollable
from gui.theme import THEMES, current_theme
from gui.widgets import DataTable, MetricRow, Panel, StatusPill, label

SCREEN_TITLE = "Settings"


class SettingsScreen(Screen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._settings = context["settings"]
        self._accounts = context["account_repository"]

        body = QWidget()
        outer = QHBoxLayout(body)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        outer.addLayout(self._build_left(), 1)
        outer.addLayout(self._build_right(), 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scrollable(body))

    def _build_left(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(8)

        connection = Panel("Connection")
        self._mode_pill = StatusPill("", tone="warn")
        connection.body.addWidget(self._mode_pill)
        self._rows = {
            "connector": MetricRow("Connector"),
            "auto_login": MetricRow("Auto login at startup"),
            "login": MetricRow("Account login"),
            "server": MetricRow("Broker server"),
            "terminal": MetricRow("Terminal path"),
        }
        for metric in self._rows.values():
            connection.body.addWidget(metric)
        column.addWidget(connection)

        appearance = Panel("Appearance")
        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        theme_row.addWidget(label("Theme", role="muted"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(sorted(THEMES))
        self._theme_combo.setCurrentText(current_theme())
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo, 1)
        appearance.body.addLayout(theme_row)
        appearance.body.addWidget(
            label("Applied immediately to the running window.", role="muted")
        )
        column.addWidget(appearance)
        column.addStretch(1)
        return column

    def _build_right(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(8)

        paths = Panel("Storage", note="read-only")
        self._path_rows = {
            "base": MetricRow("Base directory"),
            "data": MetricRow("Runtime directory"),
            "logs": MetricRow("Log directory"),
            "database": MetricRow("Database file"),
        }
        for metric in self._path_rows.values():
            paths.body.addWidget(metric)
        column.addWidget(paths)

        profiles = Panel("Account profiles", note="from the database")
        self._profiles = DataTable(["Profile", "Login", "Server", "Terminal"])
        self._profiles.set_empty_message("No account profile stored")
        self._profiles.stretch_columns(stretch_last=True)
        profiles.body.addWidget(self._profiles, 1)
        column.addWidget(profiles, 1)

        source = Panel("Configuration source")
        source.body.addWidget(
            label(
                "Values are read from environment variables at startup: MT5_USE_MOCK, "
                "MT5_LOGIN, MT5_SERVER, MT5_TERMINAL_PATH, MT5_AUTO_LOGIN and MT5_THEME. "
                "They are not editable from this screen.",
                role="muted",
            )
        )
        column.addWidget(source)
        return column

    def refresh(self) -> None:
        settings = self._settings
        sandbox = bool(settings.use_mock_connector)
        self._mode_pill.set_state(
            "SANDBOX (mock connector)" if sandbox else "LIVE (MetaTrader 5 terminal)",
            "warn" if sandbox else "down",
        )
        self._rows["connector"].set_value(
            "MockMt5Connector" if sandbox else "MetaTrader5Connector"
        )
        self._rows["auto_login"].set_value("enabled" if settings.auto_login else "disabled")
        for key, value in (
            ("login", settings.account_login),
            ("server", settings.account_server),
            ("terminal", settings.account_terminal_path),
        ):
            self._rows[key].set_value(value or "not configured", None if value else "muted")

        for key, value in (
            ("base", settings.base_dir),
            ("data", settings.data_dir),
            ("logs", settings.log_dir),
            ("database", settings.db_path),
        ):
            full = str(value)
            self._path_rows[key].set_value(shorten_path(full))
            self._path_rows[key].setToolTip(full)

        self._profiles.clear_rows()
        for profile in self._accounts.list_profiles():
            self._profiles.append_row(
                [profile.profile_name, profile.login, profile.server, profile.terminal_path]
            )

    def _on_theme_changed(self, name: str) -> None:
        apply = self.context.get("set_theme")
        if callable(apply):
            apply(name)
