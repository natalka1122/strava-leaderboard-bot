"""Club event reminders.

Every health-check cycle, scrape the club's upcoming group events from the
Strava web pages (same `_strava4_session` cookie as the leaderboard — no
OAuth) and post a Reminder Card to the Event Reminder Thread when an
occurrence enters a Reminder Window (lead L fires while remaining time is in
(L-1 days, L days]). A missed window never fires late; the Reminder State
File dedupes per (event, occurrence, lead).
"""
import json
import logging
import os
import random
from datetime import datetime, timezone, timedelta, tzinfo
from urllib.parse import quote
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
from strava_scraper import fetch_group_event, fetch_group_event_ids
from telegram_client import send_to_telegram

log = logging.getLogger("event-reminders")

STATE_FILE = os.path.join(OUTPUT_DIR, "event_reminder_state.json")

WEEKDAYS_RU = (
    "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ",
    "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ",
)
MONTHS_RU = (
    "января", "февраля", "марта", "апреля",
    "мая", "июня", "июля", "августа",
    "сентября", "октября", "ноября", "декабря",
)
_IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


# ── Fetch + occurrence expansion ───────────────────────
def get_group_events() -> list[dict]:
    """Club group events with computed future occurrences.

    Cookie-based SSR scrape (same pattern as the leaderboard): club page
    yields upcoming event ids, each event page yields its next occurrence
    plus recurrence schedule. Occurrences are expanded from the rule.
    """
    ids = fetch_group_event_ids(EVENTS_CLUB_ID)
    events = []
    for ev_id in ids:
        try:
            events.append(fetch_group_event(EVENTS_CLUB_ID, ev_id))
        except RuntimeError as e:
            log.warning("Skipping event %s: %s", ev_id, e)
    return events


_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}


def _ordinal_in_month(d: datetime) -> int:
    """1-based occurrence number of d's weekday inside its month (1..5)."""
    return (d.day - 1) // 7 + 1


def _in_month_aligned(d: datetime, start: datetime, interval: int) -> bool:
    """True when d's month matches start's month stepped by `interval`."""
    months = (d.year - start.year) * 12 + (d.month - start.month)
    return months >= 0 and months % interval == 0


def expand_occurrences(event: dict, now: datetime, horizon_days: int) -> list[datetime]:
    """Future occurrence datetimes of an event (timezone-aware, local zone).

    Uses the next occurrence (`occurrence_datetime`, as the site serves it)
    as the first candidate; later occurrences are computed from the
    recurrence schedule (weekly / monthly ordinals). A schedule we don't
    understand degrades to the single served occurrence.
    """
    zone = event.get("zone") or "UTC"
    tz: tzinfo = timezone.utc
    try:
        tz = ZoneInfo(zone)
    except Exception:
        tz = timezone.utc

    def parse(s: str) -> datetime:
        return datetime.fromisoformat(s).replace(tzinfo=tz)

    try:
        served = parse(event["occurrence_datetime"])
    except (KeyError, ValueError):
        return []

    rule = (event.get("schedule") or {}).get("recurrenceRule") or {}
    freq = (rule.get("frequency") or "").lower()
    interval = int(rule.get("interval") or 1) or 1
    days = rule.get("days") or []
    ords = rule.get("ordinals") or []

    if freq not in ("weekly", "monthly"):
        # one-shot / unknown rule: keep the served next occurrence only
        return [served] if served > now else []

    try:
        start = parse(event["schedule"]["startTime"])
    except (KeyError, ValueError):
        start = served

    horizon = now + timedelta(days=horizon_days)
    day_idx = {_WEEKDAYS[d.lower()] for d in days if d.lower() in _WEEKDAYS}
    ords_n = {_ORDINALS[o.lower()] for o in ords if o.lower() in _ORDINALS}
    has_last = any(o.lower() == "last" for o in ords)

    out = []
    guard = 0
    d = start
    while d <= horizon and guard < 600:
        guard += 1
        if freq == "weekly":
            from_start = (d.date() - start.date()).days
            phase_ok = from_start >= 0 and (interval == 1 or from_start % (7 * interval) == 0)
            if d.weekday() in day_idx and phase_ok:
                out.append(d)
        else:  # monthly
            nth = _ordinal_in_month(d)
            last_wd = d.day + 7 > _days_in_month(d)
            ordinal_ok = (nth in ords_n and d.weekday() in day_idx) or (has_last and last_wd and d.weekday() in day_idx)
            if ordinal_ok and _in_month_aligned(d, start, interval):
                out.append(d)
        d += timedelta(days=1)

    # the site's served next occurrence is authoritative; rule expansion is
    # a substitute for the future-dates list — keep expansions from served on
    result = {o for o in out if o > now and o >= served}
    if served > now:
        result.add(served)
    return sorted(result)


def _days_in_month(d: datetime) -> int:
    if d.month == 12:
        return 31
    return (d.replace(month=d.month + 1, day=1) - timedelta(days=1)).day


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


# ── Caption ─────────────────────────────────────────────
def build_maps_url(event: dict) -> str:
    """Google Maps link for the event start location."""
    lat = event.get("start_lat")
    lng = event.get("start_lng")
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    place = event.get("place") or ""
    return f"https://www.google.com/maps/search/?api=1&query={quote(str(place))}"


def build_caption(event: dict, occurrence: datetime) -> str:
    """Telegram caption with date, time, place, and maps link."""
    zone = event.get("zone")
    tz: tzinfo = timezone.utc
    if isinstance(zone, str) and zone:
        try:
            tz = ZoneInfo(zone)
        except Exception:
            tz = timezone.utc
    local = occurrence.astimezone(tz)
    wd = WEEKDAYS_RU[local.weekday()]
    d = local.day
    m = MONTHS_RU[local.month - 1]
    hhmm = f"{local.hour}:{local.minute:02d}"

    place = event.get("place") or ""
    maps_url = build_maps_url(event)

    lines = [
        EVENT_REMINDER_CAPTION,
        "",
        f"{wd}, {d} {m}, {hhmm}",
    ]
    if place:
        lines.append(f'📍 <a href="{maps_url}">{place}</a>')
    else:
        lines.append(f"📍 {maps_url}")
    event_url = f"https://www.strava.com/clubs/{EVENTS_CLUB_ID}/group_events/{event['id']}"
    lines.append(f'🔗 <a href="{event_url}">Strava</a>')
    return "\n".join(lines)


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

    if send_to_telegram(path, caption=build_caption(event, occurrence), thread_id=EVENT_REMINDER_THREAD_ID):
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

    now = datetime.now(timezone.utc)
    try:
        events = get_group_events()
    except RuntimeError as e:
        log.warning("Event reminder fetch failed: %s — skipping this cycle", e)
        return

    horizon = max(EVENT_REMINDER_LEAD_DAYS) + 1
    rows = load_state(now)
    dirty = False
    for ev in events:
        for occ in expand_occurrences(ev, now, horizon):
            if occ <= now:
                continue  # already due/passed — lead missed, never fires late
            for lead in firing_leads(now, occ, EVENT_REMINDER_LEAD_DAYS):
                if is_posted(rows, ev.get("id"), occ, lead):
                    log.info("Reminder for event %s lead %dd already posted — skipping", ev.get("id"), lead)
                    continue
                dirty = _post(ev, occ, lead, dry_run, rows) or dirty
    if dirty:
        save_state(rows)
