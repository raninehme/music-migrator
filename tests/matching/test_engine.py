"""Test matching orchestration independently from migration reconciliation and writes."""

from music_migrator.core.models import Track
from music_migrator.matching import MatchCache, MatchEngine
from music_migrator.matching.normalization import track_fingerprint


def track(track_id: str, title: str = "Song") -> Track:
    return Track(track_id, title, ("Artist",), "Album", 180, f"ISRC-{track_id}")


def test_engine_reuses_cached_match_without_search(mocker, tmp_path):
    source = track("source")
    destination = mocker.Mock()

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        cache.put(source.source_id, "cached", track_fingerprint(source))
        results = MatchEngine(destination, cache).match_tracks([source], "Mix")

    assert results.matched == ["cached"]
    assert results.unmatched == []
    destination.search_tracks.assert_not_called()


def test_engine_preserves_source_order_across_concurrent_matches(mocker, tmp_path):
    sources = [track("one"), track("two"), track("three")]
    destination = mocker.Mock()
    candidates = {
        item.source_id: Track(
            f"target-{item.source_id}",
            item.title,
            item.artists,
            item.album,
            item.duration_seconds,
            item.isrc,
        )
        for item in sources
    }
    destination.search_tracks.side_effect = lambda item, **_: [candidates[item.source_id]]

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        results = MatchEngine(destination, cache, max_concurrency=3).match_tracks(sources, "Mix")

    assert results.source_ids == ["one", "two", "three"]
    assert results.matched == ["target-one", "target-two", "target-three"]


def test_engine_reports_unmatched_tracks(mocker, tmp_path):
    source = track("source")
    destination = mocker.Mock()
    destination.search_tracks.return_value = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        results = MatchEngine(destination, cache).match_tracks([source], "Mix")

    assert results.matched == []
    assert results.unmatched == [source]
    assert results.count == 1


def test_engine_reports_matching_progress(mocker, tmp_path):
    source = track("source")
    destination = mocker.Mock()
    destination.search_tracks.return_value = []
    progress = mocker.Mock()

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        MatchEngine(destination, cache, progress=progress).match_tracks([source], "Mix")

    assert progress.call_args_list == [
        mocker.call("Matching Mix", 0, None),
        mocker.call("Matching Mix", 1, None),
        mocker.call("Matching Mix", 1, 1),
    ]
