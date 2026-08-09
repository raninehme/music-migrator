from music_migrator.matching import best_match, normalize_title, score
from music_migrator.models import Track


def test_normalizes_soundtrack_and_feature_qualifiers():
    assert normalize_title('Rabbit Run - From "8 Mile" Soundtrack') == "rabbit run"
    assert normalize_title("Favorite Bitch (feat. Ty Dolla $ign)") == "favorite bitch"


def test_matches_same_track_with_service_specific_title_and_isrc():
    source = Track(
        "spotify",
        'Rabbit Run - From "8 Mile" Soundtrack',
        ("Eminem",),
        "8 Mile (Music From And Inspired By The Motion Picture)",
        190,
        "USIR10211651",
    )
    candidate = Track(
        "tidal",
        "Rabbit Run",
        ("Eminem",),
        "8 Mile (Music From And Inspired By The Motion Picture (Expanded Edition))",
        190,
        "USIR10211627",
    )

    result = best_match(source, [candidate])

    assert result.destination_id == "tidal"
    assert result.confidence > 0.9


def test_rejects_same_title_from_different_artist():
    source = Track("spotify", "Rabbit Run", ("Eminem",), None, 190)
    candidate = Track("tidal", "Rabbit Run", ("Rainbow Kitten Surprise",), None, 228)
    assert score(source, candidate).confidence < 0.78
