from music_migrator.core.journal import MigrationJournal, migration_scope_fingerprint


def test_incomplete_run_is_resumed(tmp_path):
    path = tmp_path / "state.sqlite3"
    scope = migration_scope_fingerprint(None, None, include_saved=True)

    with MigrationJournal(path) as journal:
        run_id, resumed = journal.begin_or_resume("spotify-to-tidal", "replace", scope)
        assert resumed is False
        journal.mark_collection(
            run_id,
            "playlist:one",
            kind="playlist",
            status="in_progress",
            desired_fingerprint="abc",
        )

    with MigrationJournal(path) as journal:
        resumed_run_id, resumed = journal.begin_or_resume(
            "spotify-to-tidal", "replace", scope
        )
        assert resumed is True
        assert resumed_run_id == run_id
        assert journal.collection_status(run_id, "playlist:one") == "in_progress"


def test_completed_run_is_not_resumed(tmp_path):
    path = tmp_path / "state.sqlite3"
    scope = migration_scope_fingerprint(None, None, include_saved=False)

    with MigrationJournal(path) as journal:
        first_run_id, resumed = journal.begin_or_resume(
            "spotify-to-tidal", "replace", scope
        )
        assert resumed is False
        journal.mark_collection(
            first_run_id,
            "playlist:one",
            kind="playlist",
            status="completed",
            desired_fingerprint="abc",
        )
        journal.complete_run(first_run_id)

        second_run_id, resumed = journal.begin_or_resume(
            "spotify-to-tidal", "replace", scope
        )
        assert resumed is False
        assert second_run_id != first_run_id


def test_routes_modes_and_scopes_resume_independently(tmp_path):
    path = tmp_path / "state.sqlite3"
    all_scope = migration_scope_fingerprint(None, None, include_saved=False)
    selected_scope = migration_scope_fingerprint(["playlist-1"], None, include_saved=False)

    with MigrationJournal(path) as journal:
        replace_run, _ = journal.begin_or_resume(
            "spotify-to-tidal", "replace", all_scope
        )
        combine_run, combine_resumed = journal.begin_or_resume(
            "spotify-to-tidal", "combine", all_scope
        )
        reverse_run, reverse_resumed = journal.begin_or_resume(
            "tidal-to-spotify", "combine", all_scope
        )
        selected_run, selected_resumed = journal.begin_or_resume(
            "spotify-to-tidal", "replace", selected_scope
        )

        assert combine_resumed is False
        assert reverse_resumed is False
        assert selected_resumed is False
        assert len({replace_run, combine_run, reverse_run, selected_run}) == 4


def test_scope_fingerprint_is_order_independent_for_explicit_selection():
    first = migration_scope_fingerprint(["b", "a"], None, include_saved=True)
    second = migration_scope_fingerprint(["a", "b"], None, include_saved=True)

    assert first == second


def test_scope_fingerprint_distinguishes_saved_tracks_and_all_playlists():
    without_saved = migration_scope_fingerprint(None, None, include_saved=False)
    with_saved = migration_scope_fingerprint(None, None, include_saved=True)
    selected = migration_scope_fingerprint(["playlist-1"], None, include_saved=False)

    assert without_saved != with_saved
    assert without_saved != selected
