"""Persist migration runs and reconciliation operation progress."""

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from music_migrator.reconciliation.operations import ReconciliationOperation


@dataclass(frozen=True, slots=True)
class MigrationRun:
    """Identify a migration run and whether it resumes interrupted work."""

    run_id: str
    resumed: bool


class MigrationJournal(Protocol):
    """Store resumable progress without overriding remote reconciliation state."""

    def start_run(self, scope_key: str) -> MigrationRun: ...

    def begin_collection(self, run_id: str, collection_key: str) -> None: ...

    def plan_operations(
        self,
        run_id: str,
        collection_key: str,
        operations: tuple[ReconciliationOperation, ...],
    ) -> None: ...

    def complete_operation(
        self,
        run_id: str,
        collection_key: str,
        operation: ReconciliationOperation,
    ) -> None: ...

    def complete_collection(self, run_id: str, collection_key: str) -> None: ...

    def complete_run(self, run_id: str) -> None: ...


def operation_key(operation: ReconciliationOperation) -> str:
    """Return a bounded deterministic identifier for one reconciliation operation."""
    payload = "\0".join(operation.track_ids).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"{type(operation).__name__}:{digest}"


class NullMigrationJournal:
    """Disable persistence while preserving the Migrator journal contract."""

    def start_run(self, scope_key: str) -> MigrationRun:
        del scope_key
        return MigrationRun(str(uuid4()), False)

    def begin_collection(self, run_id: str, collection_key: str) -> None:
        del run_id, collection_key

    def plan_operations(
        self,
        run_id: str,
        collection_key: str,
        operations: tuple[ReconciliationOperation, ...],
    ) -> None:
        del run_id, collection_key, operations

    def complete_operation(
        self,
        run_id: str,
        collection_key: str,
        operation: ReconciliationOperation,
    ) -> None:
        del run_id, collection_key, operation

    def complete_collection(self, run_id: str, collection_key: str) -> None:
        del run_id, collection_key

    def complete_run(self, run_id: str) -> None:
        del run_id


class SQLiteMigrationJournal:
    """Track interrupted runs and operation progress in SQLite."""

    def __init__(self, path: Path):
        self._connection = sqlite3.connect(path, timeout=10)
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS migration_runs (
                run_id TEXT PRIMARY KEY,
                scope_key TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('running', 'completed')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS migration_runs_scope_status
                ON migration_runs(scope_key, status, created_at);

            CREATE TABLE IF NOT EXISTS migration_collections (
                run_id TEXT NOT NULL,
                collection_key TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('running', 'completed')),
                PRIMARY KEY (run_id, collection_key),
                FOREIGN KEY (run_id) REFERENCES migration_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS migration_operations (
                run_id TEXT NOT NULL,
                collection_key TEXT NOT NULL,
                operation_key TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'completed', 'superseded')),
                PRIMARY KEY (run_id, collection_key, operation_key),
                FOREIGN KEY (run_id, collection_key)
                    REFERENCES migration_collections(run_id, collection_key)
            );
            """
        )
        self._connection.commit()

    def start_run(self, scope_key: str) -> MigrationRun:
        row = self._connection.execute(
            "SELECT run_id FROM migration_runs "
            "WHERE scope_key = ? AND status = 'running' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (scope_key,),
        ).fetchone()
        if row:
            return MigrationRun(row[0], True)

        run_id = str(uuid4())
        self._connection.execute(
            "INSERT INTO migration_runs(run_id, scope_key, status) VALUES (?, ?, 'running')",
            (run_id, scope_key),
        )
        self._connection.commit()
        return MigrationRun(run_id, False)

    def begin_collection(self, run_id: str, collection_key: str) -> None:
        self._connection.execute(
            "INSERT INTO migration_collections(run_id, collection_key, status) "
            "VALUES (?, ?, 'running') "
            "ON CONFLICT(run_id, collection_key) DO UPDATE SET status = 'running'",
            (run_id, collection_key),
        )
        self._connection.commit()

    def plan_operations(
        self,
        run_id: str,
        collection_key: str,
        operations: tuple[ReconciliationOperation, ...],
    ) -> None:
        self._connection.execute(
            "UPDATE migration_operations SET status = 'superseded' "
            "WHERE run_id = ? AND collection_key = ? AND status = 'pending'",
            (run_id, collection_key),
        )
        for operation in operations:
            self._connection.execute(
                "INSERT INTO migration_operations("
                "run_id, collection_key, operation_key, operation_type, status"
                ") VALUES (?, ?, ?, ?, 'pending') "
                "ON CONFLICT(run_id, collection_key, operation_key) DO UPDATE SET "
                "operation_type = excluded.operation_type, status = 'pending'",
                (
                    run_id,
                    collection_key,
                    operation_key(operation),
                    type(operation).__name__,
                ),
            )
        self._connection.commit()

    def complete_operation(
        self,
        run_id: str,
        collection_key: str,
        operation: ReconciliationOperation,
    ) -> None:
        self._connection.execute(
            "UPDATE migration_operations SET status = 'completed' "
            "WHERE run_id = ? AND collection_key = ? AND operation_key = ?",
            (run_id, collection_key, operation_key(operation)),
        )
        self._connection.commit()

    def complete_collection(self, run_id: str, collection_key: str) -> None:
        self._connection.execute(
            "UPDATE migration_collections SET status = 'completed' "
            "WHERE run_id = ? AND collection_key = ?",
            (run_id, collection_key),
        )
        self._connection.commit()

    def complete_run(self, run_id: str) -> None:
        self._connection.execute(
            "UPDATE migration_runs SET status = 'completed', completed_at = CURRENT_TIMESTAMP "
            "WHERE run_id = ?",
            (run_id,),
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteMigrationJournal":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
