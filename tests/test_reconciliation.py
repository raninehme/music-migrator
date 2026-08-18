import pytest

from music_migrator.core.reconciliation import plan_playlist


def test_replace_uses_only_matched_source_order():
    plan = plan_playlist(
        ["source-1", "source-2"],
        ["destination-only", "source-1"],
        mode="replace",
    )

    assert plan.desired == ("source-1", "source-2")
    assert plan.changed is True
    assert plan.append_from is None


def test_combine_preserves_unique_destination_tracks_after_source_order():
    plan = plan_playlist(
        ["source-1", "source-2"],
        ["destination-only", "source-1", "destination-last"],
        mode="combine",
    )

    assert plan.desired == (
        "source-1",
        "source-2",
        "destination-only",
        "destination-last",
    )


def test_unchanged_playlist_is_idempotent():
    plan = plan_playlist(["one", "two"], ["one", "two"], mode="replace")

    assert plan.changed is False
    assert plan.append_from == 2


def test_prefix_can_resume_from_existing_length():
    plan = plan_playlist(
        ["one", "two", "three", "four"],
        ["one", "two"],
        mode="replace",
    )

    assert plan.changed is True
    assert plan.append_from == 2


def test_non_prefix_requires_reconciliation_from_start():
    plan = plan_playlist(["one", "two"], ["two"], mode="replace")

    assert plan.append_from is None


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="unknown migration mode"):
        plan_playlist(["one"], [], mode="merge")  # type: ignore[arg-type]
