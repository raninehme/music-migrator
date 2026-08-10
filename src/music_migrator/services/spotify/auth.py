from pathlib import Path

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from music_migrator.config import SpotifyConfig

SPOTIFY_SOURCE_SCOPES = "playlist-read-private playlist-read-collaborative user-library-read"


def create_spotify_client(
    config: SpotifyConfig,
    session_path: Path,
    scopes: str = SPOTIFY_SOURCE_SCOPES,
) -> spotipy.Spotify:
    """Create an authenticated Spotify client with a profile-scoped token cache."""
    cache = CacheFileHandler(cache_path=str(session_path))
    oauth = SpotifyOAuth(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri=config.redirect_uri,
        scope=scopes,
        open_browser=config.open_browser,
        cache_handler=cache,
        requests_timeout=10,
    )
    return spotipy.Spotify(auth_manager=oauth, requests_timeout=10)
