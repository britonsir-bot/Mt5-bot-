from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from core.exceptions import ConfigurationError

BOOLEAN_LITERALS = {
    "1": True,
    "0": False,
    "true": True,
    "false": False,
    "yes": True,
    "no": False,
    "on": True,
    "off": False,
}


def parse_boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value not in BOOLEAN_LITERALS:
        raise ConfigurationError(
            f"{name} must be one of {sorted(BOOLEAN_LITERALS)}, got {raw!r}."
        )
    return BOOLEAN_LITERALS[value]


def parse_optional_text(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


@dataclass(slots=True)
class Settings:
    app_name: str
    base_dir: Path
    data_dir: Path
    config_dir: Path
    log_dir: Path
    db_path: Path
    use_mock_connector: bool
    account_login: str | None = None
    account_server: str | None = None
    account_terminal_path: str | None = None
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
            use_mock_connector=parse_boolean("MT5_USE_MOCK", True),
            account_login=parse_optional_text("MT5_LOGIN"),
            account_server=parse_optional_text("MT5_SERVER"),
            account_terminal_path=parse_optional_text("MT5_TERMINAL_PATH"),
            auto_login=parse_boolean("MT5_AUTO_LOGIN", False),
            theme=os.getenv("MT5_THEME", "dark").strip() or "dark",
        )
