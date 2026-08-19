"""Wire configured providers and migration components into executable routes."""

import json
import logging
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass

from music_migrator.config import MigrationConfig
from music_migrator.matching import MatchCache
from music_migrator.migration import MigrationReport, MigrationRoute, Migrator, plan_route
from music_migrator.persistence import NullMigrationJournal, SQLiteMigrationJournal
from music_migrator.profiles import ProfilePaths
from music_migrator.reconciliation import PlaylistMode
from music_migrator.services.base import MusicDestination, MusicSource

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int | None, int | None], None]


@dataclass(frozen=True, slots=True)
class RouteReport:
    route: MigrationRoute
    report: MigrationReport


def run_migration(
    route: MigrationRoute,
    config: MigrationConfig,
    paths: ProfilePaths,
    *,
    dry_run: bool,
    mode: PlaylistMode,
    playlist_ids: list[str] | None,
    include_saved: bool,
    refresh_matches: bool,
    progress: ProgressCallback,
) -> Iterator[RouteReport]:
    """Run one migration route and, for combine mode, its reverse route."""
    forward_report = _run_route(
        route,
        config,
        paths,
        dry_run=dry_run,
        mode=mode,
        playlist_ids=playlist_ids,
        playlist_names=None,
        include_saved=include_saved,
        refresh_matches=refresh_matches,
        progress=progress,
    )
    yield RouteReport(route, forward_report)
    if mode != "combine":
        return

    reverse_route = plan_route(route.destination.name, route.source.name)
    playlist_names = (
        {item.name for item in forward_report.collections if not item.saved}
        if playlist_ids
        else None
    )
    reverse_report = _run_route(
        reverse_route,
        config,
        paths,
        dry_run=dry_run,
        mode="combine",
        playlist_ids=None,
        playlist_names=playlist_names,
        include_saved=include_saved,
        refresh_matches=refresh_matches,
        progress=progress,
    )
    yield RouteReport(reverse_route, reverse_report)


def _authenticate_route(
    route: MigrationRoute,
    config: MigrationConfig,
    paths: ProfilePaths,
) -> tuple[MusicSource, MusicDestination]:
    for service in (route.source, route.destination):
        if service.validate_config is not None:
            service.validate_config(config)

    source_authenticator = route.source.authenticate_source
    destination_authenticator = route.destination.authenticate_destination
    if source_authenticator is None or destination_authenticator is None:
        raise RuntimeError(f"Route {route.key} is not fully configured")

    logger.info("Authenticating with %s", route.source.name)
    source = source_authenticator(config, paths.session_for(route.source.name))
    logger.info("Authenticating with %s", route.destination.name)
    destination = destination_authenticator(config, paths.session_for(route.destination.name))
    return source, destination


def _migration_scope(
    *,
    mode: PlaylistMode,
    playlist_ids: list[str] | None,
    playlist_names: set[str] | None,
    include_saved: bool,
) -> str:
    return json.dumps(
        {
            "include_saved": include_saved,
            "mode": mode,
            "playlist_ids": sorted(playlist_ids) if playlist_ids else None,
            "playlist_names": sorted(playlist_names) if playlist_names is not None else None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


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
    refresh_matches: bool,
    progress: ProgressCallback,
) -> MigrationReport:
    source, destination = _authenticate_route(route, config, paths)
    route_paths = paths.for_route(route.key)
    scope_key = _migration_scope(
        mode=mode,
        playlist_ids=playlist_ids,
        playlist_names=playlist_names,
        include_saved=include_saved,
    )
    with ExitStack() as stack:
        cache = stack.enter_context(MatchCache(route_paths.match_cache))
        journal = (
            NullMigrationJournal()
            if dry_run
            else stack.enter_context(SQLiteMigrationJournal(route_paths.migration_state))
        )
        if refresh_matches:
            cache.clear()
        requests = config.requests_for(route.destination.name, route.destination.request_defaults)
        return Migrator(
            source,
            destination,
            cache,
            dry_run=dry_run,
            mode=mode,
            max_concurrency=requests.max_concurrency,
            rate_limit=requests.rate_limit,
            progress=progress,
            journal=journal,
            scope_key=scope_key,
        ).migrate(
            playlist_ids,
            include_saved,
            playlist_names=playlist_names,
        )
