from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Track:
    source_id: str
    title: str
    artists: tuple[str, ...]
    album: str | None
    duration_seconds: float | None
    isrc: str | None = None


@dataclass(frozen=True, slots=True)
class Playlist:
    source_id: str
    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class TrackMatch:
    source: Track
    destination_id: str | None
    confidence: float
    reason: str
