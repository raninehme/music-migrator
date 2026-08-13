import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import requests
import tidalapi

from music_migrator.core.matching import strip_title_qualifiers
from music_migrator.core.models import Playlist, Track
from music_migrator.services.tidal.auth import create_tidal_session

T = TypeVar("T")

logger = logging.getLogger(__name__)

TIDAL_PAGE_SIZE = 50
TIDAL_WRITE_BATCH_SIZE = 50


def _track_from_tidal(raw: Any) -> Track:
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


class TidalSource:
    display_name = "TIDAL"

    saved_tracks_name = "Favorites"

    def __init__(self, session: tidalapi.Session):
        self._session = session

    @classmethod
    def authenticate(cls, session_path: Path = Path(".tidal-session.json")) -> "TidalSource":
        return cls(create_tidal_session(session_path))

    def playlists(self) -> Iterator[Playlist]:
        for raw in self._session.user.playlists():
            yield Playlist(
                source_id=str(raw.id),
                name=raw.name,
                description=getattr(raw, "description", "") or "",
            )

    def playlist(self, playlist_id: str) -> Playlist:
        raw = self._session.playlist(playlist_id)
        return Playlist(
            source_id=str(raw.id),
            name=raw.name,
            description=getattr(raw, "description", "") or "",
        )

    def playlist_tracks(self, playlist_id: str) -> Iterator[Track]:
        playlist = self._session.playlist(playlist_id)
        for raw in playlist.tracks_paginated():
            yield _track_from_tidal(raw)

    def saved_tracks(self) -> Iterator[Track]:
        offset = 0
        while True:
            page = self._session.user.favorites.tracks(limit=TIDAL_PAGE_SIZE, offset=offset)
            for raw in page:
                yield _track_from_tidal(raw)
            if len(page) < TIDAL_PAGE_SIZE:
                return
            offset += TIDAL_PAGE_SIZE


class TidalDestination:
    display_name = "TIDAL"

    saved_tracks_name = "Favorites"

    def __init__(self, session: tidalapi.Session):
        self._session = session

    @classmethod
    def authenticate(cls, session_path: Path = Path(".tidal-session.json")) -> "TidalDestination":
        return cls(create_tidal_session(session_path))

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
                candidate = _track_from_tidal(raw)
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
        title = strip_title_qualifiers(title)
        title = re.sub(r"\s+-\s+.*$", "", title)
        return title.strip()

    def sync_playlist(self, playlist: Any, track_ids: list[str]) -> bool:
        existing = self.playlist_track_ids(playlist)
        if existing == track_ids:
            return False
        if existing == track_ids[: len(existing)]:
            self._add_tracks(playlist, track_ids[len(existing) :])
            return True
        try:
            self._replace_tracks(playlist, track_ids, clear=bool(existing))
        except Exception:
            logger.warning("Playlist update failed; restoring original TIDAL tracks")
            try:
                self._replace_tracks(playlist, existing, clear=True)
            except Exception:
                logger.exception("Could not restore the original TIDAL playlist")
            raise
        return True

    @staticmethod
    def playlist_track_ids(playlist: Any) -> list[str]:
        return [str(track.id) for track in playlist.tracks_paginated()]

    def add_favorites(self, track_ids: list[str]) -> int:
        existing = self.favorite_track_ids()
        missing = [track_id for track_id in track_ids if track_id not in existing]
        for start in range(0, len(missing), TIDAL_WRITE_BATCH_SIZE):
            self._session.user.favorites.add_track(missing[start : start + TIDAL_WRITE_BATCH_SIZE])
        return len(missing)

    def favorite_track_ids(self) -> set[str]:
        ids: set[str] = set()
        offset = 0
        while True:
            page = self._session.user.favorites.tracks(limit=TIDAL_PAGE_SIZE, offset=offset)
            ids.update(str(track.id) for track in page)
            if len(page) < TIDAL_PAGE_SIZE:
                return ids
            offset += TIDAL_PAGE_SIZE

    def _replace_tracks(self, playlist: Any, track_ids: list[str], *, clear: bool) -> None:
        if clear:
            self._retry_precondition(playlist, playlist.clear)
        self._add_tracks(playlist, track_ids)

    def _add_tracks(self, playlist: Any, track_ids: list[str]) -> None:
        for start in range(0, len(track_ids), TIDAL_WRITE_BATCH_SIZE):
            chunk = track_ids[start : start + TIDAL_WRITE_BATCH_SIZE]
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
