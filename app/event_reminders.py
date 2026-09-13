"""Club event reminders.

Every health-check cycle, list club group events from the Strava v3 API and
post a Reminder Card to the Event Reminder Thread when an occurrence enters a
Reminder Window (lead L fires while remaining time is in (L-1 days, L days]).
A missed window never fires late; the Reminder State File dedupes per
(event, occurrence, lead).
"""
import json
import logging
import os
import random
from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from config import (
    EVENT_PHOTOS_DIR,
    EVENT_REMINDER_CAPTION,
    EVENT_REMINDER_LEAD_DAYS,
    EVENT_REMINDER_THREAD_ID,
    EVENTS_CLUB_ID,
    OUTPUT_DIR,
    STRAVA_SESSION_COOKIE,
)
from image_generator import _font
from strava_scraper import _session
from telegram_client import send_to_telegram

log = logging.getLogger("event-reminders")

STATE_FILE = os.path.join(OUTPUT_DIR, "event_reminder_state.json")

WEEKDAYS_RU = (
    "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ",
    "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ",
)
_IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


# ── Fetch ───────────────────────────────────────────────
def get_group_events() -> list[dict]:
    """List club group events from Strava v3 (bare JSON array)."""
    url = f"https://www.strava.com/api/v3/clubs/{EVENTS_CLUB_ID}/group_events"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.strava.com/clubs/{EVENTS_CLUB_ID}/events",
    }
    resp = _session().get(url, params={"upcoming": "true"}, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Group events returned HTTP {resp.status_code}")
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected group events response: {type(data).__name__}")
    return data


def _parse_occurrences(event: dict) -> list[datetime]:
    """UTC aware datetimes from `upcoming_occurrences`; malformed entries skipped."""
    out = []
    for s in event.get("upcoming_occurrences") or []:
        try:
            out.append(datetime.fromisoformat(str(s).replace("Z", "+00:00")))
        except ValueError:
            log.warning("Bad occurrence datetime %r for event %s", s, event.get("id"))
    return out


# ── Lead windows ────────────────────────────────────────
def firing_leads(now: datetime, occurrence: datetime, lead_days: list[int]) -> list[int]:
    """Lead values whose window (L-1 days, L days] contains the remaining time.

    Called at the first check inside the window, so a lead fires exactly once
    per occurrence; a window that passes between checks never fires late.
    """
    remaining = (occurrence - now).total_seconds() / 86400.0
    return [L for L in lead_days if (L - 1) < remaining <= L]


# ── Reminder state ─────────────────────────────────────
def load_state(now: datetime) -> list[dict]:
    """Posted (event, occurrence, lead) entries; prunes already-passed occurrences."""
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE) as f:
            rows = json.load(f)
    except (json.JSONDecodeError, OSError):
        log.warning("Reminder state file unreadable — starting fresh")
        return []
    live = []
    for r in rows:
        try:
            occ = datetime.fromisoformat(str(r["occurrence"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if occ > now:
            live.append(r)
    return live


def save_state(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def is_posted(rows: list[dict], event_id, occurrence: datetime, lead: int) -> bool:
    key = (str(event_id), occurrence.isoformat(), lead)
    return any((r.get("event_id"), r.get("occurrence"), r.get("lead")) == key for r in rows)


# ── Photo pool ──────────────────────────────────────────
def photo_pool() -> list[str]:
    if not os.path.isdir(EVENT_PHOTOS_DIR):
        return []
    return sorted(n for n in os.listdir(EVENT_PHOTOS_DIR) if n.lower().endswith(_IMG_EXTS))


def pick_photo(pool: list[str], occurrence: datetime) -> str:
    """Occurrence-seeded pick: same photo for every lead of one occurrence,
    restart-stable, different across occurrences."""
    return random.Random(occurrence.isoformat()).choice(pool)


# ── Card ────────────────────────────────────────────────
def build_reminder_card(photo_path: str, event: dict, occurrence: datetime) -> Image.Image:
    """Photo with title / weekday+time / place overlaid.

    Minimal default layout — the photo workstream owns the styling seam here.
    """
    img = Image.open(photo_path).convert("RGB")
    w, h = img.size
    if w > 1600:  # telegram-friendly
        img = img.resize((1600, int(h * 1600 / w)), Image.Resampling.LANCZOS)
        w, h = img.size

    zone = event.get("zone")
    tz: tzinfo = timezone.utc
    if isinstance(zone, str) and zone:
        try:
            tz = ZoneInfo(zone)
        except Exception:
            tz = timezone.utc
    local = occurrence.astimezone(tz)

    title = str(event.get("title") or "").strip() or "Мероприятие клуба"
    when = f"{WEEKDAYS_RU[local.weekday()]}, {local.hour}:{local.minute:02d}"
    place = event.get("place") or ""
    place_name = place.get("name") if isinstance(place, dict) else place
    if place_name:
        when += " · " + str(place_name)

    pad = max(20, w // 30)
    title_size = max(28, w // 28)
    meta_size = max(22, w // 40)
    banner_h = pad * 2 + title_size + 8 + meta_size

    overlay = Image.new("RGBA", (w, banner_h), (0, 0, 0, 160))
    img.paste(overlay, (0, h - banner_h), overlay)
    dr = ImageDraw.Draw(img)
    dr.text((pad, h - banner_h + pad), title, fill=(255, 255, 255), font=_font(title_size, bold=True))
    dr.text((pad, h - banner_h + pad + title_size + 8), when, fill=(255, 200, 120), font=_font(meta_size))
    return img


# ── Run ─────────────────────────────────────────────────
def _post(event: dict, occurrence: datetime, lead: int, dry_run: bool, rows: list[dict]) -> bool:
    """Build + send one reminder. Returns True when state should be marked."""
    ev_id = event.get("id")
    pool = photo_pool()
    if not pool:
        log.warning("EVENT_PHOTOS_DIR empty/unreadable (%s) — skipped reminder for event %s, lead %dd",
                    EVENT_PHOTOS_DIR, ev_id, lead)
        return False

    photo = os.path.join(EVENT_PHOTOS_DIR, pick_photo(pool, occurrence))
    card = build_reminder_card(photo, event, occurrence)

    stamp = occurrence.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(OUTPUT_DIR, f"reminder_{ev_id}_{stamp}_{lead}d.png")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    card.save(path)
    log.info("Reminder for event %s, lead %dd, occurrence %s → %s",
             ev_id, lead, occurrence.isoformat(), path)

    if dry_run:
        log.info("[DRY-RUN] Would post to Telegram thread %s", EVENT_REMINDER_THREAD_ID or "main")
        return False

    if send_to_telegram(path, caption=EVENT_REMINDER_CAPTION, thread_id=EVENT_REMINDER_THREAD_ID):
        log.info("✅ Reminder posted for event %s (lead %dd)", ev_id, lead)
        rows.append({"event_id": str(ev_id), "occurrence": occurrence.isoformat(), "lead": lead})
        return True
    log.warning("Reminder send failed — retrying next cycle if still inside window")
    return False


def run_event_reminders(dry_run: bool = False) -> None:
    """One reminder cycle — called on the health-check cadence."""
    if not STRAVA_SESSION_COOKIE:
        log.warning("STRAVA_SESSION_COOKIE not set — skipping event reminders")
        return
    if not EVENT_REMINDER_LEAD_DAYS:
        log.info("EVENT_REMINDER_LEAD_DAYS not set — event reminders disabled")
        return

    try:
        events = get_group_events()
    except RuntimeError as e:
        log.warning("Event reminder fetch failed: %s — skipping this cycle", e)
        return

    now = datetime.now(timezone.utc)
    rows = load_state(now)
    dirty = False
    for ev in events:
        for occ in _parse_occurrences(ev):
            if occ <= now:
                continue  # already due/passed — lead missed, never fires late
            for lead in firing_leads(now, occ, EVENT_REMINDER_LEAD_DAYS):
                if is_posted(rows, ev.get("id"), occ, lead):
                    continue
                dirty = _post(ev, occ, lead, dry_run, rows) or dirty
    if dirty:
        save_state(rows)