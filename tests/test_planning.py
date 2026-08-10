import pytest

from music_migrator.core.planning import plan_route


@pytest.mark.parametrize(
    ("source", "destination", "key"),
    [
        ("spotify", "tidal", "spotify-to-tidal"),
        ("tidal", "spotify", "tidal-to-spotify"),
    ],
)
def test_plans_supported_routes(source, destination, key):
    route = plan_route(source, destination)

    assert route.source.name == source
    assert route.destination.name == destination
    assert route.key == key
    assert route.source.authenticate_source is not None
    assert route.destination.authenticate_destination is not None


def test_rejects_same_service_route():
    with pytest.raises(ValueError, match="must be different"):
        plan_route("spotify", "spotify")


def test_rejects_unknown_service():
    with pytest.raises(ValueError, match="Unknown service 'youtube'"):
        plan_route("youtube", "tidal")
