from types import SimpleNamespace
from unittest.mock import Mock

from music_migrator.domain.models import Playlist, Track
from music_migrator.matching import MatchCache
from music_migrator.migration import Migrator


def test_replace_keeps_existing_playlist_when_nothing_matches(tmp_path):
    source_track = Track("source-1", "Missing", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    target = SimpleNamespace()
    destination.playlists_by_name.return_value = {"Mix": target}
    destination.search_tracks.return_value = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=False).migrate(None, False)

    assert report.collections[0].source_tracks == 1
    assert report.collections[0].matched_tracks == 0
    assert report.collections[0].unmatched == [source_track]
    assert report.collections[0].changed is False
    destination.playlist_track_ids.assert_not_called()
    destination.create_playlist.assert_not_called()
    destination.append_playlist_tracks.assert_not_called()
    destination.replace_playlist_tracks.assert_not_called()


def test_replace_does_not_create_empty_playlist_when_nothing_matches(tmp_path):
    source_track = Track("source-1", "Missing", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    destination.playlists_by_name.return_value = {}
    destination.search_tracks.return_value = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=False).migrate(None, False)

    assert report.collections[0].source_tracks == 1
    assert report.collections[0].matched_tracks == 0
    assert report.collections[0].changed is False
    destination.create_playlist.assert_not_called()
    destination.append_playlist_tracks.assert_not_called()
    destination.replace_playlist_tracks.assert_not_called()


def test_replace_still_applies_when_only_some_tracks_match(tmp_path):
    matched_source = Track("source-1", "Found", ("Artist",), "Album", 180, "ISRC1")
    unmatched_source = Track("source-2", "Missing", ("Artist",), "Album", 180, "ISRC2")
    candidate = Track("target-1", "Found", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = [matched_source, unmatched_source]
    destination = Mock()
    target = SimpleNamespace()
    destination.playlists_by_name.return_value = {"Mix": target}
    destination.playlist_track_ids.return_value = ["target-only"]
    destination.search_tracks.side_effect = [[candidate], []]

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(
            source,
            destination,
            cache,
            dry_run=False,
            max_concurrency=1,
        ).migrate(None, False)

    assert report.collections[0].source_tracks == 2
    assert report.collections[0].matched_tracks == 1
    assert report.collections[0].unmatched == [unmatched_source]
    assert report.collections[0].changed is True
    destination.replace_playlist_tracks.assert_called_once_with(
        target,
        ["target-1"],
        original_track_ids=["target-only"],
    )
