from __future__ import annotations

import sys

from app import create_app_context


def main() -> int:
    context = create_app_context()

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
    window = MainWindow(context)
    window.resize(1024, 720)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
