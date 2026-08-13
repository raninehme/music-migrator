from dataclasses import dataclass
from typing import Any

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"


@dataclass(frozen=True, slots=True)
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str = DEFAULT_REDIRECT_URI
    open_browser: bool = True

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "SpotifyConfig":
        missing = [key for key in ("client_id", "client_secret") if not raw.get(key)]
        if missing:
            raise ValueError(f"Missing Spotify setting(s): {', '.join(missing)}")
        open_browser = raw.get("open_browser", True)
        if not isinstance(open_browser, bool):
            raise ValueError("open_browser must be true or false")
        return cls(
            client_id=str(raw["client_id"]),
            client_secret=str(raw["client_secret"]),
            redirect_uri=str(raw.get("redirect_uri", DEFAULT_REDIRECT_URI)),
            open_browser=open_browser,
        )
