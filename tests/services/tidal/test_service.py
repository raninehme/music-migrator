from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
import requests

from music_migrator.services.tidal.service import TidalDestination


def test_appends_planned_playlist_tracks():
    playlist = Mock()
    destination = TidalDestination(Mock())

    destination.append_playlist_tracks(playlist, ["2"], expected_before=["1"])

    playlist.add.assert_called_once_with(["2"])
    playlist.clear.assert_not_called()


def test_replaces_planned_playlist_contents():
    playlist = Mock()
    destination = TidalDestination(Mock())

    destination.replace_playlist_tracks(playlist, ["new"], original_track_ids=["old"])

    playlist.clear.assert_called_once_with()
    playlist.add.assert_called_once_with(["new"])


def test_precondition_failure_refreshes_and_retries():
    response = SimpleNamespace(status_code=412)
    operation = Mock(side_effect=[requests.HTTPError(response=response), None])
    playlist = Mock()

    TidalDestination._retry_precondition(playlist, operation)
    assert operation.call_count == 2
    playlist._reparse.assert_called_once_with()


def test_loads_tidal_favorite_track_ids():
    session = Mock()
    session.user.favorites.tracks.return_value = [
        SimpleNamespace(id="one"),
        SimpleNamespace(id="two"),
    ]

    result = TidalDestination(session).favorite_track_ids()

    assert result == {"one", "two"}


def test_restores_tidal_playlist_after_interrupted_replacement():
    playlist = Mock()
    playlist.tracks.return_value = []
    playlist.add.side_effect = [RuntimeError("write failed"), None]
    destination = TidalDestination(Mock())

    with pytest.raises(RuntimeError, match="write failed"):
        destination.replace_playlist_tracks(
            playlist,
            ["new"],
            original_track_ids=["old"],
        )

    assert playlist.clear.call_count == 2
    assert playlist.add.call_args_list == [call(["new"]), call(["old"])]


def test_confirms_append_that_succeeded_before_response_failed():
    playlist = Mock()
    playlist.tracks.return_value = [SimpleNamespace(id="one"), SimpleNamespace(id="two")]
    playlist.add.side_effect = requests.Timeout("response lost")
    destination = TidalDestination(Mock())

    destination.append_playlist_tracks(playlist, ["two"], expected_before=["one"])

    playlist.add.assert_called_once_with(["two"])
