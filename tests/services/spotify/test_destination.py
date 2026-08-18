from types import SimpleNamespace

import pytest
import requests

from music_migrator.core.models import Track
from music_migrator.services.spotify.auth import SPOTIFY_DESTINATION_SCOPES
from music_migrator.services.spotify.service import SpotifyDestination


def spotify_track(track_id: str, isrc: str = "TEST123") -> dict:
    return {
        "id": track_id,
        "name": "Song",
        "type": "track",
        "artists": [{"name": "Artist"}],
        "album": {"name": "Album"},
        "duration_ms": 181000,
        "external_ids": {"isrc": isrc},
    }


def test_authenticate_requests_destination_scopes(mocker, tmp_path):
    client = mocker.Mock()
    create_client = mocker.patch(
        "music_migrator.services.spotify.service.create_spotify_client",
        return_value=client,
    )
    config = SimpleNamespace()
    session_path = tmp_path / "spotify-session.json"

    destination = SpotifyDestination.authenticate(config, session_path)

    create_client.assert_called_once_with(
        config,
        session_path,
        SPOTIFY_DESTINATION_SCOPES,
    )
    assert destination._client is client


def test_lists_only_writable_playlists_and_creates_private_playlist(mocker):
    client = mocker.Mock()
    client.current_user.return_value = {"id": "me"}
    client.current_user_playlists.return_value = {
        "items": [
            {"id": "owned", "name": "Owned", "owner": {"id": "me"}},
            {
                "id": "collab",
                "name": "Collab",
                "owner": {"id": "other"},
                "collaborative": True,
            },
            {"id": "followed", "name": "Followed", "owner": {"id": "other"}},
        ],
        "next": None,
    }
    destination = SpotifyDestination(client)

    playlists = destination.playlists_by_name()
    destination.create_playlist("New", "Description")

    assert set(playlists) == {"Owned", "Collab"}
    client.current_user_playlist_create.assert_called_once_with(
        "New", public=False, description="Description"
    )


def test_searches_by_isrc_before_text(mocker):
    client = mocker.Mock()
    client.search.return_value = {"tracks": {"items": [spotify_track("track-1")]}}
    source = Track("tidal-1", "Song", ("Artist",), "Album", 181, "TEST123")

    tracks = SpotifyDestination(client).search_tracks(source)

    client.search.assert_called_once_with(q="isrc:TEST123", type="track", limit=10)
    assert tracks[0].source_id == "track-1"
    assert tracks[0].duration_seconds == 181


def test_appends_planned_playlist_tracks(mocker):
    client = mocker.Mock()
    destination = SpotifyDestination(client)

    destination.append_playlist_tracks(
        {"id": "playlist-1"},
        ["second"],
        expected_before=["first"],
    )

    client.playlist_add_items.assert_called_once_with("playlist-1", ["second"])
    client.playlist_replace_items.assert_not_called()


def test_replaces_planned_playlist_contents(mocker):
    client = mocker.Mock()
    destination = SpotifyDestination(client)

    destination.replace_playlist_tracks(
        {"id": "playlist-1"},
        ["new"],
        original_track_ids=["old"],
    )

    client.playlist_replace_items.assert_called_once_with("playlist-1", ["new"])
    client.playlist_add_items.assert_not_called()


def test_loads_spotify_favorite_track_ids(mocker):
    client = mocker.Mock()
    client.current_user_saved_tracks.return_value = {
        "items": [{"item": spotify_track("one")}, {"item": spotify_track("two")}],
        "next": None,
    }

    result = SpotifyDestination(client).favorite_track_ids()

    assert result == {"one", "two"}


def test_adds_only_missing_saved_tracks(mocker):
    client = mocker.Mock()
    client.current_user_saved_tracks_contains.return_value = [True, False, False]

    added = SpotifyDestination(client).add_favorites(["one", "two", "three"])

    assert added == 2
    client.current_user_saved_tracks_add.assert_called_once_with(["two", "three"])


def test_checks_saved_tracks_in_current_api_batches(mocker):
    client = mocker.Mock()
    client.current_user_saved_tracks_contains.side_effect = [
        [True] * 40,
        [False],
    ]

    added = SpotifyDestination(client).add_favorites([str(index) for index in range(41)])

    assert added == 1
    assert client.current_user_saved_tracks_contains.call_count == 2
    client.current_user_saved_tracks_add.assert_called_once_with(["40"])


def test_restores_spotify_playlist_after_interrupted_replacement(mocker):
    client = mocker.Mock()
    client.playlist_add_items.side_effect = RuntimeError("write failed")
    destination = SpotifyDestination(client)
    desired = [str(index) for index in range(101)]

    with pytest.raises(RuntimeError, match="write failed"):
        destination.replace_playlist_tracks(
            {"id": "playlist-1"},
            desired,
            original_track_ids=["old"],
        )

    assert client.playlist_replace_items.call_args_list == [
        mocker.call("playlist-1", desired[:100]),
        mocker.call("playlist-1", ["old"]),
    ]


def test_confirms_append_that_succeeded_before_response_failed(mocker):
    client = mocker.Mock()
    client.playlist_items.return_value = {
        "items": [{"item": spotify_track("one")}, {"item": spotify_track("two")}],
        "next": None,
    }
    client.playlist_add_items.side_effect = requests.Timeout("response lost")
    destination = SpotifyDestination(client)

    destination.append_playlist_tracks(
        {"id": "playlist-1"},
        ["two"],
        expected_before=["one"],
    )

    client.playlist_add_items.assert_called_once_with("playlist-1", ["two"])
