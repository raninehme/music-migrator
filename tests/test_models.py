from music_migrator.domain.models import Playlist, Track


def test_domain_models_are_immutable():
    track = Track(
        source_id="track-1",
        title="Song",
        artists=("Artist",),
        album="Album",
        duration_seconds=180,
        isrc="TEST123",
    )
    playlist = Playlist(source_id="playlist-1", name="Playlist")

    assert track.artists == ("Artist",)
    assert playlist.description == ""
