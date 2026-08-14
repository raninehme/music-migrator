import pytest

from music_migrator.application import _authenticate_route, _run_route, run_migration
from music_migrator.config import MigrationConfig, RequestSettings
from music_migrator.core.migration import CollectionReport, MigrationReport
from music_migrator.core.planning import plan_route
from music_migrator.profiles import ProfilePaths
from music_migrator.services.spotify.config import SpotifyConfig

SPOTIFY_SERVICES = {"spotify": {"client_id": "client", "client_secret": "secret"}}


def test_authenticates_reverse_route_with_service_sessions(mocker):
    config = MigrationConfig(services=SPOTIFY_SERVICES)
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

    tidal_source.assert_called_once_with(paths.session_for("tidal"))
    spotify_destination.assert_called_once_with(
        SpotifyConfig("client", "secret"), paths.session_for("spotify")
    )
    assert source is tidal_source.return_value
    assert destination is spotify_destination.return_value


def test_combine_runs_both_directions_for_selected_playlist_names(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    config = MigrationConfig(services=SPOTIFY_SERVICES)
    forward_report = MigrationReport([CollectionReport("Mix", 1, 1)])
    reverse_report = MigrationReport()
    run_route = mocker.patch(
        "music_migrator.application._run_route",
        side_effect=[forward_report, reverse_report],
    )

    reports = list(
        run_migration(
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
    config = MigrationConfig(services=SPOTIFY_SERVICES)
    run_route = mocker.patch(
        "music_migrator.application._run_route",
        side_effect=[MigrationReport(), MigrationReport()],
    )

    list(
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
    )

    reverse = run_route.call_args_list[1]
    assert reverse.kwargs["playlist_names"] is None


def test_forward_report_is_available_before_reverse_route_runs(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    config = MigrationConfig(services=SPOTIFY_SERVICES)
    forward_report = MigrationReport([CollectionReport("Mix", 1, 1)])
    run_route = mocker.patch(
        "music_migrator.application._run_route",
        side_effect=[forward_report, RuntimeError("reverse failed")],
    )
    reports = run_migration(
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

    assert next(reports).report is forward_report
    assert run_route.call_count == 1


def test_route_configuration_is_validated_before_authentication(mocker):
    config = MigrationConfig()
    paths = ProfilePaths.for_name("rani")
    tidal_source = mocker.patch("music_migrator.services.tidal.service.TidalSource.authenticate")
    spotify_destination = mocker.patch(
        "music_migrator.services.spotify.service.SpotifyDestination.authenticate"
    )

    with pytest.raises(ValueError, match="Missing Spotify configuration"):
        _authenticate_route(plan_route("tidal", "spotify"), config, paths)

    tidal_source.assert_not_called()
    spotify_destination.assert_not_called()


def test_destination_request_override_configures_migrator(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    paths = ProfilePaths.for_name("rani")
    paths.prepare()
    config = MigrationConfig(
        services=SPOTIFY_SERVICES,
        service_requests={"tidal": RequestSettings(4, 5)},
    )
    mocker.patch("music_migrator.services.spotify.service.SpotifySource.authenticate")
    mocker.patch("music_migrator.services.tidal.service.TidalDestination.authenticate")
    migrator = mocker.patch("music_migrator.application.Migrator")
    migrator.return_value.migrate.return_value = MigrationReport()

    _run_route(
        plan_route("spotify", "tidal"),
        config,
        paths,
        dry_run=True,
        mode="replace",
        playlist_ids=None,
        playlist_names=None,
        include_saved=False,
        refresh_matches=False,
        progress=mocker.Mock(),
    )

    assert migrator.call_args.kwargs["max_concurrency"] == 4
    assert migrator.call_args.kwargs["rate_limit"] == 5
