import re
from dataclasses import dataclass
from pathlib import Path

PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
ROUTE_PATTERN = re.compile(r"^[a-z0-9-]+-to-[a-z0-9-]+$")


@dataclass(frozen=True, slots=True)
class MigrationPaths:
    match_cache: Path
    unmatched_report: Path


@dataclass(frozen=True, slots=True)
class ProfilePaths:
    root: Path
    config: Path
    spotify_session: Path
    tidal_session: Path
    cache_dir: Path
    log_file: Path
    reports_dir: Path

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
            cache_dir=root / "cache",
            log_file=root / "logs" / "music-migrator.log",
            reports_dir=root / "reports",
        )

    def prepare(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def for_route(self, route_key: str) -> MigrationPaths:
        if not ROUTE_PATTERN.fullmatch(route_key):
            raise ValueError(f"invalid migration route key: {route_key}")
        return MigrationPaths(
            match_cache=self.cache_dir / f"{route_key}.sqlite3",
            unmatched_report=self.reports_dir / route_key / "unmatched.csv",
        )

    def session_for(self, service_name: str) -> Path:
        sessions = {
            "spotify": self.spotify_session,
            "tidal": self.tidal_session,
        }
        try:
            return sessions[service_name]
        except KeyError as error:
            raise ValueError(f"unknown session service: {service_name}") from error

    def reset_auth(self) -> int:
        removed = 0
        for path in (self.spotify_session, self.tidal_session):
            if path.exists():
                path.unlink()
                removed += 1
        return removed
