"""Tests for the leaderboard history collector (weekly GIF snapshots)."""

import json
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

import leaderboard_history as lh

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)

SAMPLE = [
    {
        "athlete": {
            "id": 1,
            "firstname": "Ann",
            "lastname": "Fast",
            "profile": "http://x/a.jpg",
        },
        "distance": 32000.0,
        "rank": 1,
        "num_activities": 3,
    },
    {
        "athlete": {"id": 2, "firstname": "Bob", "lastname": "Slow"},
        "distance": 1000.0,
        "rank": 2,
        "num_activities": 1,
    },
]


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    """Redirect the history file into a scratch directory."""
    monkeypatch.setattr(lh, "OUTPUT_DIR", str(tmp_path))
    return tmp_path


def _write(path, *snapshots):
    path.write_text(
        "".join(json.dumps(s) + "\n" for s in snapshots), encoding="utf-8"
    )


def test_record_writes_slimmed_snapshot(out_dir):
    with mock.patch.object(lh, "get_leaderboard_entries", return_value=SAMPLE):
        assert lh.record_snapshot(now=NOW)

    snap = lh.load_snapshots()[0]
    assert snap["ts"] == NOW.isoformat()
    assert snap["entries"][0]["firstname"] == "Ann"
    assert snap["entries"][0]["num_activities"] == 3
    assert snap["entries"][0]["profile"] == "http://x/a.jpg"
    assert snap["entries"][1]["profile"] == ""


def test_fetch_failure_writes_nothing(out_dir):
    with mock.patch.object(
        lh, "get_leaderboard_entries", side_effect=RuntimeError("HTTP 302")
    ):
        assert not lh.record_snapshot(now=NOW)
    assert not lh.history_path().exists()


def test_empty_leaderboard_writes_nothing(out_dir):
    with mock.patch.object(lh, "get_leaderboard_entries", return_value=[]):
        assert not lh.record_snapshot(now=NOW)
    assert not lh.history_path().exists()


def test_disabled_flag_skips_fetch(out_dir):
    with (
        mock.patch.object(lh, "LEADERBOARD_HISTORY_ENABLED", new=False),
        mock.patch.object(lh, "get_leaderboard_entries") as fetch,
    ):
        assert not lh.record_snapshot(now=NOW)
    fetch.assert_not_called()


def test_prune_drops_old_and_keeps_recent(out_dir):
    old = {"ts": (NOW - timedelta(days=20)).isoformat(), "entries": []}
    new = {"ts": (NOW - timedelta(days=1)).isoformat(), "entries": []}
    _write(lh.history_path(), old, new)
    with mock.patch.object(lh, "HISTORY_RETENTION_DAYS", 14):
        removed = lh.prune(now=NOW)
    assert removed == 1
    kept = lh.load_snapshots()
    assert len(kept) == 1
    assert kept[0]["ts"] == new["ts"]


def test_malformed_lines_are_ignored(out_dir):
    good = {"ts": NOW.isoformat(), "entries": []}
    lh.history_path().write_text(
        "not json\n" + json.dumps(good) + "\n{}\n", encoding="utf-8"
    )
    assert lh.load_snapshots() == [good]
