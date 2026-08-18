from music_migrator.domain.models import Track
from music_migrator.matching import best_match, normalize, score, track_fingerprint
from music_migrator.matching.scoring import (
    ALBUM_WEIGHT,
    ARTIST_WEIGHT,
    DURATION_WEIGHT,
    MATCH_THRESHOLD,
    TITLE_WEIGHT,
)


def track(identifier="1", title="Song", artists=("Artist",), duration=180, isrc=None):
    return Track(identifier, title, artists, "Album", duration, isrc)


def test_normalize_handles_accents_and_punctuation():
    assert normalize("Beyoncé: Halo!") == "beyonce halo"


def test_normalize_preserves_non_latin_scripts():
    assert normalize("فيروز") == "فيروز"
    assert normalize("宇多田ヒカル") == "宇多田ヒカル"
    assert normalize("아이유") == "아이유"


def test_isrc_is_an_exact_match():
    result = score(track(isrc="ABC"), track("2", title="Other", isrc="abc"))
    assert result.destination_id == "2"
    assert result.confidence == 1.0


def test_rejects_weak_candidate():
    result = best_match(track(), [track("2", title="Completely Different", artists=("Else",))])
    assert result.destination_id is None


def test_matching_weights_remain_normalized():
    assert TITLE_WEIGHT + ARTIST_WEIGHT + DURATION_WEIGHT + ALBUM_WEIGHT == 1.0
    assert MATCH_THRESHOLD == 0.78


def test_track_fingerprint_changes_with_match_relevant_metadata():
    original = track(title="Song", artists=("Artist",), duration=180, isrc="ABC")
    changed = track(title="Different", artists=("Artist",), duration=180, isrc="ABC")

    assert track_fingerprint(original) != track_fingerprint(changed)


def test_track_fingerprint_ignores_normalization_only_title_changes():
    accented = track(title="Beyoncé: Halo!")
    normalized = track(title="Beyonce Halo")

    assert track_fingerprint(accented) == track_fingerprint(normalized)
