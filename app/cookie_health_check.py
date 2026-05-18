"""Proactive cookie health check module.

Periodically checks the Strava leaderboard endpoint (per_page=1) to detect
session cookie expiry before the weekly run. Alerts Bot Owners via Telegram DM.

State machine:
  - 200 → reset strike, clear alerting
  - 302/401 → alert immediately (definite expiry)
  - Other error → strike 1 = log; strike 2 = alert
  - Once alerting, re-alert every cycle until 200
"""
import logging

import schedule

from config import (
    COOKIE_CHECK_INTERVAL_MINUTES,
    STRAVA_SESSION_COOKIE,
    TELEGRAM_ALERT_IDS,
)
from strava_scraper import check_cookie
from telegram_client import send_message

log = logging.getLogger("cookie-health")

# Persistent state for the strike / alerting machine
_consecutive_failures = 0
_is_alerting = False


def _alert_owners(status: int) -> None:
    """Send a Telegram DM to every Bot Owner."""
    if not TELEGRAM_ALERT_IDS:
        log.warning("No TELEGRAM_ALERT_IDS configured — cannot alert")
        return

    message = (
        f"⚠️ Strava session cookie expired!\n\n"
        f"Health check returned HTTP {status}.\n"
        f"The leaderboard bot cannot fetch data until the cookie is refreshed.\n\n"
        f"Please update STRAVA_SESSION_COOKIE in .env and restart the container."
    )

    for owner_id in TELEGRAM_ALERT_IDS:
        owner_id = owner_id.strip()
        if not owner_id:
            continue
        ok = send_message(owner_id, message)
        if ok:
            log.info("Alert sent to owner %s", owner_id)
        else:
            log.error("Failed to send alert to owner %s", owner_id)


def run_health_check() -> None:
    """One health check cycle — called on schedule."""
    global _consecutive_failures, _is_alerting

    if not STRAVA_SESSION_COOKIE:
        log.warning("STRAVA_SESSION_COOKIE not set — skipping health check")
        return

    status = check_cookie()
    log.info("Cookie health check: HTTP %d", status)

    if status == 200:
        # Cookie is valid — reset everything
        if _is_alerting:
            log.info("Cookie restored — alerting stopped")
        _consecutive_failures = 0
        _is_alerting = False
        return

    # Non-200: handle by category
    if status in (302, 401):
        # Definite expiry — alert immediately (strike-capped or not)
        _consecutive_failures += 1
        if not _is_alerting:
            log.warning("Cookie expired (HTTP %d) — alerting owners", status)
            _alert_owners(status)
            _is_alerting = True
        else:
            log.warning("Cookie still expired (HTTP %d) — re-alerting owners", status)
            _alert_owners(status)
        return

    # Other error (timeout, 500, 0 = network error, etc.)
    _consecutive_failures += 1
    if _is_alerting:
        # Already in alert mode — keep notifying every cycle
        log.warning("Cookie still appears expired (HTTP %d) — re-alerting owners", status)
        _alert_owners(status)
    elif _consecutive_failures >= 2:
        # Second consecutive non-definite error — promote to alert
        log.warning(
            "Cookie check: %d consecutive failures — alerting owners",
            _consecutive_failures,
        )
        _alert_owners(status)
        _is_alerting = True
    else:
        log.warning(
            "Cookie check failed (HTTP %d) — strike %d/2",
            status,
            _consecutive_failures,
        )


def start_health_check() -> None:
    """Start the cookie health check loop. Runs immediately, then on schedule."""
    if COOKIE_CHECK_INTERVAL_MINUTES <= 0:
        log.warning("COOKIE_CHECK_INTERVAL_MINUTES is %d — health check disabled", COOKIE_CHECK_INTERVAL_MINUTES)
        return

    log.info(
        "Cookie health check: every %d minute(s)",
        COOKIE_CHECK_INTERVAL_MINUTES,
    )

    # First check immediately
    run_health_check()

    # Schedule recurring checks
    schedule.every(COOKIE_CHECK_INTERVAL_MINUTES).minutes.do(run_health_check)
    log.info("Next health check in %d minute(s)", COOKIE_CHECK_INTERVAL_MINUTES)