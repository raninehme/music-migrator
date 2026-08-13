from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
DEFAULT_MAX_CONCURRENCY = 10
DEFAULT_RATE_LIMIT = 10


def _boolean(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value


def _positive_integer(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value < 1:
        raise ValueError(f"{key} must be at least 1")
    return value


@dataclass(frozen=True, slots=True)
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str = DEFAULT_REDIRECT_URI
    open_browser: bool = True


@dataclass(frozen=True, slots=True)
class MigrationConfig:
    spotify: SpotifyConfig
    include_saved_tracks: bool = True
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    rate_limit: int = DEFAULT_RATE_LIMIT

    @classmethod
    def load(cls, path: Path) -> "MigrationConfig":
        with path.open(encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file) or {}
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a mapping")
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "MigrationConfig":
        spotify_raw = raw.get("spotify")
        if not isinstance(spotify_raw, dict):
            raise ValueError("Missing 'spotify' configuration")

        required = ("client_id", "client_secret")
        missing = [key for key in required if not spotify_raw.get(key)]
        if missing:
            raise ValueError(f"Missing Spotify setting(s): {', '.join(missing)}")

        max_concurrency = _positive_integer(raw, "max_concurrency", DEFAULT_MAX_CONCURRENCY)
        rate_limit = _positive_integer(raw, "rate_limit", DEFAULT_RATE_LIMIT)

        return cls(
            spotify=SpotifyConfig(
                client_id=str(spotify_raw["client_id"]),
                client_secret=str(spotify_raw["client_secret"]),
                redirect_uri=str(spotify_raw.get("redirect_uri", DEFAULT_REDIRECT_URI)),
                open_browser=_boolean(spotify_raw, "open_browser", True),
            ),
            include_saved_tracks=_boolean(raw, "include_saved_tracks", True),
            max_concurrency=max_concurrency,
            rate_limit=rate_limit,
        )
