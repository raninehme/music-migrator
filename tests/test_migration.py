from types import SimpleNamespace
from unittest.mock import Mock

from music_migrator.core.cache import MatchCache
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
    selected = Playlist("selected", "Selected")
    ignored = Playlist("ignored", "Ignored")
    source = Mock()
    source.playlists.return_value = [selected, ignored]
    source.playlist_tracks.return_value = []
    destination = Mock()
    destination.playlists_by_name.return_value = {
        "Selected": SimpleNamespace(),
        "Ignored": SimpleNamespace(),
    }
    destination.playlist_track_ids.return_value = []

    with MatchCache(tmp_path / "cache.sqlite3") as cache:
        report = Migrator(source, destination, cache, dry_run=True).migrate(
            None,
            False,
            playlist_names={"Selected"},
        )

    assert [item.name for item in report.collections] == ["Selected"]
    source.playlist_tracks.assert_called_once_with("selected")
