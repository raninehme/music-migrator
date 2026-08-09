import pytest

from music_migrator.cli import build_parser


def test_profile_is_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_profile_is_parsed():
    assert build_parser().parse_args(["--profile", "rani"]).profile == "rani"
