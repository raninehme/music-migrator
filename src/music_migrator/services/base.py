"""Define provider contracts for discovery, matching, and primitive destination writes."""

from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from music_migrator.domain.models import Playlist, Track


class MusicSource(Protocol):
    """Read playlists and saved tracks from a music service."""

    display_name: str
    saved_tracks_name: str

    def playlists(self) -> Iterable[Playlist]: ...

    def playlist(self, playlist_id: str) -> Playlist: ...

    def playlist_tracks(self, playlist_id: str) -> Iterable[Track]: ...

    def saved_tracks(self) -> Iterable[Track]: ...


class MusicDestination(Protocol):
    """Search destination state and execute provider-specific write primitives."""

    display_name: str
    saved_tracks_name: str

    def playlists_by_name(self) -> Mapping[str, Any]: ...

    def create_playlist(self, name: str, description: str) -> Any: ...

    def search_tracks(
        self,
        source: Track,
        limit: int = 20,
        before_request: Callable[[], None] | None = None,
    ) -> list[Track]: ...

    def playlist_track_ids(self, playlist: Any) -> list[str]: ...

    def append_playlist_tracks(
        self,
        playlist: Any,
        track_ids: list[str],
        *,
        expected_before: list[str],
    ) -> None: ...

    def replace_playlist_tracks(
        self,
        playlist: Any,
        track_ids: list[str],
        *,
        original_track_ids: list[str],
    ) -> None: ...

    def saved_track_ids(self) -> set[str]: ...

    def add_saved_tracks(self, track_ids: list[str]) -> int: ...
