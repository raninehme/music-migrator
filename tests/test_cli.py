import argparse
import csv

import pytest
import yaml

from music_migrator.cli import _handle_migration, _setup_profile, _write_unmatched, main
from music_migrator.core.migration import CollectionReport, MigrationReport
from music_migrator.core.models import Track
from music_migrator.profiles import ProfilePaths


def test_unmatched_report_deduplicates_source_tracks(tmp_path):
    track = Track("spotify-1", "Song", ("Artist",), "Album", 180, "ISRC")
    report = MigrationReport(
        [
            CollectionReport("One", 1, 0, [track]),
            CollectionReport("Two", 1, 0, [track]),
        ]
    )
    output = tmp_path / "reports" / "unmatched.csv"

    _write_unmatched(report, output)

    with output.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    assert rows[0]["source_collections"] == "One; Two"
    assert rows[0]["source_id"] == "spotify-1"


def test_setup_writes_profile_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "client-id")
    monkeypatch.setattr("music_migrator.cli.getpass.getpass", lambda _: "client-secret")
    paths = ProfilePaths.for_name("rani")
    paths.prepare()

    _setup_profile(paths, "rani")

    raw = yaml.safe_load(paths.config.read_text())
    assert raw["spotify"]["client_id"] == "client-id"
    assert raw["spotify"]["client_secret"] == "client-secret"
    assert raw["max_concurrency"] == 10
    assert raw["rate_limit"] == 10


def test_setup_refuses_to_overwrite_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    paths.config.write_text("existing")

    with pytest.raises(FileExistsError, match="already configured"):
        _setup_profile(paths, "rani")

    assert paths.config.read_text() == "existing"


def test_migration_mode_is_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        main(["--profile", "rani"])


def test_migration_handler_delegates_execution_and_presentation(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    paths.config.write_text(
        """spotify:
  client_id: client
  client_secret: secret
"""
    )
    args = argparse.Namespace(
        apply=False,
        debug=False,
        destination_service="tidal",
        dry_run=True,
        mode="replace",
        no_saved_tracks=False,
        playlist=["playlist-1"],
        quiet=True,
        refresh_matches=True,
        source_service="spotify",
    )
    reports = [mocker.Mock()]
    run_migration = mocker.patch("music_migrator.cli.run_migration", return_value=reports)
    present_reports = mocker.patch("music_migrator.cli._present_reports")

    result = _handle_migration(args, mocker.Mock(), paths, "rani")

    assert result == 0
    run_migration.assert_called_once()
    assert run_migration.call_args.args[0].key == "spotify-to-tidal"
    assert run_migration.call_args.kwargs["playlist_ids"] == ["playlist-1"]
    assert run_migration.call_args.kwargs["refresh_matches"] is True
    present_reports.assert_called_once_with(reports, paths, dry_run=True)
