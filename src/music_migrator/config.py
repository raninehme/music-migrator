from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _boolean(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value


def _positive_integer(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value < 1:
        raise ValueError(f"{key} must be at least 1")
    return value


@dataclass(frozen=True, slots=True)
class RequestSettings:
    max_concurrency: int
    rate_limit: int


@dataclass(frozen=True, slots=True)
class MigrationConfig:
    services: dict[str, dict[str, Any]] = field(default_factory=dict)
    include_saved_tracks: bool = True
    service_requests: dict[str, RequestSettings] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "MigrationConfig":
        with path.open(encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file) or {}
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a mapping")
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "MigrationConfig":
        unknown = set(raw) - {"services", "include_saved_tracks"}
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Unknown top-level configuration setting(s): {names}")

        services_raw = raw.get("services", {})
        if not isinstance(services_raw, dict):
            raise ValueError("services must be a mapping")

        services: dict[str, dict[str, Any]] = {}
        service_requests: dict[str, RequestSettings] = {}
        for service_name, service_raw in services_raw.items():
            if service_raw is None:
                service_raw = {}
            if not isinstance(service_raw, dict):
                raise ValueError(f"services.{service_name} must be a mapping")
            services[service_name] = service_raw
            requests_raw = service_raw.get("requests")
            if requests_raw is None:
                continue
            if not isinstance(requests_raw, dict):
                raise ValueError(f"services.{service_name}.requests must be a mapping")
            service_requests[service_name] = RequestSettings(
                max_concurrency=_positive_integer(requests_raw, "max_concurrency"),
                rate_limit=_positive_integer(requests_raw, "rate_limit"),
            )

        return cls(
            services=services,
            include_saved_tracks=_boolean(raw, "include_saved_tracks", True),
            service_requests=service_requests,
        )

    def service(self, service_name: str) -> dict[str, Any] | None:
        return self.services.get(service_name)

    def requests_for(self, service_name: str, defaults: RequestSettings) -> RequestSettings:
        return self.service_requests.get(service_name, defaults)


def render_profile_config(service_sections: Iterable[str]) -> str:
    """Assemble provider-owned profile sections into one configuration file."""
    return "services:\n" + "".join(service_sections) + "\ninclude_saved_tracks: true\n"
