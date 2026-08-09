import pytest

from music_migrator.profiles import ProfilePaths


def test_default_profile_preserves_existing_paths():
    paths = ProfilePaths.for_name("default")
    assert paths.spotify_session.name == ".spotify-session.json"
    assert paths.match_cache.name == ".music-migrator-cache.sqlite3"


def test_named_profile_is_isolated():
    paths = ProfilePaths.for_name("girlfriend")
    assert paths.spotify_session.as_posix() == (
        ".music-migrator/profiles/girlfriend/spotify-session.json"
    )
    assert paths.unmatched_report.parent == paths.spotify_session.parent


@pytest.mark.parametrize("name", ["../other", "with space", "", "a/b"])
def test_rejects_unsafe_profile_names(name):
    with pytest.raises(ValueError, match="profile may contain"):
        ProfilePaths.for_name(name)


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
