"""Test configurable matching concurrency and rate-limit settings."""

import pytest

from music_migrator.config import MigrationConfig


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
