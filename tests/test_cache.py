from music_migrator.core.cache import MatchCache


def test_cache_round_trip_and_update(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        assert cache.get("spotify") is None
        cache.put("spotify", "tidal-1")
        cache.put("spotify", "tidal-2")
        assert cache.get("spotify") == "tidal-2"


def test_cache_ignores_matches_from_an_old_matcher_version(tmp_path):
    path = tmp_path / "cache.sqlite3"
    with MatchCache(path, match_version=1) as cache:
        cache.put("spotify", "tidal")

    with MatchCache(path, match_version=2) as cache:
        assert cache.get("spotify") is None


def test_cache_migrates_the_original_schema(tmp_path):
    import sqlite3

    path = tmp_path / "cache.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE matches (source_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO matches VALUES ('spotify', 'tidal')")

    with MatchCache(path, match_version=2) as cache:
        assert cache.get("spotify") is None
        cache.put("spotify", "new-tidal")
        assert cache.get("spotify") == "new-tidal"


def test_cache_can_be_cleared(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        cache.put("spotify", "tidal")
        cache.clear()

        assert cache.get("spotify") is None
