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
from music_migrator.core.migration import MigrationReport, Migrator, PlaylistMode
from music_migrator.core.models import Track
from music_migrator.core.planning import MigrationRoute, plan_route
from music_migrator.logging_config import configure_logging
from music_migrator.profiles import ProfilePaths
from music_migrator.services.base import MusicDestination, MusicSource
from music_migrator.services.registry import SERVICES

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Move music between streaming services")
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--profile", metavar="NAME")
    identity.add_argument("--setup", metavar="NAME", help="create a new profile configuration")
    parser.add_argument(
        "--from",
        dest="source_service",
        choices=sorted(SERVICES),
        default="spotify",
        help="source service (default: spotify)",
    )
    parser.add_argument(
        "--to",
        dest="destination_service",
        choices=sorted(SERVICES),
        default="tidal",
        help="destination service (default: tidal)",
    )
    parser.add_argument("--playlist", action="append", default=[], metavar="PLAYLIST_ID")
    parser.add_argument("--no-saved-tracks", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    mode.add_argument("--apply", action="store_true", help="write changes to the destination")
    parser.add_argument(
        "--mode",
        choices=("replace", "combine"),
        default="replace",
        help="replace destination playlists or combine both services (default: replace)",
    )
    parser.add_argument(
        "--reset-auth", action="store_true", help="remove profile login sessions and exit"
    )
    parser.add_argument("--quiet", action="store_true", help="show errors and final report only")
    parser.add_argument("--debug", action="store_true", help="show debug logs and tracebacks")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _authenticate_route(
    route: MigrationRoute,
    config: MigrationConfig,
    paths: ProfilePaths,
) -> tuple[MusicSource, MusicDestination]:
    source_authenticator = route.source.authenticate_source
    destination_authenticator = route.destination.authenticate_destination
    if source_authenticator is None or destination_authenticator is None:
        raise RuntimeError(f"Route {route.key} is not fully configured")

    logger.info("Authenticating with %s", route.source.name)
    source = source_authenticator(config, paths.session_for(route.source.name))
    logger.info("Authenticating with %s", route.destination.name)
    destination = destination_authenticator(
        config,
        paths.session_for(route.destination.name),
    )
    return source, destination


def _run_route(
    route: MigrationRoute,
    config: MigrationConfig,
    paths: ProfilePaths,
    *,
    dry_run: bool,
    mode: PlaylistMode,
    playlist_ids: list[str] | None,
    playlist_names: set[str] | None,
    include_saved: bool,
    quiet: bool,
) -> MigrationReport:
    source, destination = _authenticate_route(route, config, paths)
    route_paths = paths.for_route(route.key)
    with MatchCache(route_paths.match_cache) as cache:
        report = Migrator(
            source,
            destination,
            cache,
            dry_run=dry_run,
            mode=mode,
            max_concurrency=config.max_concurrency,
            rate_limit=config.rate_limit,
            progress=ConsoleProgress(quiet=quiet),
        ).migrate(
            playlist_ids,
            include_saved,
            playlist_names=playlist_names,
        )
    _write_unmatched(report, route_paths.unmatched_report)
    return report


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

        route = plan_route(args.source_service, args.destination_service)
        config = MigrationConfig.load(paths.config)
        logger.info(
            "Starting %s using %s mode from %s to %s for profile %s with %d workers "
            "and %d requests/second",
            "migration" if args.apply else "dry run",
            args.mode,
            route.source.name,
            route.destination.name,
            profile_name,
            config.max_concurrency,
            config.rate_limit,
        )
        include_saved = config.include_saved_tracks and not args.no_saved_tracks
        report = _run_route(
            route,
            config,
            paths,
            dry_run=not args.apply,
            mode=args.mode,
            playlist_ids=args.playlist or None,
            playlist_names=None,
            include_saved=include_saved,
            quiet=args.quiet,
        )
        reports = [(route, report)]
        if args.mode == "combine":
            reverse_route = plan_route(route.destination.name, route.source.name)
            playlist_names = (
                {item.name for item in report.collections if not item.saved}
                if args.playlist
                else None
            )
            reverse_report = _run_route(
                reverse_route,
                config,
                paths,
                dry_run=not args.apply,
                mode="combine",
                playlist_ids=None,
                playlist_names=playlist_names,
                include_saved=include_saved,
                quiet=args.quiet,
            )
            reports.append((reverse_route, reverse_report))

        show_routes = len(reports) > 1
        for report_route, migration_report in reports:
            _print_report(
                migration_report,
                dry_run=not args.apply,
                route=report_route if show_routes else None,
            )
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


def _print_report(
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


def _write_unmatched(report: MigrationReport, path: Path) -> None:
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
