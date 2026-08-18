from music_migrator.services.registry import SERVICES

SOURCE_METHODS = ("playlists", "playlist", "playlist_tracks", "saved_tracks")
DESTINATION_METHODS = (
    "playlists_by_name",
    "create_playlist",
    "search_tracks",
    "playlist_track_ids",
    "append_playlist_tracks",
    "replace_playlist_tracks",
    "saved_track_ids",
    "add_saved_tracks",
)


def test_registered_services_have_consistent_names_and_defaults():
    for key, service in SERVICES.items():
        assert service.name == key
        assert service.request_defaults.max_concurrency > 0
        assert service.request_defaults.rate_limit > 0


def test_source_capabilities_are_fully_wired():
    for service in SERVICES.values():
        if service.source is None:
            assert service.authenticate_source is None
            continue

        assert service.authenticate_source is not None
        for method in SOURCE_METHODS:
            assert hasattr(service.source, method), f"{service.name} source missing {method}"


def test_destination_capabilities_are_fully_wired():
    for service in SERVICES.values():
        if service.destination is None:
            assert service.authenticate_destination is None
            continue

        assert service.authenticate_destination is not None
        for method in DESTINATION_METHODS:
            assert hasattr(service.destination, method), (
                f"{service.name} destination missing {method}"
            )
