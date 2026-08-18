"""Expose the provider-neutral matching subsystem."""

from music_migrator.matching.cache import MatchCache
from music_migrator.matching.engine import MatchEngine, MatchResults
from music_migrator.matching.models import TrackMatch
from music_migrator.matching.normalization import (
    normalize,
    normalize_title,
    strip_title_qualifiers,
    track_fingerprint,
)
from music_migrator.matching.scoring import MATCH_VERSION, best_match, score

__all__ = [
    "MATCH_VERSION",
    "MatchCache",
    "MatchEngine",
    "MatchResults",
    "TrackMatch",
    "best_match",
    "normalize",
    "normalize_title",
    "score",
    "strip_title_qualifiers",
    "track_fingerprint",
]
