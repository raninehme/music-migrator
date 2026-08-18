from music_migrator.core.collections import CollectionSnapshot


def test_playlist_snapshot_preserves_order():
    snapshot = CollectionSnapshot.playlist("playlist:one", "Mix", ["b", "a"])

    assert snapshot.kind == "playlist"
    assert snapshot.track_ids == ("b", "a")
    assert snapshot.ordered is True


def test_saved_tracks_snapshot_is_order_independent():
    first = CollectionSnapshot.saved_tracks("saved-tracks", "Favorites", ["b", "a"])
    second = CollectionSnapshot.saved_tracks("saved-tracks", "Favorites", ["a", "b"])

    assert first.track_ids == ("a", "b")
    assert first.fingerprint == second.fingerprint
    assert first.ordered is False


def test_playlist_fingerprint_changes_when_order_changes():
    first = CollectionSnapshot.playlist("playlist:one", "Mix", ["a", "b"])
    second = CollectionSnapshot.playlist("playlist:one", "Mix", ["b", "a"])

    assert first.fingerprint != second.fingerprint
