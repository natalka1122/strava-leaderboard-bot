"""Tests for event_reminders money logic: lead windows, state dedupe, photo picks."""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import event_reminders as er

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def occ(days: float) -> datetime:
    return NOW + timedelta(days=days)


class FiringLeadsTest(unittest.TestCase):
    def test_inside_window_fires(self):
        self.assertEqual(er.firing_leads(NOW, occ(6.75), [7, 1]), [7])   # (6, 7]
        self.assertEqual(er.firing_leads(NOW, occ(0.25), [7, 1]), [1])   # (0, 1]

    def test_exactly_L_fires(self):
        self.assertEqual(er.firing_leads(NOW, occ(7), [7, 1]), [7])
        self.assertEqual(er.firing_leads(NOW, occ(1), [7, 1]), [1])

    def test_exactly_L_minus_1_does_not_fire(self):
        # window is (L-1, L] — the lower bound is excluded
        self.assertEqual(er.firing_leads(NOW, occ(6), [7]), [])
        self.assertEqual(er.firing_leads(NOW, occ(0), [1]), [])
        self.assertEqual(er.firing_leads(NOW, occ(6), [14, 7, 1]), [])   # (13,14]? no

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
        er.save_state([
            {"event_id": "1", "occurrence": occ(2).isoformat(), "lead": 7},   # future — kept
            {"event_id": "2", "occurrence": occ(-1).isoformat(), "lead": 1},  # past — pruned
        ])
        rows = er.load_state(NOW)
        self.assertEqual([r["event_id"] for r in rows], ["1"])

    def test_corrupt_file_starts_fresh(self):
        with open(er.STATE_FILE, "w") as f:
            f.write("{not json")
        self.assertEqual(er.load_state(NOW), [])


class OccurrenceParseTest(unittest.TestCase):
    def test_parses_utc_zulu(self):
        got = er._parse_occurrences({"id": 9, "upcoming_occurrences": ["2026-09-20T07:00:00Z"]})
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].utcoffset(), timedelta(0))

    def test_skips_garbage(self):
        got = er._parse_occurrences({"id": 9, "upcoming_occurrences": ["not-a-date", "2026-09-20T07:00:00Z"]})
        self.assertEqual(len(got), 1)

    def test_no_occurrences(self):
        self.assertEqual(er._parse_occurrences({"id": 9}), [])


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


if __name__ == "__main__":
    unittest.main()