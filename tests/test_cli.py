import csv

from music_migrator.cli import _write_unmatched
from music_migrator.migration import CollectionReport, MigrationReport
from music_migrator.models import Track


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
