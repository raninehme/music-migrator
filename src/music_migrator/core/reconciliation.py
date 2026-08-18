import hashlib
from dataclasses import dataclass
from typing import Literal

PlaylistMode = Literal["combine", "replace"]


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    current: tuple[str, ...]
    desired: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return self.current != self.desired

    @property
    def append_from(self) -> int | None:
        if self.current == self.desired[: len(self.current)]:
            return len(self.current)
        return None

    @property
    def desired_fingerprint(self) -> str:
        return fingerprint_track_ids(self.desired)


def fingerprint_track_ids(track_ids: tuple[str, ...] | list[str]) -> str:
    digest = hashlib.sha256()
    for track_id in track_ids:
        digest.update(track_id.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def desired_playlist_tracks(
    matched: list[str],
    existing: list[str],
    *,
    mode: PlaylistMode,
) -> list[str]:
    if mode == "replace":
        return list(matched)
    if mode != "combine":
        raise ValueError(f"unknown migration mode: {mode}")

    matched_ids = set(matched)
    return [*matched, *(track_id for track_id in existing if track_id not in matched_ids)]


def plan_playlist(
    matched: list[str],
    existing: list[str],
    *,
    mode: PlaylistMode,
) -> ReconciliationPlan:
    desired = desired_playlist_tracks(matched, existing, mode=mode)
    return ReconciliationPlan(tuple(existing), tuple(desired))
