"""Tests for scraper health logic: cookie check degradation detection."""
import os
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))


class CheckCookieTest(unittest.TestCase):
    def _fake(self, status, body=None, text="<html></html>"):
        r = mock.Mock()
        r.status_code = status
        r.text = text
        r.json.side_effect = ValueError("no json") if body is None else (lambda: body)
        return r

    def test_json_200_is_healthy(self):
        from strava_scraper import check_cookie
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.return_value = self._fake(200, body={"data": []})
            self.assertEqual(check_cookie(), 200)

    def test_expired_session(self):
        from strava_scraper import check_cookie
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.return_value = self._fake(401)
            self.assertEqual(check_cookie(), 401)

    def test_html_shell_becomes_418_after_retries(self):
        from strava_scraper import check_cookie
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.return_value = self._fake(200, text="<!DOCTYPE html>")
            self.assertEqual(check_cookie(), 418)
            self.assertEqual(sess.return_value.get.call_count, 3)

    def test_shell_then_json_recovers(self):
        from strava_scraper import check_cookie
        with mock.patch("strava_scraper._session") as sess:
            html = self._fake(200, text="<html>")
            good = self._fake(200, body={"data": []})
            sess.return_value.get.side_effect = [html, good]
            self.assertEqual(check_cookie(), 200)

    def test_network_error_is_zero(self):
        from strava_scraper import check_cookie
        import requests
        with mock.patch("strava_scraper._session") as sess:
            sess.return_value.get.side_effect = requests.ConnectionError("boom")
            self.assertEqual(check_cookie(), 0)


if __name__ == "__main__":
    unittest.main()