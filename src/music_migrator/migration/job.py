"""Orchestrate collection discovery, matching, reconciliation, and provider writes."""

from collections.abc import Callable

from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.domain.models import Playlist
from music_migrator.matching import MatchCache, MatchEngine
from music_migrator.migration.reports import CollectionReport, MigrationReport
from music_migrator.persistence import MigrationJournal, NullMigrationJournal
from music_migrator.reconciliation import (
    PlaylistMode,
    apply_playlist_plan,
    apply_saved_tracks_plan,
    plan_playlist,
    plan_saved_tracks,
)
from music_migrator.services.base import MusicDestination, MusicSource
from music_migrator.transport.retry import retry_request


class Migrator:
    """Execute one provider-to-provider migration route."""

    def __init__(
        self,
        source: MusicSource,
        destination: MusicDestination,
        cache: MatchCache,
        *,
        dry_run: bool,
        mode: PlaylistMode = "replace",
        max_concurrency: int = 10,
        rate_limit: int = 10,
        progress: Callable[[str, int | None, int | None], None] | None = None,
        journal: MigrationJournal | None = None,
        scope_key: str = "default",
    ):
        self._source = source
        self._destination = destination
        self._dry_run = dry_run
        if mode not in ("combine", "replace"):
            raise ValueError(f"unknown migration mode: {mode}")
        self._mode = mode
        self._progress = progress or (lambda _label, _current, _total: None)
        self._matcher = MatchEngine(
            destination,
            cache,
            max_concurrency=max_concurrency,
            rate_limit=rate_limit,
            progress=self._progress,
        )
        self._journal = NullMigrationJournal() if dry_run or journal is None else journal
        self._scope_key = scope_key

    def migrate(
        self,
        playlist_ids: list[str] | None,
        include_saved: bool,
        *,
        playlist_names: set[str] | None = None,
    ) -> MigrationReport:
        """Discover selected collections and reconcile them with the destination."""
        self._progress(f"Loading {self._source.display_name} playlists", None, None)
        source_playlists = (
            [retry_request(lambda item=item: self._source.playlist(item)) for item in playlist_ids]
            if playlist_ids
            else retry_request(lambda: list(self._source.playlists()))
        )
        if playlist_names is not None:
            source_playlists = [item for item in source_playlists if item.name in playlist_names]
        self._reject_duplicate_playlist_names(source_playlists)
        self._progress(f"Loading {self._destination.display_name} playlists", None, None)
        destinations = retry_request(self._destination.playlists_by_name)

        run = self._journal.start_run(self._scope_key)
        if run.resumed:
            self._progress("Resuming interrupted migration", None, None)

        report = MigrationReport()
        for playlist in source_playlists:
            collection_key = f"playlist:{playlist.source_id}"
            self._journal.begin_collection(run.run_id, collection_key)
            results = self._matcher.match_tracks(
                self._source.playlist_tracks(playlist.source_id), playlist.name
            )
            if results.count == 0:
                self._journal.plan_operations(run.run_id, collection_key, ())
                self._journal.complete_collection(run.run_id, collection_key)
                continue
            if self._mode == "replace" and not results.matched:
                self._journal.plan_operations(run.run_id, collection_key, ())
                self._journal.complete_collection(run.run_id, collection_key)
                report.collections.append(
                    CollectionReport(
                        playlist.name,
                        results.count,
                        0,
                        results.unmatched,
                        False,
                    )
                )
                continue

            target = destinations.get(playlist.name)
            existing = (
                retry_request(lambda target=target: self._destination.playlist_track_ids(target))
                if target is not None
                else []
            )
            current = CollectionSnapshot.playlist(
                collection_key,
                playlist.name,
                existing,
            )
            plan = plan_playlist(results.matched, current, mode=self._mode)
            self._journal.plan_operations(run.run_id, collection_key, plan.operations)
            changed = target is None or plan.changed
            if not self._dry_run and changed:
                if target is None:
                    self._progress(
                        f"Creating {self._destination.display_name} playlist {playlist.name}",
                        None,
                        None,
                    )
                    target = self._destination.create_playlist(playlist.name, playlist.description)
                    destinations[playlist.name] = target
                self._progress(
                    f"Syncing {self._destination.display_name} playlist {playlist.name}",
                    None,
                    None,
                )
                apply_playlist_plan(
                    self._destination,
                    target,
                    plan,
                    after_operation=lambda operation, key=collection_key: (
                        self._journal.complete_operation(run.run_id, key, operation)
                    ),
                )
            self._journal.complete_collection(run.run_id, collection_key)
            report.collections.append(
                CollectionReport(
                    playlist.name,
                    results.count,
                    len(results.matched),
                    results.unmatched,
                    changed,
                )
            )

        if include_saved:
            collection_key = "saved-tracks"
            self._journal.begin_collection(run.run_id, collection_key)
            collection_name = self._source.saved_tracks_name
            results = self._matcher.match_tracks(self._source.saved_tracks(), collection_name)
            existing = retry_request(self._destination.saved_track_ids)
            current = CollectionSnapshot.saved_tracks(
                collection_key,
                self._destination.saved_tracks_name,
                existing,
            )
            plan = plan_saved_tracks(results.matched, current)
            self._journal.plan_operations(run.run_id, collection_key, plan.operations)
            changed = plan.changed
            if not self._dry_run and changed:
                label = f"{self._destination.display_name} {self._destination.saved_tracks_name}"
                self._progress(f"Syncing {label}", None, None)
                apply_saved_tracks_plan(
                    self._destination,
                    plan,
                    after_operation=lambda operation: self._journal.complete_operation(
                        run.run_id, collection_key, operation
                    ),
                )
            self._journal.complete_collection(run.run_id, collection_key)
            report.collections.append(
                CollectionReport(
                    collection_name,
                    results.count,
                    len(results.matched),
                    results.unmatched,
                    changed,
                    saved=True,
                )
            )

        self._journal.complete_run(run.run_id)
        return report

    @staticmethod
    def _reject_duplicate_playlist_names(playlists: list[Playlist]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for playlist in playlists:
            if playlist.name in seen:
                duplicates.add(playlist.name)
            seen.add(playlist.name)
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(f"Source contains duplicate playlist names: {names}")
