from types import SimpleNamespace

from music_migrator.core.cache import MatchCache
from music_migrator.core.migration import Migrator
from music_migrator.services.spotify.service import SpotifyDestination
from music_migrator.services.tidal.service import TidalSource


def test_applies_tidal_playlist_to_spotify(tmp_path, mocker):
    tidal_track = SimpleNamespace(
        id="tidal-track",
        name="Song",
        artists=[SimpleNamespace(name="Artist")],
        album=SimpleNamespace(name="Album"),
        duration=180,
        isrc="TEST123",
    )
    tidal_playlist = SimpleNamespace(
        id="tidal-playlist",
        name="Mix",
        description="Description",
        tracks_paginated=mocker.Mock(return_value=[tidal_track]),
    )
    tidal_session = mocker.Mock()
    tidal_session.user.playlists.return_value = [tidal_playlist]
    tidal_session.playlist.return_value = tidal_playlist

    spotify_track = {
        "id": "spotify-track",
        "name": "Song",
        "type": "track",
        "artists": [{"name": "Artist"}],
        "album": {"name": "Album"},
        "duration_ms": 180000,
        "external_ids": {"isrc": "TEST123"},
    }
    spotify_client = mocker.Mock()
    spotify_client.current_user.return_value = {"id": "me"}
    spotify_client.current_user_playlists.return_value = {"items": [], "next": None}
    spotify_client.search.return_value = {"tracks": {"items": [spotify_track]}}
    spotify_client.user_playlist_create.return_value = {"id": "spotify-playlist"}
    spotify_client.playlist_items.return_value = {"items": [], "next": None}

    with MatchCache(tmp_path / "matches.sqlite3") as cache:
        report = Migrator(
            TidalSource(tidal_session),
            SpotifyDestination(spotify_client),
            cache,
            dry_run=False,
        ).migrate(None, False)

    assert report.matched == 1
    spotify_client.user_playlist_create.assert_called_once_with(
        "me",
        "Mix",
        public=False,
        description="Description",
    )
    spotify_client.playlist_add_items.assert_called_once_with(
        "spotify-playlist",
        ["spotify-track"],
    )
