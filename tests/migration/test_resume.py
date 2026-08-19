import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from music_migrator.domain.models import Playlist, Track
from music_migrator.matching import MatchCache
from music_migrator.migration import Migrator
from music_migrator.persistence import SQLiteMigrationJournal
from music_migrator.persistence.migrations import operation_key
from music_migrator.reconciliation.operations import AppendPlaylistTracks


def test_interrupted_playlist_append_resumes_from_remote_prefix(tmp_path):
    source_tracks = [
        Track("source-1", "One", ("Artist",), "Album", 180, "ISRC1"),
        Track("source-2", "Two", ("Artist",), "Album", 180, "ISRC2"),
    ]
    source = Mock(display_name="Source")
    source.playlists.return_value = [Playlist("playlist-1", "Mix")]
    source.playlist_tracks.return_value = source_tracks

    target = SimpleNamespace()
    remote_ids: list[str] = []
    destination = Mock(display_name="Destination")
    destination.playlists_by_name.return_value = {"Mix": target}
    destination.playlist_track_ids.side_effect = lambda _: list(remote_ids)
    destination.search_tracks.side_effect = lambda track, **_: [
        Track(
            f"target-{track.source_id[-1]}",
            track.title,
            track.artists,
            track.album,
            track.duration_seconds,
            track.isrc,
        )
    ]

    interrupted = False

    def append_tracks(_, track_ids, *, expected_before):
        nonlocal interrupted
        if not interrupted:
            assert expected_before == []
            assert track_ids == ["target-1", "target-2"]
            remote_ids[:] = ["target-1"]
            interrupted = True
            raise RuntimeError("process interrupted after first track")
        assert expected_before == ["target-1"]
        assert track_ids == ["target-2"]
        remote_ids.extend(track_ids)

    destination.append_playlist_tracks.side_effect = append_tracks
    cache_path = tmp_path / "matches.sqlite3"
    journal_path = tmp_path / "migration.sqlite3"

    with (
        MatchCache(cache_path) as cache,
        SQLiteMigrationJournal(journal_path) as journal,
        pytest.raises(RuntimeError, match="process interrupted"),
    ):
        Migrator(
            source,
            destination,
            cache,
            dry_run=False,
            max_concurrency=1,
            journal=journal,
            scope_key="scope",
        ).migrate(None, False)

    progress: list[str] = []
    with MatchCache(cache_path) as cache, SQLiteMigrationJournal(journal_path) as journal:
        report = Migrator(
            source,
            destination,
            cache,
            dry_run=False,
            max_concurrency=1,
            journal=journal,
            scope_key="scope",
            progress=lambda label, *_: progress.append(label),
        ).migrate(None, False)

    assert remote_ids == ["target-1", "target-2"]
    assert destination.append_playlist_tracks.call_count == 2
    assert report.collections[0].changed is True
    assert "Resuming interrupted migration" in progress

    original = AppendPlaylistTracks(("target-1", "target-2"))
    resumed = AppendPlaylistTracks(("target-2",))
    connection = sqlite3.connect(journal_path)
    runs = connection.execute("SELECT status FROM migration_runs").fetchall()
    operations = dict(connection.execute("SELECT operation_key, status FROM migration_operations"))
    connection.close()

    assert runs == [("completed",)]
    assert operations == {
        operation_key(original): "superseded",
        operation_key(resumed): "completed",
    }
