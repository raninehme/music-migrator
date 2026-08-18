"""Define provider-neutral mutations produced by reconciliation planning."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppendPlaylistTracks:
    """Append tracks to an ordered playlist without changing its existing prefix."""

    track_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReplacePlaylistTracks:
    """Replace the complete ordered contents of a playlist."""

    track_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AddSavedTracks:
    """Add missing tracks to an unordered saved-track collection."""

    track_ids: tuple[str, ...]


ReconciliationOperation = AppendPlaylistTracks | ReplacePlaylistTracks | AddSavedTracks
