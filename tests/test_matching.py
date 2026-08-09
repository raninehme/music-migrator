from music_migrator.matching import best_match, normalize, score
from music_migrator.models import Track


def track(identifier="1", title="Song", artists=("Artist",), duration=180, isrc=None):
    return Track(identifier, title, artists, "Album", duration, isrc)


def test_normalize_handles_accents_and_punctuation():
    assert normalize("Beyoncé: Halo!") == "beyonce halo"


def test_isrc_is_an_exact_match():
    result = score(track(isrc="ABC"), track("2", title="Other", isrc="abc"))
    assert result.destination_id == "2"
    assert result.confidence == 1.0


def test_rejects_weak_candidate():
    result = best_match(track(), [track("2", title="Completely Different", artists=("Else",))])
    assert result.destination_id is None
