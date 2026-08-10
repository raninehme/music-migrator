import pytest

from music_migrator.services.registry import get_service
from music_migrator.services.spotify.service import SpotifySource
from music_migrator.services.tidal.service import TidalDestination


def test_registry_exposes_current_service_capabilities():
    spotify = get_service("spotify")
    tidal = get_service("TIDAL")

    assert spotify.source is SpotifySource
    assert spotify.destination is None
    assert tidal.source is None
    assert tidal.destination is TidalDestination


def test_registry_rejects_unknown_service():
    with pytest.raises(ValueError, match="Unknown service 'youtube'"):
        get_service("youtube")
