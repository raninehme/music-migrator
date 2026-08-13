import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from music_migrator.config import MigrationConfig
from music_migrator.core.migration import Migrator
from music_migrator.core.models import Track, TrackMatch


def test_concurrent_matching_preserves_source_order():
    first = Track("s1", "First", ("Artist",), None, 1)
    second = Track("s2", "Second", ("Artist",), None, 0)
    progress = Mock()
    migrator = Migrator(Mock(), Mock(), Mock(), dry_run=True, max_concurrency=2, progress=progress)

    def match(track):
        time.sleep(track.duration_seconds * 0.02)
        return TrackMatch(track, f"tidal-{track.source_id}", 1.0, "test")

    migrator._match_track = match
    results = migrator._match_tracks(iter([first, second]), "Mix")

    assert results.matched == ["tidal-s1", "tidal-s2"]
    assert results.unmatched == []
    assert results.source_ids == ["s1", "s2"]
    progress.assert_any_call("Matching Mix", 2, 2)


def test_configures_concurrency_and_rate_limit():
    config = MigrationConfig.from_mapping(
        {
            "spotify": {"client_id": "client", "client_secret": "secret"},
            "max_concurrency": 4,
            "rate_limit": 7,
        }
    )

    assert config.max_concurrency == 4
    assert config.rate_limit == 7


@pytest.mark.parametrize("setting", ["max_concurrency", "rate_limit"])
def test_rejects_non_positive_performance_settings(setting):
    raw = {
        "spotify": {"client_id": "client", "client_secret": "secret"},
        setting: 0,
    }
    with pytest.raises(ValueError, match=f"{setting} must be at least 1"):
        MigrationConfig.from_mapping(raw)


def test_each_search_request_uses_one_rate_limit_slot():
    source = Track("source", "Song", ("Artist",), "Album", 180, "ISRC")
    candidate = Track("target", "Song", ("Artist",), "Album", 180, "ISRC")
    destination = Mock()

    def search(_track, *, before_request):
        before_request()
        return [candidate]

    destination.search_tracks.side_effect = search
    cache = Mock()
    cache.get.return_value = None
    migrator = Migrator(Mock(), destination, cache, dry_run=True)
    migrator._rate_limiter.wait = Mock()

    result = migrator._match_track(source)

    assert result.destination_id == "target"
    migrator._rate_limiter.wait.assert_called_once_with()


def test_matching_keeps_active_and_buffered_results_within_one_worker_window():
    first_can_finish = Event()
    later_track_finished = Event()
    yielded = 0
    tracks = [Track(f"s{index}", f"Track {index}", ("Artist",), None, 0) for index in range(20)]
    migrator = Migrator(Mock(), Mock(), Mock(), dry_run=True, max_concurrency=3)

    def source_tracks():
        nonlocal yielded
        for track in tracks:
            yielded += 1
            yield track

    def match(track):
        if track.source_id == "s0":
            first_can_finish.wait(timeout=2)
        else:
            later_track_finished.set()
        return TrackMatch(track, f"target-{track.source_id}", 1.0, "test")

    migrator._match_track = match
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(migrator._match_tracks, source_tracks(), "Large")
        assert later_track_finished.wait(timeout=1)
        time.sleep(0.02)
        assert yielded == 3
        first_can_finish.set()
        results = future.result(timeout=2)

    assert results.count == 20


def test_matching_preserves_order_across_multiple_worker_windows():
    tracks = [
        Track(f"s{index}", f"Track {index}", ("Artist",), None, 9 - index) for index in range(10)
    ]
    migrator = Migrator(Mock(), Mock(), Mock(), dry_run=True, max_concurrency=3)

    def match(track):
        time.sleep(track.duration_seconds * 0.001)
        destination_id = None if track.source_id in {"s3", "s8"} else f"target-{track.source_id}"
        return TrackMatch(track, destination_id, 1.0, "test")

    migrator._match_track = match

    results = migrator._match_tracks(iter(tracks), "Large")

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
    assert [track.source_id for track in results.unmatched] == ["s3", "s8"]
    assert results.source_ids == [track.source_id for track in tracks]
