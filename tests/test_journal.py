from music_migrator.core.journal import MigrationJournal


def test_incomplete_run_is_resumed(tmp_path):
    path = tmp_path / "state.sqlite3"

    with MigrationJournal(path) as journal:
        run_id, resumed = journal.begin_or_resume("spotify-to-tidal", "replace")
        journal.mark_collection(
            run_id,
            "playlist:one",
            kind="playlist",
            status="in_progress",
            desired_fingerprint="abc",
        )

    with MigrationJournal(path) as journal:
        resumed_run_id, resumed = journal.begin_or_resume("spotify-to-tidal", "replace")
        assert resumed is True
        assert resumed_run_id == run_id
        assert journal.collection_status(run_id, "playlist:one") == "in_progress"


def test_completed_run_is_not_resumed(tmp_path):
    path = tmp_path / "state.sqlite3"

    with MigrationJournal(path) as journal:
        first_run_id, resumed = journal.begin_or_resume("spotify-to-tidal", "replace")
        assert resumed is False
        journal.mark_collection(
            first_run_id,
            "playlist:one",
            kind="playlist",
            status="completed",
            desired_fingerprint="abc",
        )
        journal.complete_run(first_run_id)

        second_run_id, resumed = journal.begin_or_resume("spotify-to-tidal", "replace")
        assert resumed is False
        assert second_run_id != first_run_id


def test_routes_and_modes_resume_independently(tmp_path):
    path = tmp_path / "state.sqlite3"

    with MigrationJournal(path) as journal:
        replace_run, _ = journal.begin_or_resume("spotify-to-tidal", "replace")
        combine_run, combine_resumed = journal.begin_or_resume("spotify-to-tidal", "combine")
        reverse_run, reverse_resumed = journal.begin_or_resume("tidal-to-spotify", "combine")

        assert combine_resumed is False
        assert reverse_resumed is False
        assert len({replace_run, combine_run, reverse_run}) == 3
