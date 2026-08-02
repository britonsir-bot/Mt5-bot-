from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class Settings:
    app_name: str
    base_dir: Path
    data_dir: Path
    config_dir: Path
    log_dir: Path
    db_path: Path
    use_mock_connector: bool
    auto_login: bool = False
    theme: str = "dark"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "Settings":
        resolved_base_dir = base_dir or Path(__file__).resolve().parents[1]
        data_dir = resolved_base_dir / "runtime"
        return cls(
            app_name="MT5 AI Trading Bot",
            base_dir=resolved_base_dir,
            data_dir=data_dir,
            config_dir=data_dir / "config",
            log_dir=data_dir / "logs",
            db_path=data_dir / "db" / "mt5_bot.sqlite3",
            use_mock_connector=os.getenv("MT5_USE_MOCK", "1") != "0",
            auto_login=os.getenv("MT5_AUTO_LOGIN", "0") == "1",
        )
