"""Fetch Strava club leaderboard from the web JSON API.

Only needs a valid _strava4_session cookie (refresh every ~2-4 weeks).
Forwards athlete identity, distance, and a selected set of stat
fields (see STAT_KEYS) to the image generator.
"""
import html
import json
import logging
import re
import time

import requests
from config import CLUB_ID, STRAVA_SESSION_COOKIE

logger = logging.getLogger(__name__)

# Keys the web API returns that we forward to the image generator
STAT_KEYS = (
    "velocity", "elev_gain", "num_activities",
    "best_activities_distance", "moving_time", "rank",
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    })
    if STRAVA_SESSION_COOKIE:
        # Send as raw Cookie header — requests cookie jar causes 302 → /login
        s.headers["Cookie"] = f"_strava4_session={STRAVA_SESSION_COOKIE}"
    return s


def get_leaderboard_entries(per_page: int = 20) -> list[dict]:
    url = f"https://www.strava.com/clubs/{CLUB_ID}/leaderboard"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": url,
    }

    logger.info("Fetching leaderboard from Strava web JSON API…")
    # Strava A/B-serves an HTML shell for a share of requests; retry until the
    # body is actually JSON so a flaky 200-with-HTML never crashes the bot.
    resp = None
    data = None
    for attempt in range(3):
        resp = _session().get(
            url, params={"per_page": per_page, "page": 1}, headers=headers,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                break
            except ValueError:
                logger.warning("Leaderboard returned non-JSON body (attempt %d/3)", attempt + 1)
                time.sleep(2 * (attempt + 1))
        else:
            break
    assert resp is not None  # the loop above always assigns it
    if resp.status_code != 200:
        logger.error("Web API returned HTTP %d", resp.status_code)
        raise RuntimeError(f"Leaderboard returned HTTP {resp.status_code}")
    if data is None:
        raise RuntimeError("Leaderboard returned a non-JSON response (HTML shell?)")

    raw = data.get("data", [])
    logger.info("Got %d entries from Strava web API", len(raw))

    entries = []
    for row in raw:
        entry = {
            "athlete": {
                "id": row.get("athlete_id"),
                "firstname": row.get("athlete_firstname", ""),
                "lastname": row.get("athlete_lastname", ""),
                "profile": row.get("athlete_picture_url", ""),
                "profile_medium": row.get("athlete_picture_url", ""),
            },
            "distance": float(row.get("distance") or 0),
        }
        # Forward extra stat fields (key names match what image_generator expects)
        for k in STAT_KEYS:
            v = row.get(k)
            if v is not None:
                entry[k] = v

        entries.append(entry)

    return entries


def check_cookie() -> int:
    """Quick health check: fetch leaderboard with per_page=1, no redirects.

    Returns 200 (valid), 302/401 (expired), 0 (network error), 418 (server
    returned HTML instead of JSON — Strava rollout, fetch degraded)."""
    url = f"https://www.strava.com/clubs/{CLUB_ID}/leaderboard"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": url,
    }
    try:
        for attempt in range(3):
            resp = _session().get(
                url, params={"per_page": 1, "page": 1},
                headers=headers,
                allow_redirects=False,
                timeout=15,
            )
            if resp.status_code != 200:
                return resp.status_code
            try:
                resp.json()
                return 200
            except ValueError:
                logger.warning("Cookie check: non-JSON body (attempt %d/3)", attempt + 1)
                time.sleep(2 * (attempt + 1))
        return 418
    except requests.RequestException as e:
        logger.warning("Cookie check request failed: %s", e)
        return 0


# ── Club group events (same cookie auth) ─────────────────
# The events pages are server-rendered for the logged-in web session:
# the club page embeds `upcomingGroupEventIds` and each event page embeds a
# `__NEXT_DATA__` JSON with the next occurrence + recurrence schedule. No
# OAuth token involved — same `_strava4_session` cookie as the leaderboard.

def _get_orion(url: str, tries: int = 3) -> requests.Response:
    """GET a page that should be the logged-in orion render.

    Strava A/B-serves the Next.js marketing shell for a share of requests;
    the orion render is small (~100KB) and embeds `upcomingGroupEventIds`,
    the shell is ~600KB without it. Retry to miss the shell."""
    for i in range(tries):
        resp = _session().get(url, timeout=20)
        if resp.status_code == 200 and "/login" not in resp.url:
            big_or_shell = len(resp.text) > 300_000 and "upcomingGroupEventIds" not in html.unescape(resp.text)
            if not big_or_shell:
                return resp
        time.sleep(2 * (i + 1))
    return resp


def fetch_group_event_ids(club_id: int) -> list[str]:
    """IDs of upcoming group events from the club page SSR, newest output."""
    resp = _get_orion(f"https://www.strava.com/clubs/{club_id}")
    if resp.status_code != 200 or "/login" in resp.url:
        raise RuntimeError(f"Club page returned HTTP {resp.status_code} (or session expired)")
    text = html.unescape(resp.text)
    m = re.search(r'"upcomingGroupEventIds"\s*:\s*\[([0-9,\s]*)]', text)
    if not m:
        return []
    return [e for e in m.group(1).split(",") if e.strip()]


def fetch_group_event(club_id: int, event_id: str) -> dict:
    """Event detail from the event page SSR `__NEXT_DATA__` — follows 307
    redirect to the next-occurrence page. Raises RuntimeError."""
    url = f"https://www.strava.com/clubs/{club_id}/group_events/{event_id}"
    resp = _session().get(url, timeout=20, allow_redirects=False)
    # 307 → occurrence page — follow manually (allow_redirects drops Cookie)
    if resp.status_code == 307:
        loc = resp.headers.get("Location", "")
        if not loc.startswith("http"):
            loc = "https://www.strava.com" + loc
        resp = _session().get(loc, timeout=20)
    if resp.status_code != 200 or "/login" in resp.url:
        raise RuntimeError(f"Event page {url} returned HTTP {resp.status_code}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.S)
    if not m:
        raise RuntimeError(f"Event page {url}: no __NEXT_DATA__ payload")
    try:
        pp = json.loads(html.unescape(m.group(1)))["props"]["pageProps"]
    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Event page {url}: unexpected payload ({e})") from e

    # New format: occurrence page (redirect target) has eventOccurrence
    if "eventOccurrence" in pp:
        occ = pp["eventOccurrence"]
        startXY = occ.get("startXY") or {}
        return {
            "id": event_id,
            "title": occ.get("title") or "",
            "zone": occ.get("zone") or "",
            "place": occ.get("address") or "",
            "schedule": occ.get("schedule") or {},
            "occurrence_datetime": occ.get("occurrenceDateTime") or "",
            "start_lat": startXY.get("lat"),
            "start_lng": startXY.get("lng"),
        }

    # New format (fallback): event landing page has event.occurrences[]
    ev = pp.get("event") or {}
    occs = ev.get("occurrences") or []
    oc = occs[0] if occs else {}
    return {
        "id": event_id,
        "title": oc.get("title") or "",
        "zone": oc.get("zone") or "",
        "place": oc.get("address") or "",
        "schedule": oc.get("schedule") or {},
        "occurrence_datetime": oc.get("occurrenceDateTime") or "",
        "start_lat": None,
        "start_lng": None,
    }
