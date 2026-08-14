from types import SimpleNamespace

from music_migrator.services.spotify.auth import (
    SPOTIFY_SOURCE_SCOPES,
    create_spotify_client,
)


def test_create_spotify_client_uses_profile_cache_and_source_scopes(mocker, tmp_path):
    cache_type = mocker.patch("music_migrator.services.spotify.auth.CacheFileHandler")
    oauth_type = mocker.patch("music_migrator.services.spotify.auth.SpotifyOAuth")
    client_type = mocker.patch("music_migrator.services.spotify.auth.spotipy.Spotify")
    config = SimpleNamespace(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://127.0.0.1:8888/callback",
        open_browser=True,
    )
    session_path = tmp_path / "spotify-session.json"

    client = create_spotify_client(config, session_path)

    cache_type.assert_called_once_with(cache_path=str(session_path))
    oauth_type.assert_called_once_with(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://127.0.0.1:8888/callback",
        scope=SPOTIFY_SOURCE_SCOPES,
        open_browser=True,
        cache_handler=cache_type.return_value,
        requests_timeout=10,
    )
    client_type.assert_called_once_with(
        auth_manager=oauth_type.return_value,
        requests_timeout=10,
        retries=0,
        status_retries=0,
    )
    assert client is client_type.return_value
