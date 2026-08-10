from types import SimpleNamespace
from unittest.mock import Mock

from music_migrator.core.models import Track
from music_migrator.services.tidal.service import TidalDestination


def raw_track(identifier, title, artists, isrc):
    return SimpleNamespace(
        id=identifier,
        name=title,
        artists=[SimpleNamespace(name=artist) for artist in artists],
        album=SimpleNamespace(name="Album"),
        duration=180,
        isrc=isrc,
    )


def test_search_uses_simplified_title_and_primary_artist_then_stops_on_isrc():
    session = Mock()
    session.search.return_value = {
        "tracks": [raw_track("t1", "Yah Yah", ["Eminem"], "USUM72000791")]
    }
    source = Track(
        "s1",
        "Yah Yah (feat. Royce Da 5'9\", Black Thought & Q-Tip)",
        ("Eminem", "Royce Da 5'9\"", "Black Thought", "Q-Tip"),
        "Album",
        180,
        "USUM72000791",
    )
    before_request = Mock()

    results = TidalDestination(session).search_tracks(source, before_request=before_request)

    assert [item.source_id for item in results] == ["t1"]
    session.search.assert_called_once()
    assert session.search.call_args.args[0] == "Yah Yah Eminem"
    before_request.assert_called_once_with()


def test_search_falls_back_and_deduplicates_candidates():
    session = Mock()
    candidate = raw_track("t1", "Song", ["Artist"], "OTHER")
    session.search.return_value = {"tracks": [candidate]}
    source = Track("s1", "Song - From a Film", ("Artist",), "Album", 180, "EXPECTED")

    results = TidalDestination(session).search_tracks(source)

    assert [item.source_id for item in results] == ["t1"]
    assert session.search.call_count == 3


def test_simplifies_soundtrack_and_feature_qualifiers():
    simplify = TidalDestination._simplify_title
    assert simplify('Lose Yourself - From "8 Mile" Soundtrack') == "Lose Yourself"
    assert simplify("Favorite Bitch (feat. Ty Dolla $ign)") == "Favorite Bitch"
    assert simplify("Sunflower - Spider-Man: Into the Spider-Verse") == "Sunflower"
