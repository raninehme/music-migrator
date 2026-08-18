"""Test matching orchestration independently from migration reconciliation and writes."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from music_migrator.domain.models import Track
from music_migrator.matching import MatchCache, MatchEngine, TrackMatch
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


def test_concurrent_matching_preserves_source_order(mocker):
    first = Track("s1", "First", ("Artist",), None, 1)
    second = Track("s2", "Second", ("Artist",), None, 0)
    progress = mocker.Mock()
    engine = MatchEngine(mocker.Mock(), mocker.Mock(), max_concurrency=2, progress=progress)

    def match(item):
        time.sleep(item.duration_seconds * 0.02)
        return TrackMatch(item, f"tidal-{item.source_id}", 1.0, "test")

    engine._match_track = match
    results = engine.match_tracks(iter([first, second]), "Mix")

    assert results.matched == ["tidal-s1", "tidal-s2"]
    assert results.unmatched == []
    assert results.source_ids == ["s1", "s2"]
    progress.assert_any_call("Matching Mix", 2, 2)


def test_each_search_request_uses_one_rate_limit_slot(mocker):
    source = Track("source", "Song", ("Artist",), "Album", 180, "ISRC")
    candidate = Track("target", "Song", ("Artist",), "Album", 180, "ISRC")
    destination = mocker.Mock()

    def search(_track, *, before_request):
        before_request()
        return [candidate]

    destination.search_tracks.side_effect = search
    cache = mocker.Mock()
    cache.get.return_value = None
    engine = MatchEngine(destination, cache)
    engine._rate_limiter.wait = mocker.Mock()

    result = engine._match_track(source)

    assert result.destination_id == "target"
    engine._rate_limiter.wait.assert_called_once_with()


def test_matching_keeps_active_and_buffered_results_within_one_worker_window(mocker):
    first_can_finish = Event()
    later_track_finished = Event()
    yielded = 0
    tracks = [Track(f"s{index}", f"Track {index}", ("Artist",), None, 0) for index in range(20)]
    engine = MatchEngine(mocker.Mock(), mocker.Mock(), max_concurrency=3)

    def source_tracks():
        nonlocal yielded
        for item in tracks:
            yielded += 1
            yield item

    def match(item):
        if item.source_id == "s0":
            first_can_finish.wait(timeout=2)
        else:
            later_track_finished.set()
        return TrackMatch(item, f"target-{item.source_id}", 1.0, "test")

    engine._match_track = match
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(engine.match_tracks, source_tracks(), "Large")
        assert later_track_finished.wait(timeout=1)
        time.sleep(0.02)
        assert yielded == 3
        first_can_finish.set()
        results = future.result(timeout=2)

    assert results.count == 20


def test_matching_preserves_order_across_multiple_worker_windows(mocker):
    tracks = [
        Track(f"s{index}", f"Track {index}", ("Artist",), None, 9 - index) for index in range(10)
    ]
    engine = MatchEngine(mocker.Mock(), mocker.Mock(), max_concurrency=3)

    def match(item):
        time.sleep(item.duration_seconds * 0.001)
        destination_id = None if item.source_id in {"s3", "s8"} else f"target-{item.source_id}"
        return TrackMatch(item, destination_id, 1.0, "test")

    engine._match_track = match
    results = engine.match_tracks(iter(tracks), "Large")

    assert results.matched == [
        "target-s0",
        "target-s1",
        "target-s2",
        "target-s4",
        "target-s5",
        "target-s6",
        "target-s7",
        "target-s9",
    ]
    assert [item.source_id for item in results.unmatched] == ["s3", "s8"]
    assert results.source_ids == [item.source_id for item in tracks]
