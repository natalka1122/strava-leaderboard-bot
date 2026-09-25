"""Tests for event_reminders money logic: lead windows, state dedupe, photo picks."""

import os
import shutil
import sys
import tempfile
import json
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
)

import event_reminders as er

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
BUD = "Europe/Budapest"


def bud(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=ZoneInfo(BUD))


def occ(days: float) -> datetime:
    return NOW + timedelta(days=days)


class FiringLeadsTest(unittest.TestCase):
    def test_inside_window_fires(self):
        self.assertEqual(er.firing_leads(NOW, occ(6.75), [7, 1]), [7])  # (6, 7]
        self.assertEqual(er.firing_leads(NOW, occ(0.25), [7, 1]), [1])  # (0, 1]

    def test_exactly_L_fires(self):
        self.assertEqual(er.firing_leads(NOW, occ(7), [7, 1]), [7])
        self.assertEqual(er.firing_leads(NOW, occ(1), [7, 1]), [1])

    def test_exactly_L_minus_1_does_not_fire(self):
        # window is (L-1, L] — the lower bound is excluded
        self.assertEqual(er.firing_leads(NOW, occ(6), [7]), [])
        self.assertEqual(er.firing_leads(NOW, occ(0), [1]), [])
        self.assertEqual(er.firing_leads(NOW, occ(6), [14, 7, 1]), [])  # (13,14]? no

    def test_beyond_L_does_not_fire(self):
        self.assertEqual(er.firing_leads(NOW, occ(8), [7]), [])
        self.assertEqual(er.firing_leads(NOW, occ(15), [14, 7, 1]), [])

    def test_missed_window_never_fires_late(self):
        # 5.5d left: the 7d window passed unseen, 1d window not reached yet
        self.assertEqual(er.firing_leads(NOW, occ(5.5), [7, 1]), [])
        # 0.9d left after the 1d window was already open — fires (still inside)
        self.assertEqual(er.firing_leads(NOW, occ(0.9), [7, 1]), [1])

    def test_custom_lead_lengths(self):
        self.assertEqual(er.firing_leads(NOW, occ(13.5), [14, 7, 1]), [14])
        self.assertEqual(er.firing_leads(NOW, occ(3.5), [14, 7, 1]), [])
        self.assertEqual(er.firing_leads(NOW, occ(2.9), [3]), [3])


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._old = er.STATE_FILE
        er.STATE_FILE = os.path.join(self.tmp, "state.json")

    def tearDown(self):
        er.STATE_FILE = self._old

    def test_roundtrip_and_dedupe(self):
        rows = er.load_state(NOW)
        self.assertEqual(rows, [])
        er.save_state([{"event_id": "1", "occurrence": occ(2).isoformat(), "lead": 1}])
        rows = er.load_state(NOW)
        self.assertTrue(er.is_posted(rows, "1", occ(2), 1))
        self.assertFalse(er.is_posted(rows, "1", occ(2), 7))
        self.assertFalse(er.is_posted(rows, "2", occ(2), 1))
        self.assertFalse(er.is_posted(rows, "1", occ(3), 1))

    def test_prune_passed_occurrences(self):
        er.save_state(
            [
                {
                    "event_id": "1",
                    "occurrence": occ(2).isoformat(),
                    "lead": 7,
                },  # future — kept
                {
                    "event_id": "2",
                    "occurrence": occ(-1).isoformat(),
                    "lead": 1,
                },  # past — pruned
            ]
        )
        rows = er.load_state(NOW)
        self.assertEqual([r["event_id"] for r in rows], ["1"])

    def test_corrupt_file_starts_fresh(self):
        with open(er.STATE_FILE, "w") as f:
            f.write("{not json")
        self.assertEqual(er.load_state(NOW), [])


class PhotoPoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._old = er.EVENT_PHOTOS_DIR
        er.EVENT_PHOTOS_DIR = self.tmp

    def tearDown(self):
        er.EVENT_PHOTOS_DIR = self._old

    def test_pool_filters_images_and_sorts(self):
        for name in ("b.pNg", "a.jpg", "c.webp", "skip.txt"):
            open(os.path.join(self.tmp, name), "w").close()
        self.assertEqual(er.photo_pool(), ["a.jpg", "b.pNg", "c.webp"])

    def test_missing_dir_empty_pool(self):
        er.EVENT_PHOTOS_DIR = os.path.join(self.tmp, "nonexistent")
        self.assertEqual(er.photo_pool(), [])

    def test_pick_deterministic_per_occurrence(self):
        for name in ("1.jpg", "2.jpg", "3.jpg"):
            open(os.path.join(self.tmp, name), "w").close()
        pool = er.photo_pool()
        self.assertEqual(er.pick_photo(pool, occ(3)), er.pick_photo(pool, occ(3)))
        self.assertIn(er.pick_photo(pool, occ(3.7)), pool)
        self.assertIn(er.pick_photo(pool, occ(5.1)), pool)


class ExpandOccurrencesTest(unittest.TestCase):
    """Expansion of the served next occurrence + recurrence rule."""

    def test_oneshot_no_rule(self):
        ev = {
            "id": "1",
            "zone": BUD,
            "occurrence_datetime": "2026-01-15T09:00:00",
            "schedule": {"startTime": "2026-01-15T09:00:00"},
        }
        got = er.expand_occurrences(ev, NOW, 30)
        self.assertEqual(got, [bud("2026-01-15T09:00:00")])

    def test_oneshot_past_served_is_skipped(self):
        ev = {
            "id": "1",
            "zone": BUD,
            "occurrence_datetime": "2026-01-01T09:00:00",
            "schedule": {"startTime": "2026-01-01T09:00:00"},
        }
        self.assertEqual(er.expand_occurrences(ev, NOW, 30), [])

    def test_monthly_first_saturday_real_shape(self):
        # the live Sziget Run 5K event: monthly, first Saturday
        ev = {
            "id": "2116323",
            "zone": BUD,
            "occurrence_datetime": "2026-10-03T09:00:00",
            "schedule": {
                "startTime": "2026-09-05T09:00:00",
                "recurrenceRule": {
                    "days": ["Saturday"],
                    "frequency": "Monthly",
                    "interval": 1,
                    "ordinals": ["First"],
                },
            },
        }
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        got = er.expand_occurrences(ev, now, 120)
        first_saturdays = [
            "2026-10-03T09:00:00",
            "2026-11-07T09:00:00",
            "2026-12-05T09:00:00",
            "2027-01-02T09:00:00",
        ]
        self.assertEqual(got, [bud(s) for s in first_saturdays])

    def test_weekly_every_week(self):
        ev = {
            "id": "2",
            "zone": BUD,
            "occurrence_datetime": "2026-01-10T18:00:00",
            "schedule": {
                "startTime": "2026-01-03T18:00:00",
                "recurrenceRule": {
                    "days": ["Saturday"],
                    "frequency": "Weekly",
                    "interval": 1,
                },
            },
        }
        now = datetime(2026, 1, 5, tzinfo=timezone.utc)
        got = er.expand_occurrences(ev, now, 20)
        self.assertEqual(
            got,
            [
                bud("2026-01-10T18:00:00"),
                bud("2026-01-17T18:00:00"),
                bud("2026-01-24T18:00:00"),
            ],
        )

    def test_results_are_aware_sorted_and_future_only(self):
        ev = {
            "id": "3",
            "zone": "UTC",
            "occurrence_datetime": "2026-01-10T09:00:00",
            "schedule": {
                "startTime": "2026-01-10T09:00:00",
                "recurrenceRule": {
                    "days": ["Friday"],
                    "frequency": "Weekly",
                    "interval": 1,
                },
            },
        }
        now = datetime(2026, 1, 20, tzinfo=timezone.utc)  # past the first Fridays
        got = er.expand_occurrences(ev, now, 14)
        self.assertTrue(got)
        self.assertTrue(all(o.tzinfo is not None for o in got))
        self.assertEqual(got, sorted(got))
        self.assertTrue(all(o > now for o in got))


class ScraperParseTest(unittest.TestCase):
    """Parsing of the SSR pages (mocked transport)."""

    def test_event_ids_from_club_page(self):
        from strava_scraper import fetch_group_event_ids
        import unittest.mock as mock

        html = (
            '<div data-react-props="&quot;appContext&quot;:{&quot;clubId&quot;:47046,'
            '&quot;upcomingGroupEventIds&quot;:[2116323,2119999],&quot;athleteId&quot;:&quot;1&quot;}">'
        )
        fake = mock.Mock()
        fake.status_code = 200
        fake.url = "https://www.strava.com/clubs/47046"
        fake.text = html
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.return_value = fake
            self.assertEqual(fetch_group_event_ids(47046), ["2116323", "2119999"])

    def test_event_ids_empty(self):
        from strava_scraper import fetch_group_event_ids
        import unittest.mock as mock

        fake = mock.Mock()
        fake.status_code = 200
        fake.url = "https://www.strava.com/clubs/47046"
        fake.text = "no events section"
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.return_value = fake
            self.assertEqual(fetch_group_event_ids(47046), [])

    def test_event_detail_from_next_data(self):
        from strava_scraper import fetch_group_event
        import unittest.mock as mock, json as _json

        occ = {
            "title": "SZIGET RUN 5K",
            "zone": "Europe/Budapest",
            "address": "Margit island",
            "occurrenceDateTime": "2026-10-03T09:00:00",
            "schedule": {
                "startTime": "2026-09-05T09:00:00",
                "recurrenceRule": {
                    "days": ["Saturday"],
                    "frequency": "Monthly",
                    "interval": 1,
                    "ordinals": ["First"],
                },
            },
        }
        nd = json.dumps({"props": {"pageProps": {"eventOccurrence": occ}}})
        html = f'<script id="__NEXT_DATA__" type="application/json">{nd}</script>'
        fake = mock.Mock()
        fake.status_code = 200
        fake.url = (
            "https://www.strava.com/clubs/47046/group_events/2116323/occurrences/x"
        )
        fake.text = html
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.return_value = fake
            ev = fetch_group_event(47046, "2116323")
        self.assertEqual(ev["title"], "SZIGET RUN 5K")
        self.assertEqual(ev["place"], "Margit island")
        self.assertEqual(ev["occurrence_datetime"], "2026-10-03T09:00:00")


if __name__ == "__main__":
    unittest.main()
