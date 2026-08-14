import pytest
import requests

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


def test_create_tidal_session_reauthenticates_after_unauthorized(mocker, tmp_path):
    expired = mocker.Mock()
    fresh = mocker.Mock()
    response = requests.Response()
    response.status_code = 401
    expired.login_session_file.side_effect = requests.HTTPError(response=response)
    fresh.login_session_file.return_value = True
    session_type = mocker.patch(
        "music_migrator.services.tidal.auth.tidalapi.Session",
        side_effect=[expired, fresh],
    )
    session_path = tmp_path / "tidal-session.json"
    session_path.write_text("expired")

    result = create_tidal_session(session_path)

    assert result is fresh
    assert not session_path.exists()
    assert session_type.call_count == 2
    expired.login_session_file.assert_called_once_with(session_path)
    fresh.login_session_file.assert_called_once_with(session_path)
