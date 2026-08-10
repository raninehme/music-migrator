import pytest

from music_migrator.cli import build_parser


def test_profile_or_setup_is_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_profile_is_parsed():
    args = build_parser().parse_args(["--profile", "rani", "--dry-run"])
    assert args.profile == "rani"
    assert args.dry_run is True
    assert args.refresh_matches is False


def test_reverse_route_is_parsed():
    args = build_parser().parse_args(
        ["--profile", "rani", "--from", "tidal", "--to", "spotify", "--dry-run"]
    )
    assert args.source_service == "tidal"
    assert args.destination_service == "spotify"


def test_setup_profile_is_parsed():
    assert build_parser().parse_args(["--setup", "rani"]).setup == "rani"


def test_refresh_matches_is_parsed():
    args = build_parser().parse_args(["--profile", "rani", "--dry-run", "--refresh-matches"])

    assert args.refresh_matches is True
