"""Compatibility imports for matching APIs moved to :mod:`music_migrator.matching`."""

from music_migrator.matching.normalization import (
    normalize,
    normalize_title,
    strip_title_qualifiers,
    track_fingerprint,
)
from music_migrator.matching.scoring import (
    ALBUM_WEIGHT,
    ARTIST_WEIGHT,
    DURATION_SCORE_WINDOW_SECONDS,
    DURATION_WEIGHT,
    MATCH_THRESHOLD,
    MATCH_VERSION,
    TITLE_VARIANT_DURATION_TOLERANCE_SECONDS,
    TITLE_WEIGHT,
    UNKNOWN_DURATION_SCORE,
    best_match,
    score,
)

__all__ = [
    "ALBUM_WEIGHT",
    "ARTIST_WEIGHT",
    "DURATION_SCORE_WINDOW_SECONDS",
    "DURATION_WEIGHT",
    "MATCH_THRESHOLD",
    "MATCH_VERSION",
    "TITLE_VARIANT_DURATION_TOLERANCE_SECONDS",
    "TITLE_WEIGHT",
    "UNKNOWN_DURATION_SCORE",
    "best_match",
    "normalize",
    "normalize_title",
    "score",
    "strip_title_qualifiers",
    "track_fingerprint",
]
