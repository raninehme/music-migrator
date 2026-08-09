from dataclasses import dataclass, field

from music_migrator.cache import MatchCache
from music_migrator.matching import best_match
from music_migrator.models import Track, TrackMatch
from music_migrator.spotify import SpotifySource
from music_migrator.tidal import TidalDestination


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


class Migrator:
    def __init__(
        self,
        spotify: SpotifySource,
        tidal: TidalDestination,
        cache: MatchCache,
        *,
        dry_run: bool,
    ):
        self._spotify = spotify
        self._tidal = tidal
        self._cache = cache
        self._dry_run = dry_run

    def migrate(self, playlist_ids: list[str] | None, include_saved: bool) -> MigrationReport:
        source_playlists = (
            [self._spotify.playlist(item) for item in playlist_ids]
            if playlist_ids
            else list(self._spotify.playlists())
        )
        destinations = self._tidal.playlists_by_name()
        report = MigrationReport()
        for playlist in source_playlists:
            tracks = list(self._spotify.playlist_tracks(playlist.source_id))
            matched, unmatched = self._match_tracks(tracks)
            target = destinations.get(playlist.name)
            changed = target is None or self._tidal.playlist_track_ids(target) != matched
            if not self._dry_run and changed:
                if target is None:
                    target = self._tidal.create_playlist(playlist.name, playlist.description)
                    destinations[playlist.name] = target
                self._tidal.sync_playlist(target, matched)
            report.collections.append(
                CollectionReport(playlist.name, len(tracks), len(matched), unmatched, changed)
            )

        if include_saved:
            tracks = list(self._spotify.saved_tracks())
            matched, unmatched = self._match_tracks(tracks)
            changed = bool(matched)
            if not self._dry_run:
                changed = self._tidal.add_favorites(matched) > 0
            report.collections.append(
                CollectionReport("Liked Songs", len(tracks), len(matched), unmatched, changed)
            )
        return report

    def _match_tracks(self, tracks: list[Track]) -> tuple[list[str], list[Track]]:
        matched: list[str] = []
        unmatched: list[Track] = []
        for track in tracks:
            result = self._match_track(track)
            if result.destination_id:
                matched.append(result.destination_id)
            else:
                unmatched.append(track)
        return matched, unmatched

    def _match_track(self, track: Track) -> TrackMatch:
        cached = self._cache.get(track.source_id)
        if cached:
            return TrackMatch(track, cached, 1.0, "cache")
        result = best_match(track, self._tidal.search_tracks(track))
        if result.destination_id:
            self._cache.put(track.source_id, result.destination_id)
        return result
