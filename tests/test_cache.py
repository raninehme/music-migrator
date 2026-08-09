from music_migrator.cache import MatchCache


def test_cache_round_trip_and_update(tmp_path):
    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        assert cache.get("spotify") is None
        cache.put("spotify", "tidal-1")
        cache.put("spotify", "tidal-2")
        assert cache.get("spotify") == "tidal-2"
