"""Render CLI progress, migration summaries, and unmatched-track reports."""

import csv
import logging
import sys
from collections.abc import Iterable
from pathlib import Path

from music_migrator.application import RouteReport
from music_migrator.domain.models import Track
from music_migrator.migration import MigrationReport, MigrationRoute
from music_migrator.profiles import ProfilePaths

logger = logging.getLogger(__name__)


class ConsoleProgress:
    def __init__(self, *, quiet: bool):
        self._quiet = quiet

    def __call__(self, label: str, current: int | None, total: int | None) -> None:
        if current is None:
            logger.info(label)
            return
        if current == 0 and total is not None:
            logger.info("%s: %d tracks", label, total)
        if self._quiet:
            return
        if total is None:
            print(f"{label}: {current}", end="\r", file=sys.stderr, flush=True)
            return
        if total == 0:
            return
        percent = (current / total) * 100
        end = "\n" if current >= total else "\r"
        print(
            f"{label}: {current}/{total} ({percent:5.1f}%)",
            end=end,
            file=sys.stderr,
            flush=True,
        )


def present_reports(
    reports: Iterable[RouteReport],
    paths: ProfilePaths,
    *,
    dry_run: bool,
    show_routes: bool,
) -> None:
    for route_report in reports:
        write_unmatched(
            route_report.report,
            paths.for_route(route_report.route.key).unmatched_report,
        )
        print_report(
            route_report.report,
            dry_run=dry_run,
            route=route_report.route if show_routes else None,
        )


def print_report(
    report: MigrationReport, *, dry_run: bool, route: MigrationRoute | None = None
) -> None:
    mode = "DRY RUN" if dry_run else "APPLIED"
    heading = f"{mode} {route.key}" if route else mode
    print(f"\n{heading}")
    for item in report.collections:
        action = "change" if item.changed else "unchanged"
        print(
            f"{item.name}: {item.matched_tracks}/{item.source_tracks} matched, "
            f"{len(item.unmatched)} unmatched, {action}"
        )
    print(f"Total: {report.matched} matched, {len(report.unmatched)} unmatched")


def write_unmatched(report: MigrationReport, path: Path) -> None:
    if not report.unmatched:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("source_collections", "source_id", "title", "artists", "album", "isrc"))
        tracks: dict[str, Track] = {}
        collections: dict[str, list[str]] = {}
        for collection in report.collections:
            for track in collection.unmatched:
                tracks.setdefault(track.source_id, track)
                names = collections.setdefault(track.source_id, [])
                if collection.name not in names:
                    names.append(collection.name)

        for source_id, track in tracks.items():
            writer.writerow(
                (
                    "; ".join(collections[source_id]),
                    track.source_id,
                    track.title,
                    "; ".join(track.artists),
                    track.album,
                    track.isrc,
                )
            )
    logger.warning("Unmatched tracks written to %s", path)
