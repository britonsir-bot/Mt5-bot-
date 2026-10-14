from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path

LOGGER_NAME = "mt5_bot"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event_payload"):
            payload["payload"] = record.event_payload
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _LogTarget:
    path: Path | None = None


def configure_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    log_dir = Path(log_dir)
    log_file = (log_dir / "application.log").resolve()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    if _LogTarget.path == log_file and logger.handlers:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JsonFormatter())
    logger.addHandler(stream_handler)

    _LogTarget.path = log_file
    return logger
