from music_migrator.core.matching import best_match, normalize_title, score
from music_migrator.core.models import Track


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


def test_matches_release_suffix_and_primary_artist_credit():
    source = Track(
        "spotify",
        "Sunflower - Spider-Man: Into the Spider-Verse",
        ("Post Malone", "Swae Lee"),
        "Spider-Man: Into the Spider-Verse",
        158,
    )
    candidate = Track(
        "tidal",
        "Sunflower",
        ("Post Malone",),
        "Hollywood's Bleeding",
        158,
    )

    result = best_match(source, [candidate])

    assert result.destination_id == "tidal"
    assert result.confidence > 0.9


def test_matches_spaced_slash_title_variant():
    source = Track(
        "spotify",
        "Hard Times",
        ("The Human League",),
        "Pride – Music From And Inspired By The Motion Picture",
        294,
    )
    candidate = Track(
        "tidal",
        "Hard Times / Love Action",
        ("The Human League",),
        "Fascination!",
        297,
    )

    assert best_match(source, [candidate]).destination_id == "tidal"


def test_matches_solo_and_band_artist_credits():
    source = Track(
        "spotify",
        "Are You Ready To Be Heartbroken?",
        ("Lloyd Cole and the Commotions",),
        "Pride – Music From And Inspired By The Motion Picture",
        185,
    )
    candidate = Track(
        "tidal",
        "Are You Ready To Be Heartbroken?",
        ("Lloyd Cole",),
        "Rattlesnakes",
        187,
    )

    assert best_match(source, [candidate]).destination_id == "tidal"
