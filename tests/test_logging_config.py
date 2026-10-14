from __future__ import annotations

import json

from core.logging_config import configure_logging


def read_records(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_writes_json_records_into_the_requested_directory(tmp_path):
    logger = configure_logging(tmp_path / "logs")
    logger.info("context ready", extra={"event_payload": {"mock": True}})
    records = read_records(tmp_path / "logs" / "application.log")
    assert records[-1]["message"] == "context ready"
    assert records[-1]["payload"] == {"mock": True}
    assert records[-1]["level"] == "INFO"


def test_reconfigures_when_the_directory_changes(tmp_path):
    first = configure_logging(tmp_path / "a")
    first.info("first")
    second = configure_logging(tmp_path / "b")
    second.info("second")
    assert "first" in (tmp_path / "a" / "application.log").read_text(encoding="utf-8")
    assert "second" not in (tmp_path / "a" / "application.log").read_text(encoding="utf-8")
    assert "second" in (tmp_path / "b" / "application.log").read_text(encoding="utf-8")


def test_repeated_configuration_of_the_same_directory_is_idempotent(tmp_path):
    logger = configure_logging(tmp_path)
    logger.info("once")
    configure_logging(tmp_path)
    logger.info("twice")
    records = read_records(tmp_path / "application.log")
    assert [record["message"] for record in records] == ["once", "twice"]


def test_exception_details_are_serialised(tmp_path):
    logger = configure_logging(tmp_path)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("failed")
    records = read_records(tmp_path / "application.log")
    assert "RuntimeError: boom" in records[-1]["exception"]
