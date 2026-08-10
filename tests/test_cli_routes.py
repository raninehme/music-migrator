from music_migrator.cli import _authenticate_route
from music_migrator.config import MigrationConfig, SpotifyConfig
from music_migrator.core.planning import plan_route
from music_migrator.profiles import ProfilePaths


def test_authenticates_reverse_route_with_service_sessions(mocker):
    config = MigrationConfig(spotify=SpotifyConfig("client", "secret"))
    paths = ProfilePaths.for_name("rani")
    tidal_source = mocker.patch("music_migrator.services.tidal.service.TidalSource.authenticate")
    spotify_destination = mocker.patch(
        "music_migrator.services.spotify.service.SpotifyDestination.authenticate"
    )

    source, destination = _authenticate_route(
        plan_route("tidal", "spotify"),
        config,
        paths,
    )

    tidal_source.assert_called_once_with(paths.tidal_session)
    spotify_destination.assert_called_once_with(config.spotify, paths.spotify_session)
    assert source is tidal_source.return_value
    assert destination is spotify_destination.return_value
