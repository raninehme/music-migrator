from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from music_migrator.core.cache import MatchCache
from music_migrator.core.matching import track_fingerprint
from music_migrator.core.migration import Migrator
from music_migrator.core.models import Playlist, Track


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


def test_progress_uses_service_display_names(tmp_path):
    source = Mock(display_name="Spotify")
    destination = Mock(display_name="TIDAL")
    source.playlists.return_value = []
    destination.playlists_by_name.return_value = {}
    messages = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        Migrator(
            source,
            destination,
            cache,
            dry_run=True,
            progress=lambda label, *_: messages.append(label),
        ).migrate(None, False)

    assert messages == ["Loading Spotify playlists", "Loading TIDAL playlists"]


def test_empty_source_playlist_is_skipped(tmp_path):
    source = Mock()
    source.playlists.return_value = [Playlist("empty", "Old playlist")]
    source.playlist_tracks.return_value = []
    destination = Mock()
    destination.playlists_by_name.return_value = {}

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=False).migrate(None, False)

    assert report.collections == []
    destination.create_playlist.assert_not_called()
    destination.sync_playlist.assert_not_called()


def test_combine_preserves_destination_tracks_after_source_order(tmp_path):
    source_track = Track("source-1", "Source", ("Artist",), "Album", 180, "ISRC1")
    candidate = Track("target-1", "Source", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("source-playlist", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    target = SimpleNamespace()
    destination.playlists_by_name.return_value = {"Mix": target}
    destination.playlist_track_ids.return_value = ["target-only", "target-1"]
    destination.search_tracks.return_value = [candidate]

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        Migrator(source, destination, cache, dry_run=False, mode="combine").migrate(None, False)

    destination.sync_playlist.assert_called_once_with(target, ["target-1", "target-only"])


def test_replace_removes_destination_only_tracks(tmp_path):
    source_track = Track("source-1", "Source", ("Artist",), "Album", 180, "ISRC1")
    candidate = Track("target-1", "Source", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("source-playlist", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    target = SimpleNamespace()
    destination.playlists_by_name.return_value = {"Mix": target}
    destination.playlist_track_ids.return_value = ["target-only"]
    destination.search_tracks.return_value = [candidate]

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        Migrator(source, destination, cache, dry_run=False).migrate(None, False)

    destination.sync_playlist.assert_called_once_with(target, ["target-1"])


def test_can_select_reverse_playlists_by_name(tmp_path):
    source_track = Track("source-track", "Song", ("Artist",), "Album", 180, "ISRC1")
    candidate = Track("target-track", "Song", ("Artist",), "Album", 180, "ISRC1")
    selected = Playlist("selected", "Selected")
    ignored = Playlist("ignored", "Ignored")
    source = Mock()
    source.playlists.return_value = [selected, ignored]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    destination.playlists_by_name.return_value = {
        "Selected": SimpleNamespace(),
        "Ignored": SimpleNamespace(),
    }
    destination.playlist_track_ids.return_value = []
    destination.search_tracks.return_value = [candidate]

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=True).migrate(
            None,
            False,
            playlist_names={"Selected"},
        )

    assert [item.name for item in report.collections] == ["Selected"]
    source.playlist_tracks.assert_called_once_with("selected")


def test_saved_tracks_dry_run_is_unchanged_when_all_favorites_exist(tmp_path):
    source_track = Track("source", "Song", ("Artist",), "Album", 180, "ISRC")
    candidate = Track("target", "Song", ("Artist",), "Album", 180, "ISRC")
    source = Mock(saved_tracks_name="Liked Songs")
    source.playlists.return_value = []
    source.saved_tracks.return_value = [source_track]
    destination = Mock(saved_tracks_name="Favorites")
    destination.playlists_by_name.return_value = {}
    destination.search_tracks.return_value = [candidate]
    destination.favorite_track_ids.return_value = {"target"}

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=True).migrate(None, True)

    assert report.collections[0].changed is False
    destination.add_favorites.assert_not_called()


def test_saved_tracks_dry_run_reports_missing_favorites(tmp_path):
    source_track = Track("source", "Song", ("Artist",), "Album", 180, "ISRC")
    candidate = Track("target", "Song", ("Artist",), "Album", 180, "ISRC")
    source = Mock(saved_tracks_name="Liked Songs")
    source.playlists.return_value = []
    source.saved_tracks.return_value = [source_track]
    destination = Mock(saved_tracks_name="Favorites")
    destination.playlists_by_name.return_value = {}
    destination.search_tracks.return_value = [candidate]
    destination.favorite_track_ids.return_value = set()

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=True).migrate(None, True)

    assert report.collections[0].changed is True


def test_failed_playlist_write_preserves_cached_matches(tmp_path):
    source_track = Track("source-1", "Song", ("Artist",), "Album", 180, "ISRC")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = [source_track]
    destination = Mock()
    destination.playlists_by_name.return_value = {"Mix": SimpleNamespace()}
    destination.playlist_track_ids.return_value = []
    destination.sync_playlist.side_effect = RuntimeError("write failed")

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        fingerprint = track_fingerprint(source_track)
        cache.put("source-1", "destination-1", fingerprint)
        with pytest.raises(RuntimeError, match="write failed"):
            Migrator(source, destination, cache, dry_run=False).migrate(None, False)
        assert cache.get("source-1", fingerprint) == "destination-1"


def test_failed_saved_tracks_write_preserves_cached_matches(tmp_path):
    source_track = Track("source-1", "Song", ("Artist",), "Album", 180, "ISRC")
    source = Mock(saved_tracks_name="Liked Songs")
    source.playlists.return_value = []
    source.saved_tracks.return_value = [source_track]
    destination = Mock(saved_tracks_name="Favorites")
    destination.playlists_by_name.return_value = {}
    destination.add_favorites.side_effect = RuntimeError("write failed")

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        fingerprint = track_fingerprint(source_track)
        cache.put("source-1", "destination-1", fingerprint)
        with pytest.raises(RuntimeError, match="write failed"):
            Migrator(source, destination, cache, dry_run=False).migrate(None, True)
        assert cache.get("source-1", fingerprint) == "destination-1"


def test_duplicate_source_playlist_names_stop_before_destination_loading(tmp_path):
    source = Mock()
    source.playlists.return_value = [
        Playlist("one", "Duplicate"),
        Playlist("two", "Duplicate"),
    ]
    destination = Mock()

    with (
        MatchCache(tmp_path / "cache.sqlite3") as cache,
        pytest.raises(ValueError, match="duplicate playlist names: Duplicate"),
    ):
        Migrator(source, destination, cache, dry_run=False).migrate(None, False)

    destination.playlists_by_name.assert_not_called()
    destination.create_playlist.assert_not_called()
    destination.sync_playlist.assert_not_called()


def test_saved_tracks_are_consumed_incrementally_and_keep_order(tmp_path):
    tracks = [
        Track(f"source-{index}", f"Song {index}", ("Artist",), "Album", 180, f"ISRC{index}")
        for index in range(7)
    ]
    source = Mock(saved_tracks_name="Liked Songs")
    source.playlists.return_value = []
    source.saved_tracks.return_value = (track for track in tracks)
    destination = Mock(saved_tracks_name="Favorites")
    destination.playlists_by_name.return_value = {}
    destination.search_tracks.side_effect = lambda track, **_: [
        Track(
            f"target-{track.source_id}",
            track.title,
            track.artists,
            track.album,
            track.duration_seconds,
            track.isrc,
        )
    ]
    destination.favorite_track_ids.return_value = set()

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(
            source,
            destination,
            cache,
            dry_run=True,
            max_concurrency=2,
        ).migrate(None, True)

    assert report.collections[0].source_tracks == 7
    assert report.collections[0].matched_tracks == 7


def test_late_source_iteration_failure_stops_before_destination_write(tmp_path):
    first = Track("source-1", "First", ("Artist",), "Album", 180, "ISRC1")
    source = Mock()
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]

    def failing_tracks():
        yield first
        raise RuntimeError("later page failed")

    source.playlist_tracks.return_value = failing_tracks()
    destination = Mock()
    destination.playlists_by_name.return_value = {}
    destination.search_tracks.return_value = [
        Track("target-1", "First", ("Artist",), "Album", 180, "ISRC1")
    ]

    with (
        MatchCache(tmp_path / "cache.sqlite3") as cache,
        pytest.raises(RuntimeError, match="later page failed"),
    ):
        Migrator(source, destination, cache, dry_run=False).migrate(None, False)

    destination.create_playlist.assert_not_called()
    destination.sync_playlist.assert_not_called()
