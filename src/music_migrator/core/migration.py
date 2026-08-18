import time
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from threading import Lock

from music_migrator.core.cache import MatchCache
from music_migrator.core.matching import best_match, track_fingerprint
from music_migrator.core.models import Playlist, Track, TrackMatch
from music_migrator.core.reconciliation import PlaylistMode, plan_playlist
from music_migrator.core.retry import retry_request
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


@dataclass(slots=True)
class MatchResults:
    matched: list[str] = field(default_factory=list)
    unmatched: list[Track] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.source_ids)


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
        self._reject_duplicate_playlist_names(source_playlists)
        self._progress(f"Loading {self._destination.display_name} playlists", None, None)
        destinations = retry_request(self._destination.playlists_by_name)
        report = MigrationReport()
        for playlist in source_playlists:
            results = self._match_tracks(
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
            plan = plan_playlist(results.matched, existing, mode=self._mode)
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
                self._destination.sync_playlist(target, list(plan.desired))
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
            results = self._match_tracks(self._source.saved_tracks(), collection_name)
            if self._dry_run:
                existing = retry_request(self._destination.favorite_track_ids)
                changed = any(track_id not in existing for track_id in results.matched)
            else:
                label = f"{self._destination.display_name} {self._destination.saved_tracks_name}"
                self._progress(f"Syncing {label}", None, None)
                changed = self._destination.add_favorites(results.matched) > 0
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

    def _match_tracks(self, tracks: Iterable[Track], collection_name: str) -> MatchResults:
        label = f"Matching {collection_name}"
        self._progress(label, 0, None)
        results = MatchResults()
        indexed_tracks = iter(enumerate(tracks))
        completed = 0
        next_result = 0
        with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
            pending: dict[Future[TrackMatch], int] = {}
            completed_results: dict[int, TrackMatch] = {}
            for _ in range(self._max_concurrency):
                item = next(indexed_tracks, None)
                if item is None:
                    break
                index, track = item
                pending[executor.submit(self._match_track, track)] = index

            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    completed_results[pending.pop(future)] = future.result()
                    completed += 1
                    self._progress(label, completed, None)

                while next_result in completed_results:
                    result = completed_results.pop(next_result)
                    results.source_ids.append(result.source.source_id)
                    if result.destination_id:
                        results.matched.append(result.destination_id)
                    else:
                        results.unmatched.append(result.source)
                    next_result += 1

                window_size = len(pending) + len(completed_results)
                for _ in range(self._max_concurrency - window_size):
                    item = next(indexed_tracks, None)
                    if item is None:
                        break
                    index, track = item
                    pending[executor.submit(self._match_track, track)] = index

        self._progress(label, completed, completed)
        return results

    def _match_track(self, track: Track) -> TrackMatch:
        fingerprint = track_fingerprint(track)
        cached = self._cache.get(track.source_id, fingerprint)
        if cached:
            return TrackMatch(track, cached, 1.0, "cache")
        candidates = retry_request(
            lambda: self._destination.search_tracks(track, before_request=self._rate_limiter.wait)
        )
        result = best_match(track, candidates)
        if result.destination_id:
            self._cache.put(track.source_id, result.destination_id, fingerprint)
        return result
