"""Append-only snapshots of the club leaderboard for the weekly GIF.

Rides the same 3h cadence as the cookie health check: each tick fetches the
full leaderboard and appends one JSON line to ``leaderboard_history.jsonl``.
Raw rows are stored without the display cutoff so the renderer can freeze the
week's roster later. Failures log only — owner alerting belongs to the health
check.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import (
    HISTORY_RETENTION_DAYS,
    LEADERBOARD_HISTORY_ENABLED,
    LEADERBOARD_MIN_RUNNERS,
    OUTPUT_DIR,
)
from strava_scraper import get_leaderboard_entries

log = logging.getLogger("leaderboard-history")

HISTORY_FILENAME = "leaderboard_history.jsonl"
ENCODING = "utf-8"
DEFAULT_FETCH_LIMIT = 50
FETCH_LIMIT = max(LEADERBOARD_MIN_RUNNERS, DEFAULT_FETCH_LIMIT)


def history_path() -> Path:
    """Return the snapshot file path (indirection keeps tests simple)."""
    return Path(OUTPUT_DIR) / HISTORY_FILENAME


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _slim_entry(entry: dict) -> dict:
    """Reduce an API row to the fields the GIF renderer needs."""
    athlete = entry.get("athlete", {})
    return {
        "id": athlete.get("id"),
        "firstname": athlete.get("firstname", ""),
        "lastname": athlete.get("lastname", ""),
        "distance": entry.get("distance") or 0,
        "rank": entry.get("rank"),
        "num_activities": entry.get("num_activities"),
        "profile": athlete.get("profile")
        or athlete.get("profile_medium")
        or "",
    }


def _read_snapshot(line: str) -> tuple[dict, datetime] | None:
    """Parse one JSONL line into (snapshot, timestamp), or None if unusable."""
    try:
        snapshot = json.loads(line)
    except json.JSONDecodeError:
        return None
    stamp = snapshot.get("ts") if isinstance(snapshot, dict) else None
    if not isinstance(stamp, str):
        return None
    try:
        when = _as_utc(datetime.fromisoformat(stamp))
    except ValueError:
        return None
    return snapshot, when


def record_snapshot(now: datetime | None = None) -> bool:
    """Fetch the leaderboard and append one snapshot.

    Returns True when a snapshot was written.
    """
    if not LEADERBOARD_HISTORY_ENABLED:
        return False
    try:
        entries = get_leaderboard_entries(per_page=FETCH_LIMIT)
    except Exception as exc:  # a fetch failure must never crash the scheduler
        log.warning("History: leaderboard fetch failed: %s", exc)
        return False
    if not entries:
        log.warning("History: empty leaderboard — no snapshot written")
        return False

    payload = {
        "ts": _as_utc(now or datetime.now(timezone.utc)).isoformat(),
        "entries": [_slim_entry(entry) for entry in entries],
    }
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding=ENCODING) as stream:
        stream.write(f"{json.dumps(payload, ensure_ascii=False)}\n")
    log.info("History: recorded %d rows → %s", len(entries), path)
    prune(now)
    return True


def prune(now: datetime | None = None) -> int:
    """Drop snapshots older than the retention window; return rows removed."""
    path = history_path()
    if not path.exists():
        return 0
    cutoff = _as_utc(now or datetime.now(timezone.utc)) - timedelta(
        days=HISTORY_RETENTION_DAYS
    )
    lines = path.read_text(encoding=ENCODING).splitlines()
    kept = [
        line
        for line in lines
        if (read := _read_snapshot(line)) is not None and read[1] >= cutoff
    ]
    removed = len(lines) - len(kept)
    if removed:
        path.write_text("".join(f"{row}\n" for row in kept), encoding=ENCODING)
        log.info("History: pruned %d old snapshot(s)", removed)
    return removed


def load_snapshots() -> list[dict]:
    """Return all readable snapshots in file order (malformed lines skipped)."""
    path = history_path()
    if not path.exists():
        return []
    return [
        read[0]
        for line in path.read_text(encoding=ENCODING).splitlines()
        if (read := _read_snapshot(line)) is not None
    ]
