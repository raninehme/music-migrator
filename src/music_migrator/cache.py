import sqlite3
import threading
from pathlib import Path


class MatchCache:
    def __init__(self, path: Path):
        self._connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS matches ("
            "source_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL)"
        )
        self._connection.commit()
        self._lock = threading.Lock()

    def get(self, source_id: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT destination_id FROM matches WHERE source_id = ?", (source_id,)
            ).fetchone()
        return row[0] if row else None

    def put(self, source_id: str, destination_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO matches(source_id, destination_id) VALUES (?, ?) "
                "ON CONFLICT(source_id) DO UPDATE SET destination_id = excluded.destination_id",
                (source_id, destination_id),
            )
            self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "MatchCache":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
