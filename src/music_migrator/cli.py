import argparse
import csv
import logging
import sys
import time
from pathlib import Path

from music_migrator import __version__
from music_migrator.cache import MatchCache
from music_migrator.config import MigrationConfig
from music_migrator.logging_config import configure_logging
from music_migrator.migration import MigrationReport, Migrator
from music_migrator.spotify import SpotifySource
from music_migrator.tidal import TidalDestination

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate Spotify music to TIDAL")
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--playlist", action="append", default=[], metavar="SPOTIFY_ID")
    parser.add_argument("--no-saved-tracks", action="store_true")
    parser.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
    parser.add_argument("--quiet", action="store_true", help="show errors and final report only")
    parser.add_argument("--debug", action="store_true", help="show debug logs and tracebacks")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(quiet=args.quiet, debug=args.debug)
    started = time.perf_counter()
    try:
        config = MigrationConfig.load(args.config)
        logger.info(
            "Starting %s with %d workers and %d requests/second",
            "migration" if args.apply else "dry run",
            config.max_concurrency,
            config.rate_limit,
        )
        logger.info("Authenticating with Spotify")
        spotify = SpotifySource.authenticate(config.spotify)
        logger.info("Authenticating with TIDAL")
        tidal = TidalDestination.authenticate()
        with MatchCache(Path(".music-migrator-cache.sqlite3")) as cache:
            report = Migrator(
                spotify,
                tidal,
                cache,
                dry_run=not args.apply,
                max_concurrency=config.max_concurrency,
                rate_limit=config.rate_limit,
                progress=ConsoleProgress(quiet=args.quiet),
            ).migrate(
                args.playlist or None,
                config.include_saved_tracks and not args.no_saved_tracks,
            )
        _print_report(report, dry_run=not args.apply)
        _write_unmatched(report, Path("unmatched.csv"))
        logger.info("Completed in %.1f seconds", time.perf_counter() - started)
        return 0
    except Exception as error:
        if args.debug:
            logger.exception("Migration failed")
        else:
            logger.error("Migration failed: %s", error)
        return 1


class ConsoleProgress:
    def __init__(self, *, quiet: bool):
        self._quiet = quiet

    def __call__(self, label: str, current: int | None, total: int | None) -> None:
        if current is None or total is None:
            logger.info(label)
            return
        if current == 0:
            logger.info("%s: %d tracks", label, total)
        if self._quiet or total == 0:
            return
        percent = (current / total) * 100
        end = "\n" if current >= total else "\r"
        print(
            f"{label}: {current}/{total} ({percent:5.1f}%)",
            end=end,
            file=sys.stderr,
            flush=True,
        )


def _print_report(report: MigrationReport, *, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n{mode}")
    for item in report.collections:
        action = "change" if item.changed else "unchanged"
        print(
            f"{item.name}: {item.matched_tracks}/{item.source_tracks} matched, "
            f"{len(item.unmatched)} unmatched, {action}"
        )
    print(f"Total: {report.matched} matched, {len(report.unmatched)} unmatched")


def _write_unmatched(report: MigrationReport, path: Path) -> None:
    if not report.unmatched:
        path.unlink(missing_ok=True)
        return
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("spotify_id", "title", "artists", "album", "isrc"))
        seen: set[str] = set()
        for track in report.unmatched:
            if track.source_id in seen:
                continue
            seen.add(track.source_id)
            writer.writerow(
                (track.source_id, track.title, "; ".join(track.artists), track.album, track.isrc)
            )
    logger.warning("Unmatched tracks written to %s", path)


if __name__ == "__main__":
    raise SystemExit(main())
