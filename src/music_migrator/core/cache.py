import sqlite3
import threading
from pathlib import Path

from music_migrator.core.matching import MATCH_VERSION


class MatchCache:
    def __init__(self, path: Path, match_version: int = MATCH_VERSION):
        self._connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS matches ("
            "source_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL, "
            "match_version INTEGER NOT NULL DEFAULT 1)"
        )
        columns = {
            row[1] for row in self._connection.execute("PRAGMA table_info(matches)").fetchall()
        }
        if "match_version" not in columns:
            self._connection.execute(
                "ALTER TABLE matches ADD COLUMN match_version INTEGER NOT NULL DEFAULT 1"
            )
        self._connection.commit()
        self._match_version = match_version
        self._lock = threading.Lock()

    def get(self, source_id: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT destination_id FROM matches WHERE source_id = ? AND match_version = ?",
                (source_id, self._match_version),
            ).fetchone()
        return row[0] if row else None

    def put(self, source_id: str, destination_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO matches(source_id, destination_id, match_version) VALUES (?, ?, ?) "
                "ON CONFLICT(source_id) DO UPDATE SET destination_id = excluded.destination_id, "
                "match_version = excluded.match_version",
                (source_id, destination_id, self._match_version),
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
