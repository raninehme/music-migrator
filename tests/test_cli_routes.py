from music_migrator.cli import _authenticate_route, main
from music_migrator.config import MigrationConfig, SpotifyConfig
from music_migrator.core.migration import CollectionReport, MigrationReport
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


def test_combine_runs_both_directions_for_the_selected_playlist_names(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    paths.config.write_text(
        """spotify:
  client_id: client
  client_secret: secret
"""
    )
    forward_report = MigrationReport([CollectionReport("Mix", 1, 1)])
    reverse_report = MigrationReport()
    run_route = mocker.patch(
        "music_migrator.cli._run_route",
        side_effect=[forward_report, reverse_report],
    )
    mocker.patch("music_migrator.cli._print_report")

    result = main(
        [
            "--profile",
            "rani",
            "--from",
            "tidal",
            "--to",
            "spotify",
            "--mode",
            "combine",
            "--dry-run",
            "--playlist",
            "tidal-playlist",
            "--no-saved-tracks",
        ]
    )

    assert result == 0
    assert run_route.call_count == 2
    forward, reverse = run_route.call_args_list
    assert forward.args[0].key == "tidal-to-spotify"
    assert forward.kwargs["playlist_ids"] == ["tidal-playlist"]
    assert forward.kwargs["playlist_names"] is None
    assert reverse.args[0].key == "spotify-to-tidal"
    assert reverse.kwargs["playlist_ids"] is None
    assert reverse.kwargs["playlist_names"] == {"Mix"}

    run_route.reset_mock()
    run_route.side_effect = [forward_report, reverse_report]

    result = main(
        [
            "--profile",
            "rani",
            "--from",
            "tidal",
            "--to",
            "spotify",
            "--mode",
            "combine",
            "--dry-run",
            "--no-saved-tracks",
        ]
    )

    assert result == 0
    assert run_route.call_count == 2
    reverse = run_route.call_args_list[1]
