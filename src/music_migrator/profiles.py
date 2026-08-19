import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
SERVICE_PATTERN = re.compile(r"^[a-z0-9-]+$")
ROUTE_PATTERN = re.compile(r"^[a-z0-9-]+-to-[a-z0-9-]+$")


@dataclass(frozen=True, slots=True)
class MigrationPaths:
    match_cache: Path
    migration_state: Path
    unmatched_report: Path


@dataclass(frozen=True, slots=True)
class ProfilePaths:
    root: Path
    config: Path
    sessions_dir: Path
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
            sessions_dir=root / "sessions",
            cache_dir=root / "cache",
            log_file=root / "logs" / "music-migrator.log",
            reports_dir=root / "reports",
        )

    @property
    def spotify_session(self) -> Path:
        """Return the Spotify session path for backward compatibility."""
        return self.session_for("spotify")

    @property
    def tidal_session(self) -> Path:
        """Return the TIDAL session path for backward compatibility."""
        return self.session_for("tidal")

    def prepare(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def for_route(self, route_key: str) -> MigrationPaths:
        if not ROUTE_PATTERN.fullmatch(route_key):
            raise ValueError(f"invalid migration route key: {route_key}")
        return MigrationPaths(
            match_cache=self.cache_dir / f"{route_key}.sqlite3",
            migration_state=self.cache_dir / f"{route_key}-migration.sqlite3",
            unmatched_report=self.reports_dir / route_key / "unmatched.csv",
        )

    def session_for(self, service_name: str) -> Path:
        if not SERVICE_PATTERN.fullmatch(service_name):
            raise ValueError(f"invalid session service: {service_name}")
        legacy = self.root / f"{service_name}-session.json"
        return legacy if legacy.exists() else self.sessions_dir / f"{service_name}.json"

    def reset_auth(self, service_names: Iterable[str]) -> int:
        candidates: set[Path] = set()
        for service_name in service_names:
            if not SERVICE_PATTERN.fullmatch(service_name):
                raise ValueError(f"invalid session service: {service_name}")
            candidates.add(self.root / f"{service_name}-session.json")
            candidates.add(self.sessions_dir / f"{service_name}.json")
        removed = 0
        for path in candidates:
            if path.exists():
                path.unlink()
                removed += 1
        return removed
