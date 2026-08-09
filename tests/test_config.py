import pytest

from music_migrator.config import MigrationConfig


def test_loads_valid_configuration():
    config = MigrationConfig.from_mapping(
        {
            "spotify": {
                "client_id": "client",
                "client_secret": "secret",
            },
        }
    )

    assert config.spotify.client_id == "client"
    assert config.spotify.redirect_uri == "http://127.0.0.1:8888/callback"
    assert config.include_saved_tracks is True


@pytest.mark.parametrize("missing_key", ["client_id", "client_secret"])
def test_rejects_missing_spotify_credentials(missing_key):
    spotify = {"client_id": "client", "client_secret": "secret"}
    spotify.pop(missing_key)

    with pytest.raises(ValueError, match="Missing Spotify setting"):
        MigrationConfig.from_mapping({"spotify": spotify})
