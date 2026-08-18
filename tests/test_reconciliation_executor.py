"""Test operation dispatch independently from migration orchestration and providers."""

from unittest.mock import Mock

from music_migrator.domain.collections import CollectionSnapshot
from music_migrator.reconciliation import (
    apply_playlist_plan,
    apply_saved_tracks_plan,
    plan_playlist,
    plan_saved_tracks,
)


def test_executor_dispatches_append_with_expected_prefix():
    current = CollectionSnapshot.playlist("playlist:one", "Mix", ["one"])
    plan = plan_playlist(["one", "two"], current, mode="replace")
    writer = Mock()
    playlist = object()

    apply_playlist_plan(writer, playlist, plan)

    writer.append_playlist_tracks.assert_called_once_with(
        playlist,
        ["two"],
        expected_before=["one"],
    )
    writer.replace_playlist_tracks.assert_not_called()


def test_executor_dispatches_replacement_with_original_state():
    current = CollectionSnapshot.playlist("playlist:one", "Mix", ["old"])
    plan = plan_playlist(["new"], current, mode="replace")
    writer = Mock()
    playlist = object()

    apply_playlist_plan(writer, playlist, plan)

    writer.replace_playlist_tracks.assert_called_once_with(
        playlist,
        ["new"],
        original_track_ids=["old"],
    )
    writer.append_playlist_tracks.assert_not_called()


def test_executor_does_nothing_for_idempotent_playlist():
    current = CollectionSnapshot.playlist("playlist:one", "Mix", ["one"])
    plan = plan_playlist(["one"], current, mode="replace")
    writer = Mock()

    apply_playlist_plan(writer, object(), plan)

    writer.append_playlist_tracks.assert_not_called()
    writer.replace_playlist_tracks.assert_not_called()


def test_executor_dispatches_only_missing_saved_tracks():
    current = CollectionSnapshot.saved_tracks("saved-tracks", "Favorites", {"one"})
    plan = plan_saved_tracks(["one", "two"], current)
    writer = Mock()

    apply_saved_tracks_plan(writer, plan)

    writer.add_saved_tracks.assert_called_once_with(["two"])
