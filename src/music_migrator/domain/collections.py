"""Define provider-neutral collection snapshots used during reconciliation."""

from dataclasses import dataclass
from typing import Literal

CollectionKind = Literal["playlist", "saved_tracks"]


@dataclass(frozen=True, slots=True)
class CollectionSnapshot:
    """Represent one collection's track state without provider-specific details."""

    kind: CollectionKind
    key: str
    name: str
    track_ids: tuple[str, ...]
    ordered: bool

    @classmethod
    def playlist(
        cls,
        key: str,
        name: str,
        track_ids: list[str] | tuple[str, ...],
    ) -> "CollectionSnapshot":
        return cls("playlist", key, name, tuple(track_ids), True)

    @classmethod
    def saved_tracks(
        cls,
        key: str,
        name: str,
        track_ids: set[str] | list[str] | tuple[str, ...],
    ) -> "CollectionSnapshot":
        return cls("saved_tracks", key, name, tuple(sorted(track_ids)), False)
