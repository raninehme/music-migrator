import getpass
import json
from dataclasses import dataclass
from typing import Any

from music_migrator.config import RequestSettings

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


def setup_profile(requests: RequestSettings) -> str:
    client_id = input("Spotify client ID: ").strip()
    client_secret = getpass.getpass("Spotify client secret: ").strip()
    if not client_id or not client_secret:
        raise ValueError("Spotify client ID and client secret are required")

    return f"""  spotify:
    client_id: {json.dumps(client_id)}
    client_secret: {json.dumps(client_secret)}
    redirect_uri: {DEFAULT_REDIRECT_URI}
    open_browser: true

    # Optional request limits. Uncomment only to override the safe defaults.
    # requests:
    #   max_concurrency: {requests.max_concurrency}
    #   rate_limit: {requests.rate_limit}
"""
