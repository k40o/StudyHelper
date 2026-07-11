"""Database bootstrap: engine + session factory.

Wraps SQLAlchemy so the rest of the app asks the ``Database`` for sessions and
never touches engine configuration directly.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

logger = logging.getLogger(__name__)

# Default login for data created before accounts existed. Only used once, to
# adopt pre-existing rows during the one-time migration below.
LEGACY_USER_EMAIL = "legacy@studyhelper.local"
LEGACY_USER_PASSWORD = "changeme123"


class Database:
    def __init__(self, url: str) -> None:
        # check_same_thread=False: the folder watcher runs in a background
        # thread and needs to use sessions created on the main thread's engine.
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self._engine = create_engine(url, echo=False, future=True, connect_args=connect_args)

        # Enforce ON DELETE CASCADE for SQLite (off by default per-connection),
        # so deleting a document also removes its reviews/attempts.
        if url.startswith("sqlite"):

            @event.listens_for(self._engine, "connect")
            def _fk_pragma(dbapi_conn, _record):  # pragma: no cover - tiny glue
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def create_all(self) -> None:
        """Create any tables that don't yet exist, then adopt any pre-account
        rows (documents/player/achievements from before ``users`` existed) into
        a single legacy account so nothing is silently lost."""
        inspector = inspect(self._engine)
        pre_existing_tables = set(inspector.get_table_names())
        Base.metadata.create_all(self._engine)
        self._migrate_legacy_single_user(pre_existing_tables)

    def _migrate_legacy_single_user(self, pre_existing_tables: set[str]) -> None:
        needs_migration = {"documents", "player", "achievements"} & pre_existing_tables
        if not needs_migration:
            return
        with self._engine.begin() as conn:
            for table in needs_migration:
                cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
                if "user_id" in cols:
                    continue  # already migrated
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"))
                legacy_id = self._ensure_legacy_user(conn)
                conn.execute(
                    text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
                    {"uid": legacy_id},
                )
                if table == "achievements":
                    # The old schema uniqued `key` alone; the new one uniques
                    # (user_id, key). Drop the stale single-column unique index
                    # or a second account's first achievement will collide.
                    for row in conn.execute(text("PRAGMA index_list(achievements)")):
                        index_name, is_unique = row[1], row[2]
                        cols = [
                            r[2] for r in conn.execute(text(f"PRAGMA index_info({index_name})"))
                        ]
                        if is_unique and cols == ["key"]:
                            conn.execute(text(f"DROP INDEX {index_name}"))
                logger.warning(
                    "Migrated pre-account rows in '%s' to legacy account (%s / %s) — "
                    "log in with these and change the password.",
                    table, LEGACY_USER_EMAIL, LEGACY_USER_PASSWORD,
                )

    def _ensure_legacy_user(self, conn) -> int:
        from ...core.security import hash_password  # local import avoids a cycle

        row = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": LEGACY_USER_EMAIL}
        ).first()
        if row is not None:
            return row[0]
        result = conn.execute(
            text("INSERT INTO users (email, password_hash) VALUES (:email, :hash)"),
            {"email": LEGACY_USER_EMAIL, "hash": hash_password(LEGACY_USER_PASSWORD)},
        )
        return result.lastrowid

    def session(self) -> Session:
        return self._session_factory()

    @contextmanager
    def unit_of_work(self) -> Iterator[Session]:
        """A transactional scope: commit on success, roll back on error."""
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self._engine.dispose()
