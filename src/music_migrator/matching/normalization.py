"""Normalize track metadata and fingerprint source state for matching."""

import hashlib
import re
import unicodedata

from music_migrator.domain.models import Track


def normalize(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = unicodedata.normalize("NFC", without_marks)
    return " ".join(re.findall(r"[^\W_]+", normalized.casefold(), flags=re.UNICODE))


def strip_title_qualifiers(value: str) -> str:
    """Remove soundtrack and featured-artist qualifiers while preserving display text."""
    value = re.sub(r"\s+-\s+from\b.*$", "", value, flags=re.IGNORECASE)
    return re.sub(
        r"\s*[\[(][^\])]*\b(?:feat(?:uring)?\.?|with)\b[^\])]*[\])]",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()


def normalize_title(value: str | None) -> str:
    return normalize(strip_title_qualifiers(value)) if value else ""


def track_fingerprint(track: Track) -> str:
    """Return a stable fingerprint of source metadata that influences matching."""
    duration = "" if track.duration_seconds is None else f"{track.duration_seconds:.3f}"
    metadata = (
        normalize_title(track.title),
        "\x1f".join(normalize(artist) for artist in track.artists),
        normalize(track.album),
        duration,
        (track.isrc or "").strip().casefold(),
    )
    return hashlib.sha256("\x00".join(metadata).encode()).hexdigest()
