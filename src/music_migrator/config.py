import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"


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
    max_concurrency: int | None = None
    rate_limit: int | None = None

    @classmethod
    def load(cls, path: Path) -> "MigrationConfig":
        with path.open(encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file) or {}
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a mapping")
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "MigrationConfig":
        services_raw = raw.get("services", {})
        if not isinstance(services_raw, dict):
            raise ValueError("services must be a mapping")

        services = dict(services_raw)
        if "spotify" not in services and "spotify" in raw:
            services["spotify"] = raw["spotify"]

        service_requests: dict[str, RequestSettings] = {}
        for service_name, service_raw in services.items():
            if not isinstance(service_raw, dict):
                raise ValueError(f"services.{service_name} must be a mapping")
            requests_raw = service_raw.get("requests")
            if requests_raw is None:
                continue
            if not isinstance(requests_raw, dict):
                raise ValueError(f"services.{service_name}.requests must be a mapping")
            service_requests[service_name] = RequestSettings(
                max_concurrency=_positive_integer(requests_raw, "max_concurrency"),
                rate_limit=_positive_integer(requests_raw, "rate_limit"),
            )

        max_concurrency = (
            _positive_integer(raw, "max_concurrency") if "max_concurrency" in raw else None
        )
        rate_limit = _positive_integer(raw, "rate_limit") if "rate_limit" in raw else None
        if (max_concurrency is None) != (rate_limit is None):
            raise ValueError("max_concurrency and rate_limit must be configured together")

        return cls(
            services=services,
            include_saved_tracks=_boolean(raw, "include_saved_tracks", True),
            service_requests=service_requests,
            max_concurrency=max_concurrency,
            rate_limit=rate_limit,
        )

    def service(self, service_name: str) -> dict[str, Any] | None:
        return self.services.get(service_name)

    def requests_for(self, service_name: str, defaults: RequestSettings) -> RequestSettings:
        override = self.service_requests.get(service_name)
        if override is not None:
            return override
        if self.max_concurrency is not None and self.rate_limit is not None:
            return RequestSettings(self.max_concurrency, self.rate_limit)
        return defaults


def render_profile_config(
    client_id: str,
    client_secret: str,
    request_defaults: Mapping[str, RequestSettings],
) -> str:
    """Render a discoverable profile without requiring optional request settings."""
    spotify_requests = request_defaults["spotify"]
    lines = [
        "services:",
        "  spotify:",
        f"    client_id: {json.dumps(client_id)}",
        f"    client_secret: {json.dumps(client_secret)}",
        f"    redirect_uri: {DEFAULT_REDIRECT_URI}",
        "    open_browser: true",
        "",
        "    # Optional request limits. Uncomment only to override the safe defaults.",
        "    # requests:",
        f"    #   max_concurrency: {spotify_requests.max_concurrency}",
        f"    #   rate_limit: {spotify_requests.rate_limit}",
    ]

    for service_name in sorted(request_defaults):
        if service_name == "spotify":
            continue
        defaults = request_defaults[service_name]
        lines.extend(
            [
                "",
                f"  # {service_name}:",
                "  #   requests:",
                f"  #     max_concurrency: {defaults.max_concurrency}",
                f"  #     rate_limit: {defaults.rate_limit}",
            ]
        )

    lines.extend(["", "include_saved_tracks: true", ""])
    return "\n".join(lines)
