"""Coordinate cached, concurrent, rate-limited track matching for a collection."""

import time
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from threading import Lock
from typing import Protocol

from music_migrator.core.models import Track, TrackMatch
from music_migrator.core.retry import retry_request
from music_migrator.matching.cache import MatchCache
from music_migrator.matching.normalization import track_fingerprint
from music_migrator.matching.scoring import best_match

ProgressCallback = Callable[[str, int | None, int | None], None]


class CandidateSearcher(Protocol):
    """Provider capability required by the matching engine."""

    def search_tracks(
        self,
        source: Track,
        limit: int = 20,
        before_request: Callable[[], None] | None = None,
    ) -> list[Track]: ...


@dataclass(slots=True)
class MatchResults:
    """Collect ordered match outcomes for one source collection."""

    matched: list[str] = field(default_factory=list)
    unmatched: list[Track] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.source_ids)


class _RateLimiter:
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


class MatchEngine:
    """Match source tracks to destination candidates without performing destination writes."""

    def __init__(
        self,
        destination: CandidateSearcher,
        cache: MatchCache,
        *,
        max_concurrency: int = 10,
        rate_limit: int = 10,
        progress: ProgressCallback | None = None,
    ):
        self._destination = destination
        self._cache = cache
        self._max_concurrency = max_concurrency
        self._rate_limiter = _RateLimiter(rate_limit)
        self._progress = progress or (lambda _label, _current, _total: None)

    def match_tracks(self, tracks: Iterable[Track], collection_name: str) -> MatchResults:
        """Match a collection concurrently while preserving source order in the result."""
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
            lambda: self._destination.search_tracks(
                track,
                before_request=self._rate_limiter.wait,
            )
        )
        result = best_match(track, candidates)
        if result.destination_id:
            self._cache.put(track.source_id, result.destination_id, fingerprint)
        return result
