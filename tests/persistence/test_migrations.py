import sqlite3

from music_migrator.persistence import SQLiteMigrationJournal
from music_migrator.persistence.migrations import operation_key
from music_migrator.reconciliation.operations import AppendPlaylistTracks


def test_incomplete_scope_is_resumed(tmp_path):
    path = tmp_path / "migration.sqlite3"

    with SQLiteMigrationJournal(path) as journal:
        first = journal.start_run("scope")

    with SQLiteMigrationJournal(path) as journal:
        resumed = journal.start_run("scope")

    assert resumed.run_id == first.run_id
    assert resumed.resumed is True


def test_completed_scope_starts_a_new_run(tmp_path):
    path = tmp_path / "migration.sqlite3"

    with SQLiteMigrationJournal(path) as journal:
        first = journal.start_run("scope")
        journal.complete_run(first.run_id)
        second = journal.start_run("scope")

    assert second.run_id != first.run_id
    assert second.resumed is False


def test_replanning_supersedes_stale_pending_operation(tmp_path):
    path = tmp_path / "migration.sqlite3"
    original = AppendPlaylistTracks(("one", "two"))
    resumed = AppendPlaylistTracks(("two",))

    with SQLiteMigrationJournal(path) as journal:
        run = journal.start_run("scope")
        journal.begin_collection(run.run_id, "playlist:p1")
        journal.plan_operations(run.run_id, "playlist:p1", (original,))
        journal.plan_operations(run.run_id, "playlist:p1", (resumed,))
        journal.complete_operation(run.run_id, "playlist:p1", resumed)

    connection = sqlite3.connect(path)
    rows = dict(connection.execute("SELECT operation_key, status FROM migration_operations"))
    connection.close()

    assert rows == {
        operation_key(original): "superseded",
        operation_key(resumed): "completed",
    }
