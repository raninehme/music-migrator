import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock

from music_migrator.core.cache import MatchCache
from music_migrator.core.matching import best_match
from music_migrator.core.models import Track, TrackMatch
from music_migrator.services.base import MusicDestination, MusicSource


@dataclass(slots=True)
class CollectionReport:
    name: str
    source_tracks: int
    matched_tracks: int
    unmatched: list[Track] = field(default_factory=list)
    changed: bool = False


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
        max_concurrency: int = 10,
        rate_limit: int = 10,
        progress: Callable[[str, int | None, int | None], None] | None = None,
    ):
        self._source = source
        self._destination = destination
        self._cache = cache
        self._dry_run = dry_run
        self._max_concurrency = max_concurrency
        self._rate_limiter = RateLimiter(rate_limit)
        self._progress = progress or (lambda _label, _current, _total: None)

    def migrate(self, playlist_ids: list[str] | None, include_saved: bool) -> MigrationReport:
        self._progress("Loading Spotify playlists", None, None)
        source_playlists = (
            [self._source.playlist(item) for item in playlist_ids]
            if playlist_ids
            else list(self._source.playlists())
        )
        self._progress("Loading TIDAL playlists", None, None)
        destinations = self._destination.playlists_by_name()
        report = MigrationReport()
        for playlist in source_playlists:
            tracks = list(self._source.playlist_tracks(playlist.source_id))
            matched, unmatched = self._match_tracks(tracks, playlist.name)
            target = destinations.get(playlist.name)
            changed = target is None or self._destination.playlist_track_ids(target) != matched
            if not self._dry_run and changed:
                if target is None:
                    self._progress(f"Creating TIDAL playlist {playlist.name}", None, None)
                    target = self._destination.create_playlist(playlist.name, playlist.description)
                    destinations[playlist.name] = target
                self._progress(f"Syncing TIDAL playlist {playlist.name}", None, None)
                self._destination.sync_playlist(target, matched)
            report.collections.append(
                CollectionReport(playlist.name, len(tracks), len(matched), unmatched, changed)
            )

        if include_saved:
            tracks = list(self._source.saved_tracks())
            matched, unmatched = self._match_tracks(tracks, "Liked Songs")
            changed = bool(matched)
            if not self._dry_run:
                self._progress("Syncing TIDAL favorites", None, None)
                changed = self._destination.add_favorites(matched) > 0
            report.collections.append(
                CollectionReport("Liked Songs", len(tracks), len(matched), unmatched, changed)
            )
        return report

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
        self._rate_limiter.wait()
        result = best_match(
            track, self._destination.search_tracks(track, before_request=self._rate_limiter.wait)
        )
        if result.destination_id:
            self._cache.put(track.source_id, result.destination_id)
        return result
