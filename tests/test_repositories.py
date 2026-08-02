from pathlib import Path

from database.db import Database
from database.repositories import AccountRepository


def test_account_repository_persists_profile(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.initialize()
    repo = AccountRepository(db)
    created = repo.upsert("demo", "123456", "MockBroker", "terminal.exe")
    loaded = repo.list_profiles()
    assert created.profile_name == "demo"
    assert len(loaded) == 1
