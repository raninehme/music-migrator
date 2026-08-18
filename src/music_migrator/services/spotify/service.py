"""Adapt Spotify APIs to provider-neutral source and destination contracts."""

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import spotipy

from music_migrator.config import RequestSettings
from music_migrator.core.models import Playlist, Track
from music_migrator.core.retry import retry_request
from music_migrator.services.spotify.auth import SPOTIFY_DESTINATION_SCOPES, create_spotify_client
from music_migrator.services.spotify.config import SpotifyConfig

logger = logging.getLogger(__name__)

SPOTIFY_DEFAULT_REQUEST_SETTINGS = RequestSettings(max_concurrency=3, rate_limit=3)
SPOTIFY_LIBRARY_BATCH_SIZE = 40
SPOTIFY_PLAYLIST_PAGE_SIZE = 50
SPOTIFY_SEARCH_LIMIT = 10


def _pages(fetch: Callable[[int], dict[str, Any]]) -> Iterator[dict[str, Any]]:
    offset = 0
    while True:
        page = retry_request(lambda offset=offset: fetch(offset))
        yield from page.get("items") or []
        if not page.get("next"):
            return
        limit = int(page.get("limit") or 50)
        offset += limit


def _track_from_spotify(raw: dict[str, Any] | None) -> Track | None:
    if not raw or raw.get("type", "track") != "track":
        return None

    source_id = raw.get("id")
    title = raw.get("name")
    artists = tuple(artist["name"] for artist in raw.get("artists") or [] if artist.get("name"))
    if not source_id or not title or not artists:
        return None

    album = raw.get("album") or {}
    external_ids = raw.get("external_ids") or {}
    duration_ms = raw.get("duration_ms")
    return Track(
        source_id=source_id,
        title=title,
        artists=artists,
        album=album.get("name"),
        duration_seconds=duration_ms / 1000 if duration_ms is not None else None,
        isrc=external_ids.get("isrc"),
    )


class SpotifySource:
    display_name = "Spotify"

    saved_tracks_name = "Liked Songs"

    def __init__(self, client: spotipy.Spotify):
        self._client = client
        self._user_id: str | None = None

    @classmethod
    def authenticate(
        cls,
        config: SpotifyConfig,
        session_path: Path = Path(".spotify-session.json"),
    ) -> "SpotifySource":
        return cls(create_spotify_client(config, session_path))

    def playlists(self) -> Iterator[Playlist]:
        user_id = self._current_user_id()
        for raw in _pages(
            lambda offset: self._client.current_user_playlists(limit=50, offset=offset)
        ):
            owner_id = (raw.get("owner") or {}).get("id")
            if owner_id != user_id and not raw.get("collaborative", False):
                continue
            playlist_id = raw.get("id")
            name = raw.get("name")
            if not playlist_id or not name:
                continue
            yield Playlist(
                source_id=playlist_id,
                name=name,
                description=raw.get("description") or "",
            )

    def playlist(self, playlist_id: str) -> Playlist:
        raw = self._client.playlist(playlist_id)
        if not raw.get("id") or not raw.get("name"):
            raise ValueError(f"Spotify returned an invalid playlist: {playlist_id}")
        return Playlist(
            source_id=raw["id"],
            name=raw["name"],
            description=raw.get("description") or "",
        )

    def playlist_tracks(self, playlist_id: str) -> Iterator[Track]:
        pages = _pages(
            lambda offset: self._client.playlist_items(
                playlist_id,
                limit=50,
                offset=offset,
                additional_types=("track",),
            )
        )
        yield from self._tracks_from_pages(pages)

    def saved_tracks(self) -> Iterator[Track]:
        pages = _pages(
            lambda offset: self._client.current_user_saved_tracks(limit=50, offset=offset)
        )
        yield from self._tracks_from_pages(pages)

    def _current_user_id(self) -> str:
        if self._user_id is None:
            profile = self._client.current_user()
            user_id = profile.get("id")
            if not user_id:
                raise ValueError("Spotify profile did not contain a user ID")
            self._user_id = user_id
        return self._user_id

    @classmethod
    def _tracks_from_pages(cls, entries: Iterator[dict[str, Any]]) -> Iterator[Track]:
        for entry in entries:
            raw_track = entry.get("item") or entry.get("track")
            track = _track_from_spotify(raw_track)
            if track is not None:
                yield track


class SpotifyDestination:
    display_name = "Spotify"

    saved_tracks_name = "Liked Songs"

    def __init__(self, client: spotipy.Spotify):
        self._client = client
        self._user_id: str | None = None

    @classmethod
    def authenticate(
        cls,
        config: SpotifyConfig,
        session_path: Path = Path(".spotify-session.json"),
    ) -> "SpotifyDestination":
        return cls(create_spotify_client(config, session_path, SPOTIFY_DESTINATION_SCOPES))

    def playlists_by_name(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        duplicates: set[str] = set()
        user_id = self._current_user_id()
        playlists = _pages(
            lambda offset: self._client.current_user_playlists(limit=50, offset=offset)
        )
        for playlist in playlists:
            owner_id = (playlist.get("owner") or {}).get("id")
            if owner_id != user_id and not playlist.get("collaborative", False):
                continue
            name = playlist.get("name")
            playlist_id = playlist.get("id")
            if not name or not playlist_id:
                continue
            if name in result:
                duplicates.add(name)
            result[name] = playlist
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(f"Spotify contains duplicate playlist names: {names}")
        return result

    def create_playlist(self, name: str, description: str) -> dict[str, Any]:
        return self._client.current_user_playlist_create(
            name,
            public=False,
            description=description,
        )

    def search_tracks(
        self,
        source: Track,
        limit: int = 20,
        before_request: Callable[[], None] | None = None,
    ) -> list[Track]:
        candidates: dict[str, Track] = {}
        queries = []
        if source.isrc:
            queries.append(f"isrc:{source.isrc}")
        queries.append(f"{source.title} {source.artists[0]}")
        for query in queries:
            if before_request:
                before_request()
            request_limit = max(1, min(limit, SPOTIFY_SEARCH_LIMIT))
            results = self._client.search(q=query, type="track", limit=request_limit)
            for raw in (results.get("tracks") or {}).get("items") or []:
                candidate = _track_from_spotify(raw)
                if candidate:
                    candidates[candidate.source_id] = candidate
            if source.isrc and any(
                item.isrc and item.isrc.casefold() == source.isrc.casefold()
                for item in candidates.values()
            ):
                break
        return list(candidates.values())

    def playlist_track_ids(self, playlist: Any) -> list[str]:
        playlist_id = self._playlist_id(playlist)
        entries = _pages(
            lambda offset: self._client.playlist_items(
                playlist_id,
                limit=SPOTIFY_PLAYLIST_PAGE_SIZE,
                offset=offset,
                additional_types=("track",),
            )
        )
        ids = []
        for entry in entries:
            raw = entry.get("item") or entry.get("track")
            if raw and raw.get("id"):
                ids.append(raw["id"])
        return ids

    def append_playlist_tracks(
        self,
        playlist: Any,
        track_ids: list[str],
        *,
        expected_before: list[str],
    ) -> None:
        playlist_id = self._playlist_id(playlist)
        desired = [*expected_before, *track_ids]
        self._add_tracks(playlist_id, desired, start=len(expected_before))

    def replace_playlist_tracks(
        self,
        playlist: Any,
        track_ids: list[str],
        *,
        original_track_ids: list[str],
    ) -> None:
        playlist_id = self._playlist_id(playlist)
        try:
            self._replace_tracks(playlist_id, track_ids)
        except Exception:
            logger.warning("Playlist update failed; restoring original Spotify tracks")
            try:
                self._replace_tracks(playlist_id, original_track_ids)
            except Exception:
                logger.exception("Could not restore the original Spotify playlist")
            raise

    def saved_track_ids(self) -> set[str]:
        entries = _pages(
            lambda offset: self._client.current_user_saved_tracks(limit=50, offset=offset)
        )
        ids: set[str] = set()
        for entry in entries:
            raw = entry.get("item") or entry.get("track")
            if raw and raw.get("id"):
                ids.add(raw["id"])
        return ids

    def add_saved_tracks(self, track_ids: list[str]) -> int:
        added = 0
        for start in range(0, len(track_ids), SPOTIFY_LIBRARY_BATCH_SIZE):
            chunk = track_ids[start : start + SPOTIFY_LIBRARY_BATCH_SIZE]
            existing = self._client.current_user_saved_tracks_contains(chunk)
            missing = [
                track_id for track_id, present in zip(chunk, existing, strict=True) if not present
            ]
            if missing:
                self._client.current_user_saved_tracks_add(missing)
                added += len(missing)
        return added

    def _current_user_id(self) -> str:
        if self._user_id is None:
            profile = self._client.current_user()
            user_id = profile.get("id")
            if not user_id:
                raise ValueError("Spotify profile did not contain a user ID")
            self._user_id = user_id
        return self._user_id

    def _replace_tracks(self, playlist_id: str, track_ids: list[str]) -> None:
        self._client.playlist_replace_items(playlist_id, track_ids[:100])
        self._add_tracks(playlist_id, track_ids, start=min(100, len(track_ids)))

    def _add_tracks(self, playlist_id: str, desired: list[str], *, start: int) -> None:
        for offset in range(start, len(desired), 100):
            chunk = desired[offset : offset + 100]

            def add_or_confirm(offset: int = offset, chunk: list[str] = chunk) -> None:
                try:
                    self._client.playlist_add_items(playlist_id, chunk)
                except Exception as error:
                    current = self.playlist_track_ids({"id": playlist_id})
                    if current == desired[: offset + len(chunk)]:
                        return
                    if current != desired[:offset]:
                        raise RuntimeError(str(error)) from error
                    raise

            retry_request(add_or_confirm)

    @staticmethod
    def _playlist_id(playlist: Any) -> str:
        playlist_id = playlist.get("id") if isinstance(playlist, dict) else None
        if not playlist_id:
            raise ValueError("Spotify playlist did not contain an ID")
        return playlist_id
