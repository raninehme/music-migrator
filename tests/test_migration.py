from types import SimpleNamespace
from unittest.mock import Mock

from music_migrator.cache import MatchCache
from music_migrator.migration import Migrator
from music_migrator.models import Playlist, Track


def test_dry_run_never_creates_or_changes_playlist(tmp_path):
    source_track = Track("s1", "Song", ("Artist",), "Album", 180, "ISRC1")
    candidate = Track("t1", "Song", ("Artist",), "Album", 180, "ISRC1")
    spotify = Mock()
    spotify.playlists.return_value = [Playlist("p1", "Mix")]
    spotify.playlist_tracks.return_value = [source_track]
    spotify.saved_tracks.return_value = []
    tidal = Mock()
    tidal.playlists_by_name.return_value = {}
    tidal.search_tracks.return_value = [candidate]

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(spotify, tidal, cache, dry_run=True).migrate(None, False)

    assert report.matched == 1
    assert report.collections[0].changed is True
    tidal.create_playlist.assert_not_called()
    tidal.sync_playlist.assert_not_called()


def test_apply_creates_and_syncs_playlist(tmp_path):
    source_track = Track("s1", "Song", ("Artist",), "Album", 180, "ISRC1")
    candidate = Track("t1", "Song", ("Artist",), "Album", 180, "ISRC1")
    spotify = Mock()
    spotify.playlists.return_value = [Playlist("p1", "Mix", "Description")]
    spotify.playlist_tracks.return_value = [source_track]
    tidal = Mock()
    tidal.playlists_by_name.return_value = {}
    tidal.search_tracks.return_value = [candidate]
    target = SimpleNamespace()
    tidal.create_playlist.return_value = target

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        Migrator(spotify, tidal, cache, dry_run=False).migrate(None, False)

    tidal.create_playlist.assert_called_once_with("Mix", "Description")
    tidal.sync_playlist.assert_called_once_with(target, ["t1"])
