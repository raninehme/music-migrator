import argparse
import logging
import sys
import time
from collections.abc import Iterable

from music_migrator import __version__
from music_migrator.application import run_migration
from music_migrator.cli_output import ConsoleProgress, present_reports
from music_migrator.config import MigrationConfig, render_profile_config
from music_migrator.logging_config import configure_logging
from music_migrator.migration import MigrationRoute, plan_route
from music_migrator.profiles import ProfilePaths
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
    parser.add_argument(
        "--refresh-matches",
        action="store_true",
        help="discard cached matches for every route this command runs",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm a match-cache refresh without an interactive prompt",
    )
    parser.add_argument("--quiet", action="store_true", help="show errors and final report only")
    parser.add_argument("--debug", action="store_true", help="show debug logs and tracebacks")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.yes and not args.refresh_matches:
        parser.error("--yes may be used only with --refresh-matches")
    profile_name = args.setup or args.profile
    try:
        paths = ProfilePaths.for_name(profile_name)
    except ValueError as error:
        parser.error(str(error))

    paths.prepare()
    configure_logging(paths.log_file, quiet=args.quiet, debug=args.debug)

    try:
        if args.setup:
            return _handle_setup(args, parser, paths)
        if args.reset_auth:
            return _handle_reset_auth(args, parser, paths, profile_name)
        return _handle_migration(args, parser, paths, profile_name)
    except Exception as error:
        if args.debug:
            logger.exception("Migration failed")
        else:
            logger.error("Migration failed: %s", error)
        return 1


def _handle_setup(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    paths: ProfilePaths,
) -> int:
    if args.dry_run or args.apply or args.reset_auth or args.refresh_matches:
        parser.error("--setup cannot be combined with migration or reset options")
    route = plan_route(args.source_service, args.destination_service)
    _setup_profile(
        paths,
        args.setup,
        (route.source.name, route.destination.name),
    )
    return 0


def _handle_reset_auth(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    paths: ProfilePaths,
    profile_name: str,
) -> int:
    if args.dry_run or args.apply or args.refresh_matches:
        parser.error("--reset-auth cannot be combined with --dry-run or --apply")
    removed = paths.reset_auth(SERVICES)
    logger.info(
        "Reset authentication for profile %s (%d sessions removed)",
        profile_name,
        removed,
    )
    return 0


def _handle_migration(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    paths: ProfilePaths,
    profile_name: str,
) -> int:
    if not args.dry_run and not args.apply:
        parser.error("choose exactly one migration mode: --dry-run or --apply")
    started = time.perf_counter()
    route = plan_route(args.source_service, args.destination_service)
    _confirm_match_refresh(args, route)
    config = MigrationConfig.load(paths.config)
    _log_migration_start(args, route, config, profile_name)

    reports = run_migration(
        route,
        config,
        paths,
        dry_run=not args.apply,
        mode=args.mode,
        playlist_ids=args.playlist or None,
        include_saved=config.include_saved_tracks and not args.no_saved_tracks,
        refresh_matches=args.refresh_matches,
        progress=ConsoleProgress(quiet=args.quiet),
    )
    present_reports(
        reports,
        paths,
        dry_run=not args.apply,
        show_routes=args.mode == "combine",
    )
    logger.info("Completed in %.1f seconds", time.perf_counter() - started)
    return 0


def _confirm_match_refresh(args: argparse.Namespace, route: MigrationRoute) -> None:
    if not args.refresh_matches:
        return

    route_keys = [route.key]
    if args.mode == "combine":
        route_keys.append(f"{route.destination.name}-to-{route.source.name}")
    routes = "\n".join(f"  {route_key}" for route_key in route_keys)
    print(
        "WARNING: This will clear cached matches for:\n"
        f"{routes}\n\n"
        "All tracks will be searched again and may consume significant API quota.",
        file=sys.stderr,
    )
    if args.yes:
        return
    if not sys.stdin.isatty():
        raise RuntimeError(
            "--refresh-matches requires interactive confirmation; add --yes to continue"
        )
    if input("Continue? [y/N] ").strip().casefold() not in {"y", "yes"}:
        raise RuntimeError("Match refresh cancelled")


def _log_migration_start(
    args: argparse.Namespace,
    route: MigrationRoute,
    config: MigrationConfig,
    profile_name: str,
) -> None:
    requests = config.requests_for(route.destination.name, route.destination.request_defaults)
    logger.info(
        "Starting %s using %s mode from %s to %s for profile %s with %d workers "
        "and %d requests/second",
        "migration" if args.apply else "dry run",
        args.mode,
        route.source.name,
        route.destination.name,
        profile_name,
        requests.max_concurrency,
        requests.rate_limit,
    )


def _setup_profile(
    paths: ProfilePaths,
    profile_name: str,
    service_names: Iterable[str],
) -> None:
    if paths.config.exists():
        raise FileExistsError(f"Profile '{profile_name}' is already configured at {paths.config}")

    sections = []
    for service_name in service_names:
        service = SERVICES[service_name]
        if service.profile_setup is not None:
            sections.append(service.profile_setup(service.request_defaults))

    with paths.config.open("x", encoding="utf-8") as output:
        output.write(render_profile_config(sections))
    paths.config.chmod(0o600)
    logger.info("Created profile %s at %s", profile_name, paths.config)


if __name__ == "__main__":
    raise SystemExit(main())
