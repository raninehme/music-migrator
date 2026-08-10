from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from music_migrator.config import MigrationConfig
from music_migrator.services.base import MusicDestination, MusicSource
from music_migrator.services.spotify.service import SpotifyDestination, SpotifySource
from music_migrator.services.tidal.service import TidalDestination, TidalSource

SourceAuthenticator = Callable[[MigrationConfig, Path], MusicSource]
DestinationAuthenticator = Callable[[MigrationConfig, Path], MusicDestination]


@dataclass(frozen=True, slots=True)
class Service:
    """Available capabilities for a music service."""

    name: str
    source: type[MusicSource] | None = None
    destination: type[MusicDestination] | None = None
    authenticate_source: SourceAuthenticator | None = None
    authenticate_destination: DestinationAuthenticator | None = None


def _spotify_source(config: MigrationConfig, session_path: Path) -> MusicSource:
    return SpotifySource.authenticate(config.spotify, session_path)


def _spotify_destination(config: MigrationConfig, session_path: Path) -> MusicDestination:
    return SpotifyDestination.authenticate(config.spotify, session_path)


def _tidal_source(_config: MigrationConfig, session_path: Path) -> MusicSource:
    return TidalSource.authenticate(session_path)


def _tidal_destination(_config: MigrationConfig, session_path: Path) -> MusicDestination:
    return TidalDestination.authenticate(session_path)


SERVICES = {
    "spotify": Service(
        name="spotify",
        source=SpotifySource,
        destination=SpotifyDestination,
        authenticate_source=_spotify_source,
        authenticate_destination=_spotify_destination,
    ),
    "tidal": Service(
        name="tidal",
        source=TidalSource,
        destination=TidalDestination,
        authenticate_source=_tidal_source,
        authenticate_destination=_tidal_destination,
    ),
}


def get_service(name: str) -> Service:
    """Return a configured service by its case-insensitive name."""
    try:
        return SERVICES[name.casefold()]
    except KeyError as error:
        supported = ", ".join(sorted(SERVICES))
        raise ValueError(f"Unknown service '{name}'. Available services: {supported}") from error
