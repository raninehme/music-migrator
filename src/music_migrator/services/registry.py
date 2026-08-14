from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from music_migrator.config import MigrationConfig, RequestSettings
from music_migrator.services.base import MusicDestination, MusicSource
from music_migrator.services.spotify.config import SpotifyConfig
from music_migrator.services.spotify.config import setup_profile as setup_spotify_profile
from music_migrator.services.spotify.service import (
    SPOTIFY_DEFAULT_REQUEST_SETTINGS,
    SpotifyDestination,
    SpotifySource,
)
from music_migrator.services.tidal.config import setup_profile as setup_tidal_profile
from music_migrator.services.tidal.service import (
    TIDAL_DEFAULT_REQUEST_SETTINGS,
    TidalDestination,
    TidalSource,
)

SourceAuthenticator = Callable[[MigrationConfig, Path], MusicSource]
DestinationAuthenticator = Callable[[MigrationConfig, Path], MusicDestination]
ConfigValidator = Callable[[MigrationConfig], None]
ProfileSetup = Callable[[RequestSettings], str]


@dataclass(frozen=True, slots=True)
class Service:
    """Available capabilities and defaults for a music service."""

    name: str
    request_defaults: RequestSettings
    source: type[MusicSource] | None = None
    destination: type[MusicDestination] | None = None
    authenticate_source: SourceAuthenticator | None = None
    authenticate_destination: DestinationAuthenticator | None = None
    validate_config: ConfigValidator | None = None
    profile_setup: ProfileSetup | None = None


def _spotify_config(config: MigrationConfig) -> SpotifyConfig:
    raw = config.service("spotify")
    if raw is None:
        raise ValueError("Missing Spotify configuration for the selected route")
    return SpotifyConfig.from_mapping(raw)


def _validate_spotify(config: MigrationConfig) -> None:
    _spotify_config(config)


def _spotify_source(config: MigrationConfig, session_path: Path) -> MusicSource:
    return SpotifySource.authenticate(_spotify_config(config), session_path)


def _spotify_destination(config: MigrationConfig, session_path: Path) -> MusicDestination:
    return SpotifyDestination.authenticate(_spotify_config(config), session_path)


def _tidal_source(_config: MigrationConfig, session_path: Path) -> MusicSource:
    return TidalSource.authenticate(session_path)


def _tidal_destination(_config: MigrationConfig, session_path: Path) -> MusicDestination:
    return TidalDestination.authenticate(session_path)


SERVICES = {
    "spotify": Service(
        name="spotify",
        request_defaults=SPOTIFY_DEFAULT_REQUEST_SETTINGS,
        source=SpotifySource,
        destination=SpotifyDestination,
        authenticate_source=_spotify_source,
        authenticate_destination=_spotify_destination,
        validate_config=_validate_spotify,
        profile_setup=setup_spotify_profile,
    ),
    "tidal": Service(
        name="tidal",
        request_defaults=TIDAL_DEFAULT_REQUEST_SETTINGS,
        source=TidalSource,
        destination=TidalDestination,
        authenticate_source=_tidal_source,
        authenticate_destination=_tidal_destination,
        profile_setup=setup_tidal_profile,
    ),
}


def get_service(name: str) -> Service:
    """Return a configured service by its case-insensitive name."""
    try:
        return SERVICES[name.casefold()]
    except KeyError as error:
        supported = ", ".join(sorted(SERVICES))
        raise ValueError(f"Unknown service '{name}'. Available services: {supported}") from error
