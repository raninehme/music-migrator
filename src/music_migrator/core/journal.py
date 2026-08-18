import sqlite3
from pathlib import Path
from typing import Literal

RunStatus = Literal["running", "completed"]
CollectionStatus = Literal["in_progress", "completed"]


class MigrationJournal:
    """Persist migration progress without treating local state as remote truth."""

    def __init__(self, path: Path):
        self._connection = sqlite3.connect(path, timeout=10)
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS migration_runs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "route_key TEXT NOT NULL, "
            "mode TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "completed_at TEXT)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS collection_progress ("
            "run_id INTEGER NOT NULL, "
            "collection_key TEXT NOT NULL, "
            "kind TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "desired_fingerprint TEXT NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (run_id, collection_key), "
            "FOREIGN KEY (run_id) REFERENCES migration_runs(id))"
        )
        self._connection.commit()

    def begin_or_resume(self, route_key: str, mode: str) -> tuple[int, bool]:
        row = self._connection.execute(
            "SELECT id FROM migration_runs "
            "WHERE route_key = ? AND mode = ? AND status = 'running' "
            "ORDER BY id DESC LIMIT 1",
            (route_key, mode),
        ).fetchone()
        if row:
            return int(row[0]), True

        cursor = self._connection.execute(
            "INSERT INTO migration_runs(route_key, mode, status) VALUES (?, ?, 'running')",
            (route_key, mode),
        )
        self._connection.commit()
        return int(cursor.lastrowid), False

    def mark_collection(
        self,
        run_id: int,
        collection_key: str,
        *,
        kind: str,
        status: CollectionStatus,
        desired_fingerprint: str,
    ) -> None:
        self._connection.execute(
            "INSERT INTO collection_progress("
            "run_id, collection_key, kind, status, desired_fingerprint"
            ") VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(run_id, collection_key) DO UPDATE SET "
            "kind = excluded.kind, "
            "status = excluded.status, "
            "desired_fingerprint = excluded.desired_fingerprint, "
            "updated_at = CURRENT_TIMESTAMP",
            (run_id, collection_key, kind, status, desired_fingerprint),
        )
        self._connection.commit()

    def collection_status(self, run_id: int, collection_key: str) -> str | None:
        row = self._connection.execute(
            "SELECT status FROM collection_progress WHERE run_id = ? AND collection_key = ?",
            (run_id, collection_key),
        ).fetchone()
        return str(row[0]) if row else None

    def complete_run(self, run_id: int) -> None:
        self._connection.execute(
            "UPDATE migration_runs SET status = 'completed', completed_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (run_id,),
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "MigrationJournal":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
