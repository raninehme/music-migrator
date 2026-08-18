"""Persist successful track matches independently from destination writes."""

import sqlite3
import threading
from pathlib import Path

from music_migrator.matching.scoring import MATCH_VERSION


class MatchCache:
    def __init__(self, path: Path, match_version: int = MATCH_VERSION):
        self._connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS matches ("
            "source_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL, "
            "match_version INTEGER NOT NULL DEFAULT 1, source_fingerprint TEXT)"
        )
        columns = {
            row[1] for row in self._connection.execute("PRAGMA table_info(matches)").fetchall()
        }
        if "match_version" not in columns:
            self._connection.execute(
                "ALTER TABLE matches ADD COLUMN match_version INTEGER NOT NULL DEFAULT 1"
            )
        if "source_fingerprint" not in columns:
            self._connection.execute("ALTER TABLE matches ADD COLUMN source_fingerprint TEXT")
        self._connection.commit()
        self._match_version = match_version
        self._lock = threading.Lock()

    def get(self, source_id: str, source_fingerprint: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT destination_id, source_fingerprint FROM matches "
                "WHERE source_id = ? AND match_version = ?",
                (source_id, self._match_version),
            ).fetchone()
            if row and row[1] is None:
                self._connection.execute(
                    "UPDATE matches SET source_fingerprint = ? WHERE source_id = ?",
                    (source_fingerprint, source_id),
                )
                self._connection.commit()
                return row[0]
        return row[0] if row and row[1] == source_fingerprint else None

    def put(self, source_id: str, destination_id: str, source_fingerprint: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO matches("
                "source_id, destination_id, match_version, source_fingerprint"
                ") VALUES (?, ?, ?, ?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                "destination_id = excluded.destination_id, "
                "match_version = excluded.match_version, "
                "source_fingerprint = excluded.source_fingerprint",
                (source_id, destination_id, self._match_version, source_fingerprint),
            )
            self._connection.commit()

    def discard(self, source_ids: list[str]) -> None:
        if not source_ids:
            return
        with self._lock:
            self._connection.executemany(
                "DELETE FROM matches WHERE source_id = ?",
                ((source_id,) for source_id in source_ids),
            )
            self._connection.commit()

    def clear(self) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM matches")
            self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "MatchCache":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
