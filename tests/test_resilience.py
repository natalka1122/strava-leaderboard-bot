"""Regression tests: one bad Strava payload must never crash the process."""

import json
from datetime import datetime, timezone
from unittest import mock

import cookie_health_check as chc
import event_reminders as er
import leaderboard_history as lh
import strava_scraper as ss

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _next_data(page_props):
    payload = {"props": {"pageProps": page_props}}
    return (
        '<html><script id="__NEXT_DATA__">'
        f"{json.dumps(payload)}</script></html>"
    )


def _ok_response(text):
    resp = mock.Mock()
    resp.status_code = 200
    resp.url = "https://www.strava.com/clubs/47046/group_events/1"
    resp.text = text
    return resp


def test_null_event_occurrence_falls_back_instead_of_crashing():
    props = {
        "eventOccurrence": None,
        "event": {"occurrences": [{"title": "Tuesday Run", "address": "Park"}]},
    }
    with mock.patch.object(ss, "_session") as session:
        session.return_value.get.return_value = _ok_response(
            _next_data(props)
        )
        event = ss.fetch_group_event(47046, "1")
    assert event["title"] == "Tuesday Run"
    assert event["place"] == "Park"


def test_get_group_events_skips_event_that_raises():
    with (
        mock.patch.object(er, "fetch_group_event_ids", return_value=["1", "2"]),
        mock.patch.object(
            er,
            "fetch_group_event",
            side_effect=[AttributeError("boom"), {"id": "2"}],
        ),
    ):
        events = er.get_group_events()
    assert events == [{"id": "2"}]


def test_record_snapshot_survives_unexpected_error(tmp_path, monkeypatch):
    monkeypatch.setattr(lh, "OUTPUT_DIR", str(tmp_path))
    with mock.patch.object(
        lh, "get_leaderboard_entries", side_effect=ConnectionError("net")
    ):
        assert lh.record_snapshot(now=NOW) is False


def test_guard_job_swallows_exception():
    seen = []

    def boom():
        seen.append("ran")
        raise RuntimeError("kaboom")

    chc.guard_job(boom)()
    assert seen == ["ran"]


def test_guard_job_passes_kwargs():
    seen = {}

    def job(*, flag):
        seen["flag"] = flag

    chc.guard_job(job, flag=True)()
    assert seen == {"flag": True}
