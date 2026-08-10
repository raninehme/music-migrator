import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import requests
import tidalapi

from music_migrator.core.models import Track

T = TypeVar("T")


class TidalDestination:
    def __init__(self, session: tidalapi.Session):
        self._session = session

    @classmethod
    def authenticate(cls, session_path: Path = Path(".tidal-session.json")) -> "TidalDestination":
        session = tidalapi.Session()
        if not session.login_session_file(session_path):
            raise RuntimeError("TIDAL authentication failed")
        return cls(session)

    def playlists_by_name(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        duplicates: set[str] = set()
        for playlist in self._session.user.playlists():
            if playlist.name in result:
                duplicates.add(playlist.name)
            result[playlist.name] = playlist
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(f"TIDAL contains duplicate playlist names: {names}")
        return result

    def create_playlist(self, name: str, description: str) -> Any:
        return self._session.user.create_playlist(name, description)

    def search_tracks(
        self,
        source: Track,
        limit: int = 20,
        before_request: Callable[[], None] | None = None,
    ) -> list[Track]:
        candidates: dict[str, Track] = {}
        for query in self._search_queries(source):
            if before_request:
                before_request()
            results = self._session.search(query, models=[tidalapi.Track], limit=limit)
            for raw in results.get("tracks", []):
                candidate = self._to_track(raw)
                candidates[candidate.source_id] = candidate
            if source.isrc and any(
                item.isrc and item.isrc.casefold() == source.isrc.casefold()
                for item in candidates.values()
            ):
                break
        return list(candidates.values())

    @classmethod
    def _search_queries(cls, source: Track) -> list[str]:
        primary_artist = source.artists[0]
        simplified = cls._simplify_title(source.title)
        queries = [f"{simplified} {primary_artist}"]
        if simplified != source.title:
            queries.append(f"{source.title} {primary_artist}")
        queries.append(simplified)
        return list(dict.fromkeys(queries))

    @staticmethod
    def _simplify_title(title: str) -> str:
        title = re.sub(r"\s+-\s+from\b.*$", "", title, flags=re.IGNORECASE)
        title = re.sub(
            r"\s*[\[(][^\])]*\b(?:feat(?:uring)?\.?|with)\b[^\])]*[\])]",
            "",
            title,
            flags=re.IGNORECASE,
        )
        return title.strip()

    def sync_playlist(self, playlist: Any, track_ids: list[str]) -> bool:
        existing = self.playlist_track_ids(playlist)
        if existing == track_ids:
            return False
        if existing == track_ids[: len(existing)]:
            self._add_tracks(playlist, track_ids[len(existing) :])
            return True
        if existing:
            self._retry_precondition(playlist, playlist.clear)
        self._add_tracks(playlist, track_ids)
        return True

    @staticmethod
    def playlist_track_ids(playlist: Any) -> list[str]:
        return [str(track.id) for track in playlist.tracks_paginated()]

    def add_favorites(self, track_ids: list[str]) -> int:
        existing = self._favorite_track_ids()
        missing = [track_id for track_id in track_ids if track_id not in existing]
        for start in range(0, len(missing), 50):
            self._session.user.favorites.add_track(missing[start : start + 50])
        return len(missing)

    def _favorite_track_ids(self) -> set[str]:
        ids: set[str] = set()
        offset = 0
        while True:
            page = self._session.user.favorites.tracks(limit=50, offset=offset)
            ids.update(str(track.id) for track in page)
            if len(page) < 50:
                return ids
            offset += 50

    def _add_tracks(self, playlist: Any, track_ids: list[str]) -> None:
        for start in range(0, len(track_ids), 50):
            chunk = track_ids[start : start + 50]
            self._retry_precondition(playlist, lambda chunk=chunk: playlist.add(chunk))

    @staticmethod
    def _retry_precondition(playlist: Any, operation: Callable[[], T]) -> T:
        for attempt in range(3):
            try:
                return operation()
            except requests.HTTPError as error:
                status = getattr(error.response, "status_code", None)
                if status != 412 or attempt == 2:
                    raise
                playlist._reparse()
        raise AssertionError("unreachable")

    @staticmethod
    def _to_track(raw: Any) -> Track:
        artists = tuple(artist.name for artist in getattr(raw, "artists", []) if artist.name)
        album = getattr(getattr(raw, "album", None), "name", None)
        return Track(
            source_id=str(raw.id),
            title=raw.name,
            artists=artists,
            album=album,
            duration_seconds=getattr(raw, "duration", None),
            isrc=getattr(raw, "isrc", None),
        )
