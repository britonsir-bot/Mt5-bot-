from __future__ import annotations

import sys

from app import create_app_context
from core.exceptions import Mt5BotError
from gui.theme import apply_theme


def main() -> int:
    try:
        context = create_app_context()
    except Mt5BotError as exc:
        print(f"Unable to initialise the trading bot: {exc}", file=sys.stderr)
        return 2

    try:
        from PySide6.QtWidgets import QApplication

        from gui.main_window import MainWindow
    except ImportError:
        snapshot = context["account_service"].get_account_snapshot()
        print("MT5 AI Trading Bot backend scaffold is ready.")
        print(f"Connected: {snapshot.connected}")
        print(f"Account: {snapshot.login}@{snapshot.server}")
        return 0

    app = QApplication(sys.argv)
    apply_theme(app, context["settings"].theme)
    window = MainWindow(context)
    window.resize(1440, 900)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
