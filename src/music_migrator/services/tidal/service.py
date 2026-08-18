"""Adapt TIDAL APIs to provider-neutral source and destination contracts."""

import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import requests
import tidalapi

from music_migrator.config import RequestSettings
from music_migrator.core.retry import retry_request
from music_migrator.domain.models import Playlist, Track
from music_migrator.matching import strip_title_qualifiers
from music_migrator.services.tidal.auth import create_tidal_session

T = TypeVar("T")

logger = logging.getLogger(__name__)

TIDAL_DEFAULT_REQUEST_SETTINGS = RequestSettings(max_concurrency=8, rate_limit=8)
TIDAL_PAGE_SIZE = 50
TIDAL_WRITE_BATCH_SIZE = 50


def _pages(fetch: Callable[[int], list[T]]) -> Iterator[T]:
    offset = 0
    while True:
        page = retry_request(lambda offset=offset: fetch(offset))
        yield from page
        if len(page) < TIDAL_PAGE_SIZE:
            return
        offset += TIDAL_PAGE_SIZE


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
        for raw in _pages(lambda offset: playlist.tracks(limit=TIDAL_PAGE_SIZE, offset=offset)):
            yield _track_from_tidal(raw)

    def saved_tracks(self) -> Iterator[Track]:
        for raw in _pages(
            lambda offset: self._session.user.favorites.tracks(limit=TIDAL_PAGE_SIZE, offset=offset)
        ):
            yield _track_from_tidal(raw)


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

    def append_playlist_tracks(
        self,
        playlist: Any,
        track_ids: list[str],
        *,
        expected_before: list[str],
    ) -> None:
        desired = [*expected_before, *track_ids]
        self._add_tracks(playlist, desired, start=len(expected_before))

    def replace_playlist_tracks(
        self,
        playlist: Any,
        track_ids: list[str],
        *,
        original_track_ids: list[str],
    ) -> None:
        try:
            self._replace_tracks(playlist, track_ids, clear=bool(original_track_ids))
        except Exception:
            logger.warning("Playlist update failed; restoring original TIDAL tracks")
            try:
                self._replace_tracks(playlist, original_track_ids, clear=True)
            except Exception:
                logger.exception("Could not restore the original TIDAL playlist")
            raise

    @staticmethod
    def playlist_track_ids(playlist: Any) -> list[str]:
        return [
            str(track.id)
            for track in _pages(
                lambda offset: playlist.tracks(limit=TIDAL_PAGE_SIZE, offset=offset)
            )
        ]

    def add_saved_tracks(self, track_ids: list[str]) -> int:
        existing = self.saved_track_ids()
        missing = [track_id for track_id in track_ids if track_id not in existing]
        for start in range(0, len(missing), TIDAL_WRITE_BATCH_SIZE):
            self._session.user.favorites.add_track(missing[start : start + TIDAL_WRITE_BATCH_SIZE])
        return len(missing)

    def saved_track_ids(self) -> set[str]:
        return {
            str(track.id)
            for track in _pages(
                lambda offset: self._session.user.favorites.tracks(
                    limit=TIDAL_PAGE_SIZE, offset=offset
                )
            )
        }

    def _replace_tracks(self, playlist: Any, track_ids: list[str], *, clear: bool) -> None:
        if clear:
            self._retry_precondition(playlist, playlist.clear)
        self._add_tracks(playlist, track_ids, start=0)

    def _add_tracks(self, playlist: Any, desired: list[str], *, start: int) -> None:
        for offset in range(start, len(desired), TIDAL_WRITE_BATCH_SIZE):
            chunk = desired[offset : offset + TIDAL_WRITE_BATCH_SIZE]

            def add_or_confirm(offset: int = offset, chunk: list[str] = chunk) -> None:
                try:
                    self._retry_precondition(playlist, lambda chunk=chunk: playlist.add(chunk))
                except Exception as error:
                    current = self.playlist_track_ids(playlist)
                    if current == desired[: offset + len(chunk)]:
                        return
                    if current != desired[:offset]:
                        raise RuntimeError(str(error)) from error
                    raise

            retry_request(add_or_confirm)

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
