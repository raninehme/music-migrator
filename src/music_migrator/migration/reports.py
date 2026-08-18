"""Define provider-neutral reports produced by migration jobs."""

from dataclasses import dataclass, field

from music_migrator.domain.models import Track


@dataclass(slots=True)
class CollectionReport:
    name: str
    source_tracks: int
    matched_tracks: int
    unmatched: list[Track] = field(default_factory=list)
    changed: bool = False
    saved: bool = False


@dataclass(slots=True)
class MigrationReport:
    collections: list[CollectionReport] = field(default_factory=list)

    @property
    def matched(self) -> int:
        return sum(item.matched_tracks for item in self.collections)

    @property
    def unmatched(self) -> list[Track]:
        return [track for item in self.collections for track in item.unmatched]
