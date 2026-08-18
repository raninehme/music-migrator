"""Resolve and validate source-to-destination migration routes."""

from dataclasses import dataclass

from music_migrator.services.registry import Service, get_service


@dataclass(frozen=True, slots=True)
class MigrationRoute:
    """A validated source-to-destination service route."""

    source: Service
    destination: Service

    @property
    def key(self) -> str:
        return f"{self.source.name}-to-{self.destination.name}"


def plan_route(source_name: str, destination_name: str) -> MigrationRoute:
    """Resolve and validate a migration route."""
    source = get_service(source_name)
    destination = get_service(destination_name)

    if source.name == destination.name:
        raise ValueError("source and destination services must be different")
    if source.source is None or source.authenticate_source is None:
        raise ValueError(f"{source.name} cannot be used as a source")
    if destination.destination is None or destination.authenticate_destination is None:
        raise ValueError(f"{destination.name} cannot be used as a destination")
    return MigrationRoute(source=source, destination=destination)
