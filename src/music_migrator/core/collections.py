import hashlib
from dataclasses import dataclass
from typing import Literal

CollectionKind = Literal["playlist", "saved_tracks"]


@dataclass(frozen=True, slots=True)
class CollectionSnapshot:
    """Provider-neutral view of one collection at a point in time."""

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

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.kind.encode("utf-8"))
        digest.update(b"\0")
        digest.update(b"ordered" if self.ordered else b"unordered")
        digest.update(b"\0")
        for track_id in self.track_ids:
            digest.update(track_id.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()
