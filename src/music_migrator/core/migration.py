"""Orchestrate collection discovery, matching, reconciliation, and provider writes."""

from collections.abc import Callable
from dataclasses import dataclass, field

from music_migrator.core.models import Playlist, Track
from music_migrator.core.retry import retry_request
from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.matching import MatchCache, MatchEngine
from music_migrator.reconciliation import (
    PlaylistMode,
    apply_playlist_plan,
    apply_saved_tracks_plan,
    plan_playlist,
    plan_saved_tracks,
)
from music_migrator.services.base import MusicDestination, MusicSource


@dataclass(slots=True)
class CollectionReport:
    name: str
    source_tracks: int
    matched_tracks: int
    unmatched: list[Track] = field(default_factory=list)
    changed: bool = False
    saved: bool = False


@dataclass(slots=True)
class MigrationReport:
    collections: list[CollectionReport] = field(default_factory=list)

    @property
    def matched(self) -> int:
        return sum(item.matched_tracks for item in self.collections)

    @property
    def unmatched(self) -> list[Track]:
        return [track for item in self.collections for track in item.unmatched]


class Migrator:
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

    def migrate(
        self,
        playlist_ids: list[str] | None,
        include_saved: bool,
        *,
        playlist_names: set[str] | None = None,
    ) -> MigrationReport:
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
        report = MigrationReport()
        for playlist in source_playlists:
            results = self._matcher.match_tracks(
                self._source.playlist_tracks(playlist.source_id), playlist.name
            )
            if results.count == 0:
                continue
            target = destinations.get(playlist.name)
            existing = (
                retry_request(lambda target=target: self._destination.playlist_track_ids(target))
                if target is not None
                else []
            )
            current = CollectionSnapshot.playlist(
                f"playlist:{playlist.source_id}",
                playlist.name,
                existing,
            )
            plan = plan_playlist(results.matched, current, mode=self._mode)
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
                apply_playlist_plan(self._destination, target, plan)
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
            collection_name = self._source.saved_tracks_name
            results = self._matcher.match_tracks(self._source.saved_tracks(), collection_name)
            existing = retry_request(self._destination.saved_track_ids)
            current = CollectionSnapshot.saved_tracks(
                "saved-tracks",
                self._destination.saved_tracks_name,
                existing,
            )
            plan = plan_saved_tracks(results.matched, current)
            changed = plan.changed
            if not self._dry_run and changed:
                label = f"{self._destination.display_name} {self._destination.saved_tracks_name}"
                self._progress(f"Syncing {label}", None, None)
                apply_saved_tracks_plan(self._destination, plan)
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
