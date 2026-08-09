import pytest

from music_migrator.profiles import ProfilePaths


def test_named_profile_is_fully_isolated():
    paths = ProfilePaths.for_name("rani")
    root = ".music-migrator/profiles/rani"
    assert paths.spotify_session.as_posix() == f"{root}/spotify-session.json"
    assert paths.tidal_session.as_posix() == f"{root}/tidal-session.json"
    assert paths.match_cache.as_posix() == f"{root}/matches.sqlite3"
    assert paths.log_file.as_posix() == f"{root}/logs/music-migrator.log"
    assert paths.unmatched_report.as_posix() == f"{root}/reports/unmatched.csv"


@pytest.mark.parametrize("name", ["../other", "with space", "", "a/b"])
def test_rejects_unsafe_profile_names(name):
    with pytest.raises(ValueError, match="profile may contain"):
        ProfilePaths.for_name(name)


def test_prepare_creates_log_and_report_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    assert paths.log_file.parent.is_dir()
    assert paths.unmatched_report.parent.is_dir()


def test_reset_auth_removes_only_session_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("girlfriend")
    paths.prepare()
    paths.spotify_session.write_text("spotify")
    paths.tidal_session.write_text("tidal")
    paths.match_cache.write_text("cache")

    assert paths.reset_auth() == 2
    assert not paths.spotify_session.exists()
    assert not paths.tidal_session.exists()
    assert paths.match_cache.exists()
