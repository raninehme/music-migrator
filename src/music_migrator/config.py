from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str = "http://127.0.0.1:8888/callback"
    open_browser: bool = True


@dataclass(frozen=True, slots=True)
class MigrationConfig:
    spotify: SpotifyConfig
    include_saved_tracks: bool = True

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

        return cls(
            spotify=SpotifyConfig(
                client_id=str(spotify_raw["client_id"]),
                client_secret=str(spotify_raw["client_secret"]),
                redirect_uri=str(spotify_raw.get("redirect_uri", "http://127.0.0.1:8888/callback")),
                open_browser=bool(spotify_raw.get("open_browser", True)),
            ),
            include_saved_tracks=bool(raw.get("include_saved_tracks", True)),
        )
