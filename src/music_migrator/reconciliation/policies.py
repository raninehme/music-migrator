"""Translate migration policy into provider-neutral desired collection state."""

from typing import Literal

from music_migrator.domain.collections import CollectionSnapshot

PlaylistMode = Literal["combine", "replace"]


def desired_playlist_snapshot(
    matched_track_ids: list[str],
    current: CollectionSnapshot,
    *,
    mode: PlaylistMode,
) -> CollectionSnapshot:
    """Return the desired ordered playlist state for the selected migration mode."""
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
    """Return the desired unordered saved-track state as a union of both sides."""
    if current.kind != "saved_tracks":
        raise ValueError("saved-track reconciliation requires a saved-tracks snapshot")

    desired = set(current.track_ids)
    desired.update(matched_track_ids)
    return CollectionSnapshot.saved_tracks(current.key, current.name, desired)
