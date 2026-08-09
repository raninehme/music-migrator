import time
from unittest.mock import Mock

import pytest

from music_migrator.config import MigrationConfig
from music_migrator.migration import Migrator
from music_migrator.models import Track, TrackMatch


def test_concurrent_matching_preserves_source_order():
    first = Track("s1", "First", ("Artist",), None, 1)
    second = Track("s2", "Second", ("Artist",), None, 0)
    progress = Mock()
    migrator = Migrator(Mock(), Mock(), Mock(), dry_run=True, max_concurrency=2, progress=progress)

    def match(track):
        time.sleep(track.duration_seconds * 0.02)
        return TrackMatch(track, f"tidal-{track.source_id}", 1.0, "test")

    migrator._match_track = match
    matched, unmatched = migrator._match_tracks([first, second], "Mix")

    assert matched == ["tidal-s1", "tidal-s2"]
    assert unmatched == []
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
