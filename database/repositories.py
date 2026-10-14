from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.models import AccountProfile, OrderEvent
from database.db import Database


class AccountRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def upsert(
        self, profile_name: str, login: str, server: str, terminal_path: str
    ) -> AccountProfile:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO accounts (profile_name, login, server, terminal_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(profile_name) DO UPDATE SET
                    login = excluded.login,
                    server = excluded.server,
                    terminal_path = excluded.terminal_path
                """,
                (profile_name, login, server, terminal_path, created_at),
            )
        return AccountProfile(
            profile_name=profile_name,
            login=login,
            server=server,
            terminal_path=terminal_path,
        )

    def get_profile(self, profile_name: str) -> AccountProfile | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT profile_name, login, server, terminal_path
                FROM accounts
                WHERE profile_name = ?
                """,
                (profile_name,),
            ).fetchone()
        if row is None:
            return None
        return AccountProfile(
            profile_name=row["profile_name"],
            login=row["login"],
            server=row["server"],
            terminal_path=row["terminal_path"],
        )

    def list_profiles(self) -> list[AccountProfile]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT profile_name, login, server, terminal_path
                FROM accounts
                ORDER BY profile_name ASC
                """
            ).fetchall()
        return [
            AccountProfile(
                profile_name=row["profile_name"],
                login=row["login"],
                server=row["server"],
                terminal_path=row["terminal_path"],
            )
            for row in rows
        ]


class OrderEventRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def record(self, event: OrderEvent) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO order_events (symbol, side, volume, status, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.symbol,
                    event.side,
                    event.volume,
                    event.status,
                    event.reason,
                    event.created_at.isoformat(),
                ),
            )

    def list_all(self) -> list[dict[str, Any]]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT symbol, side, volume, status, reason, created_at
                FROM order_events
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]
