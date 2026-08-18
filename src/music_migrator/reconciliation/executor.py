"""Apply provider-neutral reconciliation operations through destination primitives."""

from typing import Any, Protocol

from music_migrator.reconciliation.operations import (
    AddSavedTracks,
    AppendPlaylistTracks,
    ReplacePlaylistTracks,
)
from music_migrator.reconciliation.planner import ReconciliationPlan


class ReconciliationWriter(Protocol):
    """Minimal destination write surface required by reconciliation execution."""

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

    def add_favorites(self, track_ids: list[str]) -> int: ...


def apply_playlist_plan(
    writer: ReconciliationWriter,
    playlist: Any,
    plan: ReconciliationPlan,
) -> None:
    """Apply the playlist operations already selected by the planner."""
    for operation in plan.operations:
        if isinstance(operation, AppendPlaylistTracks):
            writer.append_playlist_tracks(
                playlist,
                list(operation.track_ids),
                expected_before=list(plan.current.track_ids),
            )
        elif isinstance(operation, ReplacePlaylistTracks):
            writer.replace_playlist_tracks(
                playlist,
                list(operation.track_ids),
                original_track_ids=list(plan.current.track_ids),
            )
        else:
            raise TypeError(f"unsupported playlist operation: {type(operation).__name__}")


def apply_saved_tracks_plan(writer: ReconciliationWriter, plan: ReconciliationPlan) -> None:
    """Apply saved-track operations already selected by the planner."""
    for operation in plan.operations:
        if not isinstance(operation, AddSavedTracks):
            raise TypeError(f"unsupported saved-track operation: {type(operation).__name__}")
        writer.add_favorites(list(operation.track_ids))
