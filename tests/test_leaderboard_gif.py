"""Tests for the weekly leaderboard GIF renderer."""

from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from PIL import Image

import leaderboard_gif as lg

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)  # Thursday


def _snapshot(hours_ago, entries):
    stamp = (NOW - timedelta(hours=hours_ago)).isoformat()
    return {"ts": stamp, "entries": entries}


def _athlete(athlete_id, firstname, distance_km, runs=1):
    return {
        "id": athlete_id,
        "firstname": firstname,
        "lastname": "Runner",
        "distance": distance_km * 1000,
        "num_activities": runs,
    }


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "OUTPUT_DIR", str(tmp_path))
    return tmp_path


def test_roster_freezes_to_final_snapshot():
    snapshots = [
        _snapshot(48, [_athlete(1, "Ann", 5), _athlete(2, "Bob", 10)]),
        _snapshot(
            3,
            [
                _athlete(1, "Ann", 40),
                _athlete(2, "Bob", 10),
                _athlete(3, "Cid", 4),
            ],
        ),
    ]
    frames = lg.build_frames(snapshots, NOW)
    assert len(frames) == 2
    _, first_rows = frames[0]
    assert {row["name"] for row in first_rows} == {
        "Ann Runner",
        "Bob Runner",
        "Cid Runner",
    }
    cid = next(row for row in first_rows if row["name"].startswith("Cid"))
    assert cid["distance"] == 0  # present from the start, frozen


def test_rows_ranked_by_distance():
    snapshots = [
        _snapshot(3, [_athlete(1, "Ann", 5), _athlete(2, "Bob", 10)]),
        _snapshot(2, [_athlete(1, "Ann", 9), _athlete(2, "Bob", 10)]),
    ]
    _, rows = lg.build_frames(snapshots, NOW)[0]
    assert [row["name"] for row in rows] == ["Bob Runner", "Ann Runner"]
    assert [row["rank"] for row in rows] == [1, 2]


def test_cutoff_pulls_in_athletes_beyond_min(monkeypatch):
    monkeypatch.setattr(lg, "LEADERBOARD_MIN_RUNNERS", 1)
    monkeypatch.setattr(lg, "LEADERBOARD_KM_CUTOFF", 30)
    entries = [
        _athlete(1, "Ann", 5),
        _athlete(2, "Bob", 40),
        _athlete(3, "Cid", 35),
    ]
    snapshots = [_snapshot(3, entries), _snapshot(2, entries)]
    _, rows = lg.build_frames(snapshots, NOW)[0]
    assert {row["name"] for row in rows} == {"Bob Runner", "Cid Runner"}


def test_previous_week_is_excluded():
    old = _snapshot(8 * 24, [_athlete(9, "Old", 99)])
    recent = _snapshot(3, [_athlete(1, "Ann", 5)])
    recent2 = _snapshot(2, [_athlete(1, "Ann", 6)])
    frames = lg.build_frames([old, recent, recent2], NOW)
    assert len(frames) == 2
    assert all(
        row["name"] != "Old Runner" for _, rows in frames for row in rows
    )


def test_generate_writes_gif(out_dir):
    snapshots = [
        _snapshot(3, [_athlete(1, "Ann", 5), _athlete(2, "Bob", 10)]),
        _snapshot(2, [_athlete(1, "Ann", 9), _athlete(2, "Bob", 10)]),
    ]
    with mock.patch.object(lg, "load_snapshots", return_value=snapshots):
        path = lg.generate_weekly_gif(now=NOW)
    assert path is not None
    assert path.exists()
    with Image.open(path) as gif:
        assert getattr(gif, "n_frames", 0) == 2


def test_generate_skips_when_disabled(out_dir, monkeypatch):
    monkeypatch.setattr(lg, "LEADERBOARD_GIF_ENABLED", False)
    assert lg.generate_weekly_gif(now=NOW) is None


def test_generate_skips_with_single_snapshot(out_dir):
    snapshots = [_snapshot(3, [_athlete(1, "Ann", 5)])]
    with mock.patch.object(lg, "load_snapshots", return_value=snapshots):
        assert lg.generate_weekly_gif(now=NOW) is None
