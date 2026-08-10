from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
DEFAULT_MAX_CONCURRENCY = 10
DEFAULT_RATE_LIMIT = 10


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

        max_concurrency = int(raw.get("max_concurrency", DEFAULT_MAX_CONCURRENCY))
        rate_limit = int(raw.get("rate_limit", DEFAULT_RATE_LIMIT))
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if rate_limit < 1:
            raise ValueError("rate_limit must be at least 1")

        return cls(
            spotify=SpotifyConfig(
                client_id=str(spotify_raw["client_id"]),
                client_secret=str(spotify_raw["client_secret"]),
                redirect_uri=str(spotify_raw.get("redirect_uri", DEFAULT_REDIRECT_URI)),
                open_browser=bool(spotify_raw.get("open_browser", True)),
            ),
            include_saved_tracks=bool(raw.get("include_saved_tracks", True)),
            max_concurrency=max_concurrency,
            rate_limit=rate_limit,
        )
