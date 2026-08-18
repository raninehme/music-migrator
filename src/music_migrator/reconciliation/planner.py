"""Compare current and desired collection state and select provider-neutral mutations."""

from dataclasses import dataclass

from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.reconciliation.operations import (
    AddSavedTracks,
    AppendPlaylistTracks,
    ReconciliationOperation,
    ReplacePlaylistTracks,
)
from music_migrator.reconciliation.policies import (
    PlaylistMode,
    desired_playlist_snapshot,
    desired_saved_tracks_snapshot,
)


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    """Describe current state, desired state, and the mutations required between them."""

    current: CollectionSnapshot
    desired: CollectionSnapshot
    operations: tuple[ReconciliationOperation, ...]

    @property
    def changed(self) -> bool:
        return bool(self.operations)


def plan_playlist(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
    *,
    mode: PlaylistMode,
) -> ReconciliationPlan:
    """Build an ordered playlist plan without performing provider writes."""
    desired = desired_playlist_snapshot(matched_track_ids, current, mode=mode)
    current_ids = current.track_ids
    desired_ids = desired.track_ids

    if current_ids == desired_ids:
        operations: tuple[ReconciliationOperation, ...] = ()
    elif current_ids == desired_ids[: len(current_ids)]:
        operations = (AppendPlaylistTracks(desired_ids[len(current_ids) :]),)
    else:
        operations = (ReplacePlaylistTracks(desired_ids),)

    return ReconciliationPlan(current=current, desired=desired, operations=operations)


def plan_saved_tracks(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
) -> ReconciliationPlan:
    """Build an unordered saved-track plan without performing provider writes."""
    desired = desired_saved_tracks_snapshot(matched_track_ids, current)
    current_ids = set(current.track_ids)
    missing = tuple(track_id for track_id in desired.track_ids if track_id not in current_ids)
    operations: tuple[ReconciliationOperation, ...] = (AddSavedTracks(missing),) if missing else ()
    return ReconciliationPlan(current=current, desired=desired, operations=operations)
