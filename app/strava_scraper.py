"""Fetch Strava club leaderboard from the web JSON API.

Only needs a valid _strava4_session cookie (refresh every ~2-4 weeks).
Passes ALL fields from the API response to the image generator.
"""
import logging
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
        s.cookies.set("_strava4_session", STRAVA_SESSION_COOKIE, domain=".strava.com")
    return s


def get_leaderboard_entries(per_page: int = 20) -> list[dict]:
    url = f"https://www.strava.com/clubs/{CLUB_ID}/leaderboard"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": url,
    }

    logger.info("Fetching leaderboard from Strava web JSON API…")
    resp = _session().get(
        url, params={"per_page": per_page, "page": 1}, headers=headers,
    )

    if resp.status_code != 200:
        logger.error("Web API returned HTTP %d", resp.status_code)
        raise RuntimeError(f"Leaderboard returned HTTP {resp.status_code}")

    data = resp.json()
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
