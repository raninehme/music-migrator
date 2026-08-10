from music_migrator.services.spotify.service import SpotifySource


def spotify_track(track_id="track-1", name="Song"):
    return {
        "id": track_id,
        "name": name,
        "type": "track",
        "artists": [{"name": "Artist"}],
        "album": {"name": "Album"},
        "duration_ms": 181500,
        "external_ids": {"isrc": "TEST123"},
    }


def test_lists_owned_and_collaborative_playlists_only(mocker):
    client = mocker.Mock()
    client.current_user.return_value = {"id": "me"}
    client.current_user_playlists.return_value = {
        "items": [
            {
                "id": "owned",
                "name": "Owned",
                "owner": {"id": "me"},
                "description": None,
                "collaborative": False,
            },
            {
                "id": "collab",
                "name": "Collab",
                "owner": {"id": "someone"},
                "collaborative": True,
            },
            {
                "id": "followed",
                "name": "Followed",
                "owner": {"id": "someone"},
                "collaborative": False,
            },
        ],
        "next": None,
        "limit": 50,
    }

    playlists = list(SpotifySource(client).playlists())

    assert [playlist.source_id for playlist in playlists] == ["owned", "collab"]
    assert playlists[0].description == ""


def test_paginates_playlist_tracks_and_supports_current_payload(mocker):
    client = mocker.Mock()
    client.playlist_items.side_effect = [
        {
            "items": [{"item": spotify_track("first")}],
            "next": "next-page",
            "limit": 1,
        },
        {
            "items": [{"item": spotify_track("second")}],
            "next": None,
            "limit": 1,
        },
    ]

    tracks = list(SpotifySource(client).playlist_tracks("playlist"))

    assert [track.source_id for track in tracks] == ["first", "second"]
    assert tracks[0].duration_seconds == 181.5
    assert client.playlist_items.call_args_list[1].kwargs["offset"] == 1


def test_reads_legacy_saved_track_payload_and_skips_invalid_entries(mocker):
    client = mocker.Mock()
    client.current_user_saved_tracks.return_value = {
        "items": [
            {"track": spotify_track()},
            {"track": None},
            {"track": {**spotify_track("episode"), "type": "episode"}},
            {"track": {**spotify_track("missing-artist"), "artists": []}},
        ],
        "next": None,
        "limit": 50,
    }

    tracks = list(SpotifySource(client).saved_tracks())

    assert len(tracks) == 1
    assert tracks[0].artists == ("Artist",)
    assert tracks[0].album == "Album"
    assert tracks[0].isrc == "TEST123"


def test_current_user_profile_is_cached(mocker):
    client = mocker.Mock()
    client.current_user.return_value = {"id": "me"}
    client.current_user_playlists.return_value = {
        "items": [],
        "next": None,
        "limit": 50,
    }
    source = SpotifySource(client)

    list(source.playlists())
    list(source.playlists())

    client.current_user.assert_called_once_with()
