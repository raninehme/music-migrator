import pytest

from music_migrator.config import MigrationConfig, RequestSettings, render_profile_config
from music_migrator.services.spotify.config import SpotifyConfig


def test_loads_new_service_configuration():
    config = MigrationConfig.from_mapping(
        {
            "services": {
                "spotify": {
                    "client_id": "client",
                    "client_secret": "secret",
                }
            }
        }
    )

    assert config.service("spotify") == {
        "client_id": "client",
        "client_secret": "secret",
    }
    assert config.include_saved_tracks is True


def test_loads_existing_spotify_configuration():
    config = MigrationConfig.from_mapping(
        {"spotify": {"client_id": "client", "client_secret": "secret"}}
    )

    assert config.service("spotify") == {
        "client_id": "client",
        "client_secret": "secret",
    }


def test_allows_profiles_without_spotify():
    config = MigrationConfig.from_mapping({"services": {"tidal": {}}})

    assert config.service("spotify") is None
    assert config.service("tidal") == {}


@pytest.mark.parametrize("missing_key", ["client_id", "client_secret"])
def test_spotify_rejects_missing_credentials(missing_key):
    spotify = {"client_id": "client", "client_secret": "secret"}
    spotify.pop(missing_key)

    with pytest.raises(ValueError, match="Missing Spotify setting"):
        SpotifyConfig.from_mapping(spotify)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"include_saved_tracks": "false"}, "include_saved_tracks"),
        ({"include_saved_tracks": 0}, "include_saved_tracks"),
        ({"max_concurrency": True, "rate_limit": 1}, "max_concurrency"),
        ({"max_concurrency": "10", "rate_limit": 1}, "max_concurrency"),
        ({"max_concurrency": 1, "rate_limit": 1.5}, "rate_limit"),
        ({"max_concurrency": 1}, "configured together"),
        (
            {"services": {"tidal": {"requests": {"max_concurrency": 2}}}},
            "rate_limit",
        ),
    ],
)
def test_rejects_invalid_configuration(raw, message):
    with pytest.raises(ValueError, match=message):
        MigrationConfig.from_mapping(raw)


def test_spotify_rejects_quoted_boolean():
    raw = {
        "client_id": "client",
        "client_secret": "secret",
        "open_browser": "false",
    }

    with pytest.raises(ValueError, match="open_browser"):
        SpotifyConfig.from_mapping(raw)


def test_service_request_override_takes_precedence():
    config = MigrationConfig.from_mapping(
        {
            "services": {
                "tidal": {
                    "requests": {
                        "max_concurrency": 4,
                        "rate_limit": 5,
                    }
                }
            },
            "max_concurrency": 9,
            "rate_limit": 9,
        }
    )

    assert config.requests_for("tidal", RequestSettings(8, 8)) == RequestSettings(4, 5)
    assert config.requests_for("spotify", RequestSettings(3, 3)) == RequestSettings(9, 9)


def test_service_defaults_apply_without_overrides():
    config = MigrationConfig.from_mapping({})

    assert config.requests_for("spotify", RequestSettings(3, 3)) == RequestSettings(3, 3)


def test_profile_renderer_only_assembles_provider_sections():
    rendered = render_profile_config(["  spotify:\n    client_id: client\n", "  # tidal:\n"])

    assert rendered == (
        "services:\n  spotify:\n    client_id: client\n  # tidal:\n\ninclude_saved_tracks: true\n"
    )
