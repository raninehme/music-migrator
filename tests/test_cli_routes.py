from music_migrator.application import _authenticate_route, run_migration
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


def test_combine_runs_both_directions_for_selected_playlist_names(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    config = MigrationConfig(spotify=SpotifyConfig("client", "secret"))
    forward_report = MigrationReport([CollectionReport("Mix", 1, 1)])
    reverse_report = MigrationReport()
    run_route = mocker.patch(
        "music_migrator.application._run_route",
        side_effect=[forward_report, reverse_report],
    )

    reports = run_migration(
        plan_route("tidal", "spotify"),
        config,
        paths,
        dry_run=True,
        mode="combine",
        playlist_ids=["tidal-playlist"],
        include_saved=False,
        refresh_matches=False,
        progress=mocker.Mock(),
    )

    assert [item.route.key for item in reports] == ["tidal-to-spotify", "spotify-to-tidal"]
    assert run_route.call_count == 2
    forward, reverse = run_route.call_args_list
    assert forward.args[0].key == "tidal-to-spotify"
    assert forward.kwargs["playlist_ids"] == ["tidal-playlist"]
    assert forward.kwargs["playlist_names"] is None
    assert reverse.args[0].key == "spotify-to-tidal"
    assert reverse.kwargs["playlist_ids"] is None
    assert reverse.kwargs["playlist_names"] == {"Mix"}


def test_combine_all_playlists_does_not_filter_reverse_route(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    config = MigrationConfig(spotify=SpotifyConfig("client", "secret"))
    run_route = mocker.patch(
        "music_migrator.application._run_route",
        side_effect=[MigrationReport(), MigrationReport()],
    )

    run_migration(
        plan_route("tidal", "spotify"),
        config,
        paths,
        dry_run=True,
        mode="combine",
        playlist_ids=None,
        include_saved=False,
        refresh_matches=False,
        progress=mocker.Mock(),
    )

    reverse = run_route.call_args_list[1]
    assert reverse.kwargs["playlist_names"] is None
