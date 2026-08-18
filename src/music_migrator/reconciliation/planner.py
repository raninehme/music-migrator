"""Compare current and desired collection state before provider mutation."""

from dataclasses import dataclass

from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.reconciliation.policies import (
    PlaylistMode,
    desired_playlist_snapshot,
    desired_saved_tracks_snapshot,
)


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    """Describe provider-neutral current and desired state for one collection."""

    current: CollectionSnapshot
    desired: CollectionSnapshot

    @property
    def changed(self) -> bool:
        return self.current.track_ids != self.desired.track_ids

    @property
    def append_from(self) -> int | None:
        """Return the append offset when current state is an ordered desired prefix."""
        if not self.current.ordered or not self.desired.ordered:
            return None
        current = self.current.track_ids
        desired = self.desired.track_ids
        if current == desired[: len(current)]:
            return len(current)
        return None


def plan_playlist(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
    *,
    mode: PlaylistMode,
) -> ReconciliationPlan:
    """Build a playlist reconciliation plan without performing provider writes."""
    return ReconciliationPlan(
        current=current,
        desired=desired_playlist_snapshot(matched_track_ids, current, mode=mode),
    )


def plan_saved_tracks(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
) -> ReconciliationPlan:
    """Build a saved-track reconciliation plan without performing provider writes."""
    return ReconciliationPlan(
        current=current,
        desired=desired_saved_tracks_snapshot(matched_track_ids, current),
    )
