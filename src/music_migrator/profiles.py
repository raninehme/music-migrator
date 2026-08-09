import re
from dataclasses import dataclass
from pathlib import Path

PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class ProfilePaths:
    root: Path
    config: Path
    spotify_session: Path
    tidal_session: Path
    match_cache: Path
    log_file: Path
    unmatched_report: Path

    @classmethod
    def for_name(cls, name: str) -> "ProfilePaths":
        if not PROFILE_PATTERN.fullmatch(name):
            raise ValueError("profile may contain only letters, numbers, hyphens, and underscores")
        root = Path(".music-migrator") / "profiles" / name
        return cls(
            root=root,
            config=root / "config.yml",
            spotify_session=root / "spotify-session.json",
            tidal_session=root / "tidal-session.json",
            match_cache=root / "matches.sqlite3",
            log_file=root / "logs" / "music-migrator.log",
            unmatched_report=root / "reports" / "unmatched.csv",
        )

    def prepare(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.unmatched_report.parent.mkdir(parents=True, exist_ok=True)

    def reset_auth(self) -> int:
        removed = 0
        for path in (self.spotify_session, self.tidal_session):
            if path.exists():
                path.unlink()
                removed += 1
        return removed
