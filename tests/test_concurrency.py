"""Test configurable matching concurrency and rate-limit settings."""

import pytest

from music_migrator.config import MigrationConfig, RequestSettings


def test_configures_service_concurrency_and_rate_limit():
    config = MigrationConfig.from_mapping(
        {
            "services": {
                "spotify": {
                    "client_id": "client",
                    "client_secret": "secret",
                    "requests": {
                        "max_concurrency": 4,
                        "rate_limit": 7,
                    },
                }
            }
        }
    )

    assert config.requests_for("spotify", RequestSettings(3, 3)) == RequestSettings(4, 7)


@pytest.mark.parametrize("setting", ["max_concurrency", "rate_limit"])
def test_rejects_non_positive_performance_settings(setting):
    requests = {"max_concurrency": 4, "rate_limit": 7}
    requests[setting] = 0
    raw = {
        "services": {
            "spotify": {
                "client_id": "client",
                "client_secret": "secret",
                "requests": requests,
            }
        }
    }

    with pytest.raises(ValueError, match=f"{setting} must be at least 1"):
        MigrationConfig.from_mapping(raw)
