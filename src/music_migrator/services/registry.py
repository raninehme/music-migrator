from dataclasses import dataclass

from music_migrator.services.base import MusicDestination, MusicSource
from music_migrator.services.spotify.service import SpotifySource
from music_migrator.services.tidal.service import TidalDestination


@dataclass(frozen=True, slots=True)
class Service:
    """Available capabilities for a music service."""

    name: str
    source: type[MusicSource] | None = None
    destination: type[MusicDestination] | None = None


SERVICES = {
    "spotify": Service(name="spotify", source=SpotifySource),
    "tidal": Service(name="tidal", destination=TidalDestination),
}


def get_service(name: str) -> Service:
    """Return a configured service by its case-insensitive name."""
    try:
        return SERVICES[name.casefold()]
    except KeyError as error:
        supported = ", ".join(sorted(SERVICES))
        raise ValueError(f"Unknown service '{name}'. Available services: {supported}") from error
