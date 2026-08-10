import csv

import pytest
import yaml

from music_migrator.cli import _setup_profile, _write_unmatched, main
from music_migrator.core.migration import CollectionReport, MigrationReport
from music_migrator.core.models import Track
from music_migrator.profiles import ProfilePaths


def test_unmatched_report_deduplicates_spotify_tracks(tmp_path):
    track = Track("spotify-1", "Song", ("Artist",), "Album", 180, "ISRC")
    report = MigrationReport(
        [
            CollectionReport("One", 1, 0, [track]),
            CollectionReport("Two", 1, 0, [track]),
        ]
    )
    output = tmp_path / "unmatched.csv"

    _write_unmatched(report, output)

    with output.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    assert rows[0]["spotify_id"] == "spotify-1"


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
