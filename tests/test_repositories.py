from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.models import OrderEvent
from database.db import Database
from database.repositories import AccountRepository, OrderEventRepository


def build(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    return AccountRepository(database), OrderEventRepository(database)


def test_account_repository_persists_profile(tmp_path):
    accounts, _ = build(tmp_path)
    created = accounts.upsert("demo", "123456", "MockBroker", "terminal.exe")
    loaded = accounts.list_profiles()
    assert created.profile_name == "demo"
    assert len(loaded) == 1


def test_get_profile_returns_none_when_absent(tmp_path):
    accounts, _ = build(tmp_path)
    assert accounts.get_profile("missing") is None


def test_get_profile_returns_the_stored_profile(tmp_path):
    accounts, _ = build(tmp_path)
    accounts.upsert("default-demo", "999888", "ICMarkets-Live", "terminal64.exe")
    profile = accounts.get_profile("default-demo")
    assert profile is not None
    assert (profile.login, profile.server) == ("999888", "ICMarkets-Live")


def test_upsert_replaces_an_existing_profile(tmp_path):
    accounts, _ = build(tmp_path)
    accounts.upsert("default-demo", "1", "First", "a.exe")
    accounts.upsert("default-demo", "2", "Second", "b.exe")
    profiles = accounts.list_profiles()
    assert len(profiles) == 1
    assert (profiles[0].login, profiles[0].server) == ("2", "Second")


def test_order_events_are_appended_in_order(tmp_path):
    _, events = build(tmp_path)
    for status in ("accepted", "failed"):
        events.record(
            OrderEvent(
                symbol="EURUSD",
                side="buy",
                volume=0.25,
                status=status,
                reason="test",
                created_at=datetime.now(timezone.utc),
            )
        )
    stored = events.list_all()
    assert isinstance(stored, list)
    assert [row["status"] for row in stored] == ["accepted", "failed"]
    assert stored[0]["symbol"] == "EURUSD"
    assert stored[0]["volume"] == 0.25
