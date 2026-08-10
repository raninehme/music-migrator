import pytest

from music_migrator.profiles import ProfilePaths


def test_named_profile_is_fully_isolated():
    paths = ProfilePaths.for_name("rani")
    root = ".music-migrator/profiles/rani"
    assert paths.config.as_posix() == f"{root}/config.yml"
    assert paths.spotify_session.as_posix() == f"{root}/spotify-session.json"
    assert paths.tidal_session.as_posix() == f"{root}/tidal-session.json"
    assert paths.cache_dir.as_posix() == f"{root}/cache"
    assert paths.log_file.as_posix() == f"{root}/logs/music-migrator.log"
    assert paths.reports_dir.as_posix() == f"{root}/reports"


def test_route_data_is_isolated_by_direction():
    paths = ProfilePaths.for_name("rani")

    forward = paths.for_route("spotify-to-tidal")
    reverse = paths.for_route("tidal-to-spotify")

    assert forward.match_cache != reverse.match_cache
    assert forward.unmatched_report != reverse.unmatched_report
    assert forward.match_cache.as_posix().endswith("cache/spotify-to-tidal.sqlite3")
    assert reverse.unmatched_report.as_posix().endswith("reports/tidal-to-spotify/unmatched.csv")


@pytest.mark.parametrize("name", ["../other", "with space", "", "a/b"])
def test_rejects_unsafe_profile_names(name):
    with pytest.raises(ValueError, match="profile may contain"):
        ProfilePaths.for_name(name)


def test_prepare_creates_profile_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()

    assert paths.cache_dir.is_dir()
    assert paths.log_file.parent.is_dir()
    assert paths.reports_dir.is_dir()


def test_reset_auth_removes_only_session_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("girlfriend")
    paths.prepare()
    route_paths = paths.for_route("spotify-to-tidal")
    paths.spotify_session.write_text("spotify")
    paths.tidal_session.write_text("tidal")
    route_paths.match_cache.write_text("cache")

    assert paths.reset_auth() == 2
    assert not paths.spotify_session.exists()
    assert not paths.tidal_session.exists()
    assert route_paths.match_cache.exists()
