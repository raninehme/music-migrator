"""Orchestrate collection discovery, matching, reconciliation, and provider writes."""

import hashlib
from collections.abc import Callable, Iterable

from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.domain.models import Playlist, Track
from music_migrator.matching import MatchCache, MatchEngine, MatchResults, track_fingerprint
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


def _source_fingerprint(
    source_ids: Iterable[str],
    fingerprints: Iterable[str],
    *,
    ordered: bool,
) -> str:
    items = [
        f"{source_id}\0{fingerprint}" for source_id, fingerprint in zip(source_ids, fingerprints)
    ]
    if not ordered:
        items.sort()
    return hashlib.sha256("\x01".join(items).encode()).hexdigest()


def _track_source_fingerprint(tracks: list[Track], *, ordered: bool) -> str:
    return _source_fingerprint(
        (track.source_id for track in tracks),
        (track_fingerprint(track) for track in tracks),
        ordered=ordered,
    )


def _result_source_fingerprint(results: MatchResults, *, ordered: bool) -> str:
    return _source_fingerprint(
        results.source_ids,
        results.source_fingerprints,
        ordered=ordered,
    )


def _destination_fingerprint(
    track_ids: Iterable[str],
    *,
    present: bool = True,
    ordered: bool,
) -> str:
    items = list(track_ids)
    if not ordered:
        items.sort()
    payload = ["present" if present else "missing", *items]
    return hashlib.sha256("\0".join(payload).encode()).hexdigest()


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
            checkpoint = self._journal.collection_checkpoint(run.run_id, collection_key)
            target = None
            existing: list[str] | None = None
            source_tracks: Iterable[Track] = self._source.playlist_tracks(playlist.source_id)

            if run.resumed and checkpoint is not None and checkpoint.reusable:
                validated_tracks = list(source_tracks)
                source_tracks = validated_tracks
                source_state = _track_source_fingerprint(validated_tracks, ordered=True)
                target = destinations.get(playlist.name)
                existing = (
                    retry_request(
                        lambda target=target: self._destination.playlist_track_ids(target)
                    )
                    if target is not None
                    else []
                )
                destination_state = _destination_fingerprint(
                    existing,
                    present=target is not None,
                    ordered=True,
                )
                if (
                    source_state == checkpoint.source_fingerprint
                    and destination_state == checkpoint.destination_fingerprint
                ):
                    unmatched_ids = set(checkpoint.unmatched_source_ids)
                    report.collections.append(
                        CollectionReport(
                            playlist.name,
                            len(validated_tracks),
                            checkpoint.matched_tracks,
                            [
                                track
                                for track in validated_tracks
                                if track.source_id in unmatched_ids
                            ],
                            False,
                        )
                    )
                    continue

            self._journal.begin_collection(run.run_id, collection_key)
            results = self._matcher.match_tracks(source_tracks, playlist.name)
            source_state = _result_source_fingerprint(results, ordered=True)
            unmatched_ids = tuple(track.source_id for track in results.unmatched)
            if results.count == 0:
                self._journal.plan_operations(run.run_id, collection_key, ())
                self._journal.complete_collection(
                    run.run_id,
                    collection_key,
                    source_fingerprint=source_state,
                    matched_tracks=0,
                )
                continue
            if self._mode == "replace" and not results.matched:
                self._journal.plan_operations(run.run_id, collection_key, ())
                self._journal.complete_collection(
                    run.run_id,
                    collection_key,
                    source_fingerprint=source_state,
                    matched_tracks=0,
                    unmatched_source_ids=unmatched_ids,
                )
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

            if target is None:
                target = destinations.get(playlist.name)
            if existing is None:
                existing = (
                    retry_request(
                        lambda target=target: self._destination.playlist_track_ids(target)
                    )
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
            self._journal.complete_collection(
                run.run_id,
                collection_key,
                source_fingerprint=source_state,
                destination_fingerprint=_destination_fingerprint(
                    plan.desired.track_ids,
                    ordered=True,
                ),
                matched_tracks=len(results.matched),
                unmatched_source_ids=unmatched_ids,
            )
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
            collection_name = self._source.saved_tracks_name
            checkpoint = self._journal.collection_checkpoint(run.run_id, collection_key)
            source_tracks = self._source.saved_tracks()
            existing_saved: set[str] | None = None

            if run.resumed and checkpoint is not None and checkpoint.reusable:
                validated_tracks = list(source_tracks)
                source_tracks = validated_tracks
                source_state = _track_source_fingerprint(validated_tracks, ordered=False)
                existing_saved = retry_request(self._destination.saved_track_ids)
                destination_state = _destination_fingerprint(existing_saved, ordered=False)
                if (
                    source_state == checkpoint.source_fingerprint
                    and destination_state == checkpoint.destination_fingerprint
                ):
                    unmatched_ids = set(checkpoint.unmatched_source_ids)
                    report.collections.append(
                        CollectionReport(
                            collection_name,
                            len(validated_tracks),
                            checkpoint.matched_tracks,
                            [
                                track
                                for track in validated_tracks
                                if track.source_id in unmatched_ids
                            ],
                            False,
                            saved=True,
                        )
                    )
                    self._journal.complete_run(run.run_id)
                    return report

            self._journal.begin_collection(run.run_id, collection_key)
            results = self._matcher.match_tracks(source_tracks, collection_name)
            source_state = _result_source_fingerprint(results, ordered=False)
            unmatched_ids = tuple(track.source_id for track in results.unmatched)
            if existing_saved is None:
                existing_saved = retry_request(self._destination.saved_track_ids)
            current = CollectionSnapshot.saved_tracks(
                collection_key,
                self._destination.saved_tracks_name,
                existing_saved,
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
            self._journal.complete_collection(
                run.run_id,
                collection_key,
                source_fingerprint=source_state,
                destination_fingerprint=_destination_fingerprint(
                    plan.desired.track_ids,
                    ordered=False,
                ),
                matched_tracks=len(results.matched),
                unmatched_source_ids=unmatched_ids,
            )
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
