"""Score provider candidates and select the best destination track match."""

import re
from difflib import SequenceMatcher

from music_migrator.domain.models import Track
from music_migrator.matching.models import TrackMatch
from music_migrator.matching.normalization import normalize, normalize_title

MATCH_VERSION = 3
MATCH_THRESHOLD = 0.78
TITLE_WEIGHT = 0.45
ARTIST_WEIGHT = 0.35
DURATION_WEIGHT = 0.15
ALBUM_WEIGHT = 0.05
TITLE_VARIANT_DURATION_TOLERANCE_SECONDS = 10
DURATION_SCORE_WINDOW_SECONDS = 20
UNKNOWN_DURATION_SCORE = 0.5


def score(source: Track, candidate: Track) -> TrackMatch:
    if source.isrc and candidate.isrc and source.isrc.casefold() == candidate.isrc.casefold():
        return TrackMatch(source, candidate.source_id, 1.0, "ISRC")

    title = _title_score(source, candidate)
    artists = max(
        SequenceMatcher(None, left, right).ratio()
        for left in _artist_variants(source.artists)
        for right in _artist_variants(candidate.artists)
    )
    album = SequenceMatcher(None, normalize(source.album), normalize(candidate.album)).ratio()
    duration = _duration_score(source.duration_seconds, candidate.duration_seconds)
    confidence = (
        (title * TITLE_WEIGHT)
        + (artists * ARTIST_WEIGHT)
        + (duration * DURATION_WEIGHT)
        + (album * ALBUM_WEIGHT)
    )
    return TrackMatch(source, candidate.source_id, round(confidence, 4), "metadata")


def best_match(
    source: Track,
    candidates: list[Track],
    threshold: float = MATCH_THRESHOLD,
) -> TrackMatch:
    if not candidates:
        return TrackMatch(source, None, 0.0, "no candidates")
    result = max(
        (score(source, candidate) for candidate in candidates),
        key=lambda item: item.confidence,
    )
    if result.confidence < threshold:
        return TrackMatch(source, None, result.confidence, "below threshold")
    return result


def _title_score(source: Track, candidate: Track) -> float:
    canonical = SequenceMatcher(
        None, normalize_title(source.title), normalize_title(candidate.title)
    ).ratio()
    variant = max(
        SequenceMatcher(None, left, right).ratio()
        for left in _title_variants(source.title)
        for right in _title_variants(candidate.title)
    )
    if variant <= canonical:
        return canonical
    if _durations_close(source.duration_seconds, candidate.duration_seconds):
        return variant
    return canonical


def _durations_close(
    left: float | None,
    right: float | None,
    tolerance: float = TITLE_VARIANT_DURATION_TOLERANCE_SECONDS,
) -> bool:
    return left is not None and right is not None and abs(left - right) <= tolerance


def _title_variants(value: str) -> set[str]:
    variants = {normalize_title(value)}
    without_suffix = re.sub(r"\s+(?:-|/)\s+.*$", "", value)
    variants.add(normalize_title(without_suffix))
    variants.discard("")
    return variants or {""}


def _artist_variants(values: tuple[str, ...]) -> set[str]:
    full_credit = " ".join(values)
    primary = values[0] if values else ""
    variants = {normalize(full_credit), normalize(primary)}
    for value in (full_credit, primary):
        without_band = re.sub(r"\s+(?:and|&)\s+the\s+.*$", "", value, flags=re.IGNORECASE)
        variants.add(normalize(without_band))
    variants.discard("")
    return variants or {""}


def _duration_score(left: float | None, right: float | None) -> float:
    if left is None or right is None:
        return UNKNOWN_DURATION_SCORE
    difference = abs(left - right)
    return max(0.0, 1.0 - (difference / DURATION_SCORE_WINDOW_SECONDS))
