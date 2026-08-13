import sqlite3

from music_migrator.core.cache import MatchCache


def test_cache_round_trip_and_update(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        assert cache.get("spotify", "fingerprint") is None
        cache.put("spotify", "tidal-1", "fingerprint")
        cache.put("spotify", "tidal-2", "fingerprint")
        assert cache.get("spotify", "fingerprint") == "tidal-2"


def test_cache_ignores_matches_from_an_old_matcher_version(tmp_path):
    path = tmp_path / "cache.sqlite3"
    with MatchCache(path, match_version=1) as cache:
        cache.put("spotify", "tidal", "fingerprint")

    with MatchCache(path, match_version=2) as cache:
        assert cache.get("spotify", "fingerprint") is None


def test_cache_ignores_match_when_source_metadata_changes(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        cache.put("spotify", "tidal", "original")

        assert cache.get("spotify", "changed") is None
        assert cache.get("spotify", "original") == "tidal"


def test_cache_migrates_the_original_schema(tmp_path):
    path = tmp_path / "cache.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE matches (source_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO matches VALUES ('spotify', 'tidal')")

    with MatchCache(path, match_version=2) as cache:
        assert cache.get("spotify", "fingerprint") is None
        cache.put("spotify", "new-tidal", "fingerprint")
        assert cache.get("spotify", "fingerprint") == "new-tidal"


def test_cache_migrates_versioned_schema_without_fingerprints(tmp_path):
    path = tmp_path / "cache.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE matches ("
            "source_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL, "
            "match_version INTEGER NOT NULL DEFAULT 1)"
        )
        connection.execute("INSERT INTO matches VALUES ('spotify', 'tidal', 2)")

    with MatchCache(path, match_version=2) as cache:
        assert cache.get("spotify", "fingerprint") is None
        cache.put("spotify", "new-tidal", "fingerprint")
        assert cache.get("spotify", "fingerprint") == "new-tidal"


def test_cache_can_be_cleared(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        cache.put("spotify", "tidal", "fingerprint")
        cache.clear()

        assert cache.get("spotify", "fingerprint") is None


def test_cache_can_discard_selected_matches(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        cache.put("keep", "tidal-1", "keep-fingerprint")
        cache.put("discard", "tidal-2", "discard-fingerprint")

        cache.discard(["discard"])

        assert cache.get("keep", "keep-fingerprint") == "tidal-1"
        assert cache.get("discard", "discard-fingerprint") is None
