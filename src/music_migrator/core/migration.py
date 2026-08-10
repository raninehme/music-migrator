import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock
from typing import Literal

from music_migrator.core.cache import MatchCache
from music_migrator.core.matching import best_match
from music_migrator.core.models import Track, TrackMatch
from music_migrator.core.retry import retry_request
from music_migrator.services.base import MusicDestination, MusicSource

PlaylistMode = Literal["combine", "replace"]


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


class RateLimiter:
    def __init__(self, requests_per_second: int):
        self._limit = requests_per_second
        self._starts: deque[float] = deque()
        self._lock = Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._starts and self._starts[0] <= now - 1:
                    self._starts.popleft()
                if len(self._starts) < self._limit:
                    self._starts.append(now)
                    return
                delay = self._starts[0] + 1 - now
            time.sleep(delay)


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
        self._cache = cache
        self._dry_run = dry_run
        if mode not in ("combine", "replace"):
            raise ValueError(f"unknown migration mode: {mode}")
        self._mode = mode
        self._max_concurrency = max_concurrency
        self._rate_limiter = RateLimiter(rate_limit)
        self._progress = progress or (lambda _label, _current, _total: None)

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
        self._progress(f"Loading {self._destination.display_name} playlists", None, None)
        destinations = retry_request(self._destination.playlists_by_name)
        report = MigrationReport()
        for playlist in source_playlists:
            tracks = retry_request(
                lambda playlist=playlist: list(self._source.playlist_tracks(playlist.source_id))
            )
            if not tracks:
                continue
            matched, unmatched = self._match_tracks(tracks, playlist.name)
            target = destinations.get(playlist.name)
            existing = (
                retry_request(lambda target=target: self._destination.playlist_track_ids(target))
                if target is not None
                else []
            )
            desired = self._desired_playlist_tracks(matched, existing)
            changed = target is None or existing != desired
            if not self._dry_run and changed:
                if target is None:
                    self._progress(
                        f"Creating {self._destination.display_name} playlist {playlist.name}",
                        None,
                        None,
                    )
                    target = retry_request(
                        lambda playlist=playlist: self._destination.create_playlist(
                            playlist.name, playlist.description
                        )
                    )
                    destinations[playlist.name] = target
                self._progress(
                    f"Syncing {self._destination.display_name} playlist {playlist.name}",
                    None,
                    None,
                )
                retry_request(
                    lambda target=target, desired=desired: self._destination.sync_playlist(
                        target, desired
                    )
                )
            report.collections.append(
                CollectionReport(playlist.name, len(tracks), len(matched), unmatched, changed)
            )

        if include_saved:
            collection_name = self._source.saved_tracks_name
            tracks = retry_request(lambda: list(self._source.saved_tracks()))
            matched, unmatched = self._match_tracks(tracks, collection_name)
            changed = bool(matched)
            if not self._dry_run:
                label = f"{self._destination.display_name} {self._destination.saved_tracks_name}"
                self._progress(f"Syncing {label}", None, None)
                changed = retry_request(lambda: self._destination.add_favorites(matched)) > 0
            report.collections.append(
                CollectionReport(
                    collection_name,
                    len(tracks),
                    len(matched),
                    unmatched,
                    changed,
                    saved=True,
                )
            )
        return report

    def _desired_playlist_tracks(self, matched: list[str], existing: list[str]) -> list[str]:
        if self._mode == "replace":
            return matched
        matched_ids = set(matched)
        return [*matched, *(track_id for track_id in existing if track_id not in matched_ids)]

    def _match_tracks(
        self, tracks: list[Track], collection_name: str
    ) -> tuple[list[str], list[Track]]:
        label = f"Matching {collection_name}"
        self._progress(label, 0, len(tracks))
        results: list[TrackMatch | None] = [None] * len(tracks)
        with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
            pending = {
                executor.submit(self._match_track, track): index
                for index, track in enumerate(tracks)
            }
            for completed, future in enumerate(as_completed(pending), start=1):
                results[pending[future]] = future.result()
                self._progress(label, completed, len(tracks))

        ordered = [result for result in results if result is not None]
        matched = [result.destination_id for result in ordered if result.destination_id]
        unmatched = [result.source for result in ordered if result.destination_id is None]
        return matched, unmatched

    def _match_track(self, track: Track) -> TrackMatch:
        cached = self._cache.get(track.source_id)
        if cached:
            return TrackMatch(track, cached, 1.0, "cache")
        candidates = retry_request(
            lambda: self._destination.search_tracks(track, before_request=self._rate_limiter.wait)
        )
        result = best_match(track, candidates)
        if result.destination_id:
            self._cache.put(track.source_id, result.destination_id)
        return result
