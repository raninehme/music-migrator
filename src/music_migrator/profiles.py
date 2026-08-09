import re
from dataclasses import dataclass
from pathlib import Path

PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class ProfilePaths:
    spotify_session: Path
    tidal_session: Path
    match_cache: Path
    unmatched_report: Path

    @classmethod
    def for_name(cls, name: str) -> "ProfilePaths":
        if not PROFILE_PATTERN.fullmatch(name):
            raise ValueError("profile may contain only letters, numbers, hyphens, and underscores")
        if name == "default":
            return cls(
                Path(".spotify-session.json"),
                Path(".tidal-session.json"),
                Path(".music-migrator-cache.sqlite3"),
                Path("unmatched.csv"),
            )
        root = Path(".music-migrator") / "profiles" / name
        return cls(
            root / "spotify-session.json",
            root / "tidal-session.json",
            root / "matches.sqlite3",
            root / "unmatched.csv",
        )

    def prepare(self) -> None:
        self.spotify_session.parent.mkdir(parents=True, exist_ok=True)

    def reset_auth(self) -> int:
        removed = 0
        for path in (self.spotify_session, self.tidal_session):
            if path.exists():
                path.unlink()
                removed += 1
        return removed
