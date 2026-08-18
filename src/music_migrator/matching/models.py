"""Define matching-specific result models without leaking them into the domain layer."""

from dataclasses import dataclass

from music_migrator.domain.models import Track


@dataclass(frozen=True, slots=True)
class TrackMatch:
    source: Track
    destination_id: str | None
    confidence: float
    reason: str
