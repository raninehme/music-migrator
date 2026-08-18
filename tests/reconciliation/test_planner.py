"""Test reconciliation policy and operation planning without provider side effects."""

import pytest

from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.reconciliation import (
    AddSavedTracks,
    AppendPlaylistTracks,
    ReplacePlaylistTracks,
    plan_playlist,
    plan_saved_tracks,
)


def playlist(track_ids: list[str]) -> CollectionSnapshot:
    return CollectionSnapshot.playlist("playlist:one", "Mix", track_ids)


def test_replace_uses_only_matched_source_order():
    plan = plan_playlist(
        ["source-1", "source-2"],
        playlist(["destination-only", "source-1"]),
        mode="replace",
    )

    assert plan.desired.track_ids == ("source-1", "source-2")
    assert plan.operations == (ReplacePlaylistTracks(("source-1", "source-2")),)


def test_combine_preserves_unique_destination_tracks_after_source_order():
    plan = plan_playlist(
        ["source-1", "source-2"],
        playlist(["destination-only", "source-1", "destination-last"]),
        mode="combine",
    )

    assert plan.desired.track_ids == (
        "source-1",
        "source-2",
        "destination-only",
        "destination-last",
    )
    assert plan.operations == (
        ReplacePlaylistTracks(("source-1", "source-2", "destination-only", "destination-last")),
    )


def test_unchanged_playlist_is_idempotent():
    plan = plan_playlist(["one", "two"], playlist(["one", "two"]), mode="replace")

    assert plan.changed is False
    assert plan.operations == ()


def test_prefix_plans_only_missing_append_tracks():
    plan = plan_playlist(
        ["one", "two", "three", "four"],
        playlist(["one", "two"]),
        mode="replace",
    )

    assert plan.changed is True
    assert plan.operations == (AppendPlaylistTracks(("three", "four")),)


def test_non_prefix_plans_full_replacement():
    plan = plan_playlist(["one", "two"], playlist(["two"]), mode="replace")

    assert plan.operations == (ReplacePlaylistTracks(("one", "two")),)


def test_saved_tracks_are_modeled_as_an_unordered_union():
    current = CollectionSnapshot.saved_tracks("saved-tracks", "Favorites", {"existing"})
    plan = plan_saved_tracks(["matched", "existing"], current)

    assert plan.current.ordered is False
    assert plan.desired.track_ids == ("existing", "matched")
    assert plan.operations == (AddSavedTracks(("matched",)),)


def test_saved_tracks_are_idempotent_when_every_match_exists():
    current = CollectionSnapshot.saved_tracks("saved-tracks", "Favorites", {"one", "two"})
    plan = plan_saved_tracks(["two", "one"], current)

    assert plan.changed is False
    assert plan.operations == ()


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="unknown migration mode"):
        plan_playlist(["one"], playlist([]), mode="merge")  # type: ignore[arg-type]


def test_playlist_policy_rejects_saved_tracks_snapshot():
    current = CollectionSnapshot.saved_tracks("saved-tracks", "Favorites", set())

    with pytest.raises(ValueError, match="playlist snapshot"):
        plan_playlist(["one"], current, mode="replace")
