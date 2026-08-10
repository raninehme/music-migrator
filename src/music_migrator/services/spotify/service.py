from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from music_migrator.config import SpotifyConfig
from music_migrator.core.models import Playlist, Track

SPOTIFY_SCOPES = "playlist-read-private playlist-read-collaborative user-library-read"


class SpotifySource:
    display_name = "Spotify"

    def __init__(self, client: spotipy.Spotify):
        self._client = client
        self._user_id: str | None = None

    @classmethod
    def authenticate(
        cls,
        config: SpotifyConfig,
        session_path: Path = Path(".spotify-session.json"),
    ) -> "SpotifySource":
        cache = CacheFileHandler(cache_path=str(session_path))
        oauth = SpotifyOAuth(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            scope=SPOTIFY_SCOPES,
            open_browser=config.open_browser,
            cache_handler=cache,
            requests_timeout=10,
        )
        return cls(spotipy.Spotify(auth_manager=oauth, requests_timeout=10))

    def playlists(self) -> Iterator[Playlist]:
        user_id = self._current_user_id()
        for raw in self._pages(
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
        pages = self._pages(
            lambda offset: self._client.playlist_items(
                playlist_id,
                limit=50,
                offset=offset,
                additional_types=("track",),
            )
        )
        yield from self._tracks_from_pages(pages)

    def saved_tracks(self) -> Iterator[Track]:
        pages = self._pages(
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

    @staticmethod
    def _pages(fetch: Callable[[int], dict[str, Any]]) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            page = fetch(offset)
            yield from page.get("items") or []
            if not page.get("next"):
                return
            limit = int(page.get("limit") or 50)
            offset += limit

    @classmethod
    def _tracks_from_pages(cls, entries: Iterator[dict[str, Any]]) -> Iterator[Track]:
        for entry in entries:
            raw_track = entry.get("item") or entry.get("track")
            track = cls._to_track(raw_track)
            if track is not None:
                yield track

    @staticmethod
    def _to_track(raw: dict[str, Any] | None) -> Track | None:
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
