from types import SimpleNamespace
from unittest.mock import Mock

from music_migrator.domain.models import Playlist, Track
from music_migrator.matching import MatchCache
from music_migrator.migration import Migrator


def test_combine_does_not_create_empty_playlist_when_nothing_matches(tmp_path):
    source_track = Track("source-1", "Missing", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    destination.playlists_by_name.return_value = {}
    destination.search_tracks.return_value = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=False, mode="combine").migrate(
            None, False
        )

    assert report.collections[0].source_tracks == 1
    assert report.collections[0].matched_tracks == 0
    assert report.collections[0].unmatched == [source_track]
    assert report.collections[0].changed is False
    destination.playlist_track_ids.assert_not_called()
    destination.create_playlist.assert_not_called()
    destination.append_playlist_tracks.assert_not_called()
    destination.replace_playlist_tracks.assert_not_called()


def test_combine_keeps_existing_playlist_when_nothing_matches(tmp_path):
    source_track = Track("source-1", "Missing", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    destination.playlists_by_name.return_value = {"Mix": SimpleNamespace()}
    destination.search_tracks.return_value = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=False, mode="combine").migrate(
            None, False
        )

    assert report.collections[0].source_tracks == 1
    assert report.collections[0].matched_tracks == 0
    assert report.collections[0].unmatched == [source_track]
    assert report.collections[0].changed is False
    destination.playlist_track_ids.assert_not_called()
    destination.create_playlist.assert_not_called()
    destination.append_playlist_tracks.assert_not_called()
    destination.replace_playlist_tracks.assert_not_called()
