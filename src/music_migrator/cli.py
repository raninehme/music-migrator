import argparse
import csv
import sys
from pathlib import Path

from music_migrator import __version__
from music_migrator.cache import MatchCache
from music_migrator.config import MigrationConfig
from music_migrator.migration import MigrationReport, Migrator
from music_migrator.spotify import SpotifySource
from music_migrator.tidal import TidalDestination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate Spotify music to TIDAL")
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--playlist", action="append", default=[], metavar="SPOTIFY_ID")
    parser.add_argument("--no-saved-tracks", action="store_true")
    parser.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = MigrationConfig.load(args.config)
        spotify = SpotifySource.authenticate(config.spotify)
        tidal = TidalDestination.authenticate()
        with MatchCache(Path(".music-migrator-cache.sqlite3")) as cache:
            report = Migrator(
                spotify,
                tidal,
                cache,
                dry_run=not args.apply,
                max_concurrency=config.max_concurrency,
                rate_limit=config.rate_limit,
                progress=_show_progress,
            ).migrate(
                args.playlist or None,
                config.include_saved_tracks and not args.no_saved_tracks,
            )
        _print_report(report, dry_run=not args.apply)
        _write_unmatched(report, Path("unmatched.csv"))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _show_progress(label: str, current: int | None, total: int | None) -> None:
    if current is None or total is None:
        print(label, flush=True)
        return
    end = "\n" if current >= total else "\r"
    print(f"{label}: {current}/{total}", end=end, flush=True)


def _print_report(report: MigrationReport, *, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n{mode}")
    for item in report.collections:
        action = "change" if item.changed else "unchanged"
        print(
            f"{item.name}: {item.matched_tracks}/{item.source_tracks} matched, "
            f"{len(item.unmatched)} unmatched, {action}"
        )
    print(f"Total: {report.matched} matched, {len(report.unmatched)} unmatched")


def _write_unmatched(report: MigrationReport, path: Path) -> None:
    if not report.unmatched:
        path.unlink(missing_ok=True)
        return
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("spotify_id", "title", "artists", "album", "isrc"))
        for track in report.unmatched:
            writer.writerow(
                (track.source_id, track.title, "; ".join(track.artists), track.album, track.isrc)
            )
    print(f"Unmatched tracks written to {path}")


if __name__ == "__main__":
    raise SystemExit(main())
