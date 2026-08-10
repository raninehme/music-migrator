from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from music_migrator.core.models import Playlist, Track


class MusicSource(Protocol):
    """Read playlists and saved tracks from a music service."""

    display_name: str

    def playlists(self) -> Iterable[Playlist]: ...

    def playlist(self, playlist_id: str) -> Playlist: ...

    def playlist_tracks(self, playlist_id: str) -> Iterable[Track]: ...

    def saved_tracks(self) -> Iterable[Track]: ...


class MusicDestination(Protocol):
    """Search and update playlists and favorites on a music service."""

    display_name: str

    def playlists_by_name(self) -> Mapping[str, Any]: ...

    def create_playlist(self, name: str, description: str) -> Any: ...

    def search_tracks(
        self,
        source: Track,
        limit: int = 20,
        before_request: Callable[[], None] | None = None,
    ) -> list[Track]: ...

    def playlist_track_ids(self, playlist: Any) -> list[str]: ...

    def sync_playlist(self, playlist: Any, track_ids: list[str]) -> bool: ...
