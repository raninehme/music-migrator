from types import SimpleNamespace

from music_migrator.services.tidal.service import TidalSource


def tidal_track(track_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=track_id,
        name="Song",
        artists=[SimpleNamespace(name="Artist")],
        album=SimpleNamespace(name="Album"),
        duration=181,
        isrc="TEST123",
    )


def test_lists_and_loads_tidal_playlists():
    session = SimpleNamespace(
        user=SimpleNamespace(
            playlists=lambda: [SimpleNamespace(id="playlist-1", name="Mix", description=None)]
        )
    )
    source = TidalSource(session)

    playlists = list(source.playlists())

    assert playlists[0].source_id == "playlist-1"
    assert playlists[0].name == "Mix"
    assert playlists[0].description == ""


def test_loads_tidal_playlist_by_id(mocker):
    session = mocker.Mock()
    session.playlist.return_value = SimpleNamespace(
        id="playlist-1", name="Mix", description="Description"
    )

    playlist = TidalSource(session).playlist("playlist-1")

    session.playlist.assert_called_once_with("playlist-1")
    assert playlist.source_id == "playlist-1"
    assert playlist.name == "Mix"
    assert playlist.description == "Description"


def test_loads_playlist_tracks(mocker):
    playlist = mocker.Mock()
    playlist.tracks_paginated.return_value = [tidal_track("track-1")]
    session = mocker.Mock()
    session.playlist.return_value = playlist

    tracks = list(TidalSource(session).playlist_tracks("playlist-1"))

    session.playlist.assert_called_once_with("playlist-1")
    assert tracks[0].source_id == "track-1"
    assert tracks[0].artists == ("Artist",)
    assert tracks[0].album == "Album"
    assert tracks[0].duration_seconds == 181
    assert tracks[0].isrc == "TEST123"


def test_paginates_saved_tracks(mocker):
    favorites = mocker.Mock()
    favorites.tracks.side_effect = [
        [tidal_track(str(index)) for index in range(50)],
        [tidal_track("last")],
    ]
    session = SimpleNamespace(user=SimpleNamespace(favorites=favorites))

    tracks = list(TidalSource(session).saved_tracks())

    assert len(tracks) == 51
    assert tracks[-1].source_id == "last"
    assert [call.kwargs["offset"] for call in favorites.tracks.call_args_list] == [0, 50]
