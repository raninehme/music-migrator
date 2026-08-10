import argparse
import csv
import getpass
import logging
import sys
import time
from pathlib import Path

import yaml

from music_migrator import __version__
from music_migrator.config import MigrationConfig
from music_migrator.core.cache import MatchCache
from music_migrator.core.migration import MigrationReport, Migrator
from music_migrator.logging_config import configure_logging
from music_migrator.profiles import ProfilePaths
from music_migrator.services.spotify.service import SpotifySource
from music_migrator.services.tidal.service import TidalDestination

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate Spotify music to TIDAL")
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--profile", metavar="NAME")
    identity.add_argument("--setup", metavar="NAME", help="create a new profile configuration")
    parser.add_argument("--playlist", action="append", default=[], metavar="SPOTIFY_ID")
    parser.add_argument("--no-saved-tracks", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    mode.add_argument("--apply", action="store_true", help="write changes to TIDAL")
    parser.add_argument(
        "--reset-auth", action="store_true", help="remove profile login sessions and exit"
    )
    parser.add_argument("--quiet", action="store_true", help="show errors and final report only")
    parser.add_argument("--debug", action="store_true", help="show debug logs and tracebacks")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    profile_name = args.setup or args.profile
    try:
        paths = ProfilePaths.for_name(profile_name)
    except ValueError as error:
        parser.error(str(error))
    paths.prepare()
    configure_logging(paths.log_file, quiet=args.quiet, debug=args.debug)
    started = time.perf_counter()

    try:
        if args.setup:
            if args.dry_run or args.apply or args.reset_auth:
                parser.error("--setup cannot be combined with migration or reset options")
            _setup_profile(paths, args.setup)
            return 0

        if args.reset_auth:
            if args.dry_run or args.apply:
                parser.error("--reset-auth cannot be combined with --dry-run or --apply")
            removed = paths.reset_auth()
            logger.info(
                "Reset authentication for profile %s (%d sessions removed)",
                profile_name,
                removed,
            )
            return 0

        if not args.dry_run and not args.apply:
            parser.error("choose exactly one migration mode: --dry-run or --apply")

        config = MigrationConfig.load(paths.config)
        logger.info(
            "Starting %s for profile %s with %d workers and %d requests/second",
            "migration" if args.apply else "dry run",
            profile_name,
            config.max_concurrency,
            config.rate_limit,
        )
        logger.info("Authenticating with Spotify")
        spotify = SpotifySource.authenticate(config.spotify, paths.spotify_session)
        logger.info("Authenticating with TIDAL")
        tidal = TidalDestination.authenticate(paths.tidal_session)
        with MatchCache(paths.match_cache) as cache:
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
        _write_unmatched(report, paths.unmatched_report)
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


def _setup_profile(paths: ProfilePaths, profile_name: str) -> None:
    if paths.config.exists():
        raise FileExistsError(f"Profile '{profile_name}' is already configured at {paths.config}")

    client_id = input("Spotify client ID: ").strip()
    client_secret = getpass.getpass("Spotify client secret: ").strip()
    if not client_id or not client_secret:
        raise ValueError("Spotify client ID and client secret are required")

    config = {
        "spotify": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "http://127.0.0.1:8888/callback",
            "open_browser": True,
        },
        "include_saved_tracks": True,
        "max_concurrency": 10,
        "rate_limit": 10,
    }
    with paths.config.open("x", encoding="utf-8") as output:
        yaml.safe_dump(config, output, sort_keys=False)
    paths.config.chmod(0o600)
    logger.info("Created profile %s at %s", profile_name, paths.config)


if __name__ == "__main__":
    raise SystemExit(main())
