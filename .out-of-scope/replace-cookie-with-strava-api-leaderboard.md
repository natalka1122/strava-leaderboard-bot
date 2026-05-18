# Strava API cannot replace cookie-based leaderboard

**Date:** 2026-05-18
**Issue:** [#7](https://github.com/natalka1122/strava-leaderboard-bot/issues/7)

## Summary

Full OAuth 2.0 integration with the Strava API was tested. The `GET /clubs/{id}/activities` endpoint returns ClubActivity objects that **lack**:

- `start_date` / `start_date_local` — can't filter activities by week
- `athlete.id` — can't uniquely identify athletes (uses `firstname`/`lastname` only)

The `/athletes/{id}/stats` endpoint is also not viable — it returns 403 Forbidden for arbitrary athletes; only the authenticated OAuth owner's stats are accessible.

## Conclusion

The official Strava API v3 does not provide enough data to build a weekly club leaderboard. The cookie-based web scraping approach remains the only viable method.

## What we built instead

The OAuth module (`app/strava_api_prototype/strava_oauth.py`) can still be used for issue #6 (cookie expiry detection via `/athlete` endpoint health check).