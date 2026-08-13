from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
import requests

from music_migrator.services.tidal.service import TidalDestination


def test_playlist_sync_appends_when_existing_is_prefix():
    playlist = Mock()
    playlist.tracks_paginated.return_value = [SimpleNamespace(id="1")]
    destination = TidalDestination(Mock())

    assert destination.sync_playlist(playlist, ["1", "2"]) is True
    playlist.add.assert_called_once_with(["2"])
    playlist.clear.assert_not_called()


def test_playlist_sync_replaces_different_contents():
    playlist = Mock()
    playlist.tracks_paginated.return_value = [SimpleNamespace(id="old")]
    destination = TidalDestination(Mock())

    destination.sync_playlist(playlist, ["new"])
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
    playlist.tracks_paginated.return_value = [SimpleNamespace(id="old")]
    playlist.add.side_effect = [RuntimeError("write failed"), None]
    destination = TidalDestination(Mock())

    with pytest.raises(RuntimeError, match="write failed"):
        destination.sync_playlist(playlist, ["new"])

    assert playlist.clear.call_count == 2
    assert playlist.add.call_args_list == [call(["new"]), call(["old"])]
