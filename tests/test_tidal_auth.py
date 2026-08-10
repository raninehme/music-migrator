import pytest

from music_migrator.services.tidal.auth import create_tidal_session


def test_create_tidal_session_uses_profile_session_file(mocker, tmp_path):
    session = mocker.Mock()
    session_type = mocker.patch("music_migrator.services.tidal.auth.tidalapi.Session")
    session_type.return_value = session
    session_path = tmp_path / "tidal-session.json"

    result = create_tidal_session(session_path)

    session_type.assert_called_once_with()
    session.login_session_file.assert_called_once_with(session_path)
    assert result is session


def test_create_tidal_session_rejects_failed_login(mocker, tmp_path):
    session = mocker.Mock()
    mocker.patch("music_migrator.services.tidal.auth.tidalapi.Session", return_value=session)
    session.login_session_file.return_value = False

    with pytest.raises(RuntimeError, match="TIDAL authentication failed"):
        create_tidal_session(tmp_path / "tidal-session.json")
