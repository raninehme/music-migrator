import re
import unicodedata
from difflib import SequenceMatcher

from music_migrator.core.models import Track, TrackMatch


def normalize(value: str | None) -> str:
    if not value:
        return ""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+-\s+from\b.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\s*[\[(][^\])]*\b(?:feat(?:uring)?\.?|with)\b[^\])]*[\])]",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize(value)


def score(source: Track, candidate: Track) -> TrackMatch:
    if source.isrc and candidate.isrc and source.isrc.casefold() == candidate.isrc.casefold():
        return TrackMatch(source, candidate.source_id, 1.0, "ISRC")

    title = max(
        SequenceMatcher(None, left, right).ratio()
        for left in _title_variants(source.title)
        for right in _title_variants(candidate.title)
    )
    artists = max(
        SequenceMatcher(None, left, right).ratio()
        for left in _artist_variants(source.artists)
        for right in _artist_variants(candidate.artists)
    )
    album = SequenceMatcher(None, normalize(source.album), normalize(candidate.album)).ratio()
    duration = _duration_score(source.duration_seconds, candidate.duration_seconds)
    confidence = (title * 0.45) + (artists * 0.35) + (duration * 0.15) + (album * 0.05)
    return TrackMatch(source, candidate.source_id, round(confidence, 4), "metadata")


def best_match(source: Track, candidates: list[Track], threshold: float = 0.78) -> TrackMatch:
    if not candidates:
        return TrackMatch(source, None, 0.0, "no candidates")
    result = max(
        (score(source, candidate) for candidate in candidates),
        key=lambda item: item.confidence,
    )
    if result.confidence < threshold:
        return TrackMatch(source, None, result.confidence, "below threshold")
    return result


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
        return 0.5
    difference = abs(left - right)
    return max(0.0, 1.0 - (difference / 20.0))
