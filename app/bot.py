#!/usr/bin/env python3
"""
Strava Bot — Weekly Club Leaderboard
─────────────────────────────────────
Every Sunday 23:00 Budapest time:
  1. Fetches the club leaderboard via Strava's web JSON API
  2. Generates a Strava-styled PNG
  3. Saves it to leaderboard_output/
  4. Sends it to a Telegram group chat
"""
import argparse
import logging
import os
import time
from datetime import datetime

import schedule

from config import CLUB_ID, SCHEDULE_TIME, SCHEDULE_DAY, OUTPUT_DIR, STRAVA_SESSION_COOKIE, LEADERBOARD_MIN_RUNNERS, LEADERBOARD_KM_CUTOFF, LEADERBOARD_FAILURE_MESSAGE
from strava_scraper import get_leaderboard_entries
from image_generator import generate
from telegram_client import send_to_telegram, send_group_message
from cookie_health_check import start_health_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
)
log = logging.getLogger("strava-bot")


def fetch_and_save(dry_run: bool = False) -> None:
    """One full run: fetch → generate → save → (optionally) send to Telegram.

    When dry_run is True, all Telegram posting is skipped.
    """
    if not STRAVA_SESSION_COOKIE:
        log.error("STRAVA_SESSION_COOKIE is not set.")
        return

    # 1. Fetch leaderboard
    log.info("Fetching leaderboard from Strava web API …")
    # Fetch extra to ensure we capture everyone ≥ 30km
    fetch_limit = max(LEADERBOARD_MIN_RUNNERS, 50)
    try:
        entries = get_leaderboard_entries(per_page=fetch_limit)
    except RuntimeError as e:
        log.error("%s", e)
        if LEADERBOARD_FAILURE_MESSAGE:
            if dry_run:
                log.info("[DRY-RUN] Would send failure message to group chat")
            else:
                send_group_message(LEADERBOARD_FAILURE_MESSAGE)
        return

    if not entries:
        log.warning("Empty leaderboard — nothing to send")
        return

    # 2. Apply dynamic cutoff: at least N, or all ≥ cutoff km
    cutoff_m = LEADERBOARD_KM_CUTOFF * 1000
    km_cutoff_count = sum(1 for e in entries if (e.get("distance") or 0) >= cutoff_m)
    limit = max(LEADERBOARD_MIN_RUNNERS, km_cutoff_count)
    if len(entries) > limit:
        entries = entries[:limit]
        log.info("Truncated to %d rows (%d ran ≥ %dkm)", limit, km_cutoff_count, LEADERBOARD_KM_CUTOFF)

    # 2. Generate image
    log.info("%d athletes — generating image …", len(entries))
    img = generate(entries)

    # 3. Save to disk
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(OUTPUT_DIR, f"leaderboard_{date_str}.png")
    img.save(path, quality=95)
    log.info("Saved → %s (%d rows, %.1f KB)", path, len(entries), os.path.getsize(path) / 1024)

    # 4. Send to Telegram (skip in dry-run mode)
    if dry_run:
        log.info("[DRY-RUN] Skipping Telegram post — image saved locally")
    else:
        sent = send_to_telegram(path)
        if sent:
            log.info("✅ Leaderboard posted to Telegram group!")
        else:
            log.warning("⚠️ Image saved locally but Telegram send failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Strava Leaderboard Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Fetch and generate image but skip Telegram posting",
    )
    args, _ = parser.parse_known_args()

    log.info("╔══════════════════════════════════════════╗")
    log.info("║   Strava Bot  –  Weekly Leaderboard     ║")
    log.info("║   Club: БББП  #%d                 ║", CLUB_ID)
    log.info("║   Schedule: every %s at %s Budapest   ║", SCHEDULE_DAY, SCHEDULE_TIME)
    log.info("║   Telegram:  %s                    ║", "DRY-RUN" if args.dry_run else "enabled")
    log.info("╚══════════════════════════════════════════╝")

    # Start cookie health check (runs immediately + on interval)
    start_health_check()

    # First run immediately — always dry-run to avoid spam on restart
    fetch_and_save(dry_run=True)

    # Schedule weekly — respects the --dry-run flag for real runs
    getattr(schedule.every(), SCHEDULE_DAY).at(SCHEDULE_TIME).do(fetch_and_save, dry_run=args.dry_run)
    log.info("Scheduler active — next run: next %s at %s", SCHEDULE_DAY, SCHEDULE_TIME)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
