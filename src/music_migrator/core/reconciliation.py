from dataclasses import dataclass
from typing import Literal

from music_migrator.core.collections import CollectionSnapshot

PlaylistMode = Literal["combine", "replace"]


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    current: CollectionSnapshot
    desired: CollectionSnapshot

    @property
    def changed(self) -> bool:
        return self.current.track_ids != self.desired.track_ids

    @property
    def append_from(self) -> int | None:
        if not self.current.ordered or not self.desired.ordered:
            return None
        current = self.current.track_ids
        desired = self.desired.track_ids
        if current == desired[: len(current)]:
            return len(current)
        return None


def desired_playlist_snapshot(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
    *,
    mode: PlaylistMode,
) -> CollectionSnapshot:
    if current.kind != "playlist":
        raise ValueError("playlist reconciliation requires a playlist snapshot")
    if mode == "replace":
        desired = matched_track_ids
    elif mode == "combine":
        matched_ids = set(matched_track_ids)
        desired = [
            *matched_track_ids,
            *(track_id for track_id in current.track_ids if track_id not in matched_ids),
        ]
    else:
        raise ValueError(f"unknown migration mode: {mode}")
    return CollectionSnapshot.playlist(current.key, current.name, desired)


def desired_saved_tracks_snapshot(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
) -> CollectionSnapshot:
    if current.kind != "saved_tracks":
        raise ValueError("saved-track reconciliation requires a saved-tracks snapshot")
    desired = set(current.track_ids)
    desired.update(matched_track_ids)
    return CollectionSnapshot.saved_tracks(current.key, current.name, desired)


def plan_playlist(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
    *,
    mode: PlaylistMode,
) -> ReconciliationPlan:
    return ReconciliationPlan(
        current=current,
        desired=desired_playlist_snapshot(matched_track_ids, current, mode=mode),
    )


def plan_saved_tracks(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
) -> ReconciliationPlan:
    return ReconciliationPlan(
        current=current,
        desired=desired_saved_tracks_snapshot(matched_track_ids, current),
    )
