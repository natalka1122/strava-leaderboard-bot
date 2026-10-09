"""Render the weekly leaderboard GIF from recorded snapshots.

Reads the append-only history written by ``leaderboard_history``, keeps one
Strava week, freezes the roster to the week's final snapshot set -- top
``LEADERBOARD_MIN_RUNNERS`` or everyone at/above ``LEADERBOARD_KM_CUTOFF`` km
-- and renders one table frame per snapshot.

Output is a GIF next to the weekly leaderboard PNG. Nothing is posted to
Telegram. Visual style matches ``image_generator`` (variant A of the
2026-10-08 prototype): header bar, alternating rows, orange ranks, initials
avatars.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import (
    LEADERBOARD_GIF_ENABLED,
    LEADERBOARD_KM_CUTOFF,
    LEADERBOARD_MIN_RUNNERS,
    OUTPUT_DIR,
)
from leaderboard_history import load_snapshots

log = logging.getLogger("leaderboard-gif")

ORANGE = "#FC4C02"
WHITE = "#FFFFFF"
DARK = "#1A1A1A"
LIGHT = "#B0B0B0"
SEP = "#EAEAEE"
ROW_ALT = "#F5F6F8"
TITLE = "CLUB LEADERBOARD - THIS WEEK"
PLACEHOLDER = "-"
TOP_RANKS = 3
AVATAR_COLORS = (
    "#7B8CDE",
    "#5BA37D",
    "#C97B4A",
    "#8E6BB5",
    "#4A90A4",
    "#B5546B",
    "#6B8E4A",
    "#A47B4A",
    "#5A5F8E",
    "#4A8E7B",
)

WIDTH = 720
HEADER_H = 30
ROW_H = 40
AVATAR_R = 15
MIN_SNAPSHOTS = 2
MAX_FRAMES = 56
GIF_WIDTH = 600
FRAME_MS = 170
FONT_FILE = Path(__file__).resolve().parent / "fonts" / "NotoSans.ttf"

_fonts: dict = {}


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("b" if bold else "r", size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_FILE), size)
    return _fonts[key]


def _timestamp(snapshot: dict) -> datetime | None:
    if not isinstance(snapshot, dict):
        return None
    stamp = snapshot.get("ts")
    if not isinstance(stamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def _week_start(now: datetime) -> datetime:
    """Monday 00:00 local time for the week containing ``now``."""
    local = now.astimezone()
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=local.weekday())


def _roster(entries: list[dict]) -> list[dict]:
    """Freeze the display set: top N, or everyone at/above the km cutoff."""
    ordered = sorted(entries, key=lambda item: -(item.get("distance") or 0))
    cutoff = LEADERBOARD_KM_CUTOFF * 1000
    above = sum(
        1 for entry in ordered if (entry.get("distance") or 0) >= cutoff
    )
    keep = max(LEADERBOARD_MIN_RUNNERS, above)

    roster = []
    for entry in ordered[:keep]:
        name = (
            f"{entry.get('firstname', '')} {entry.get('lastname', '')}".strip()
            or PLACEHOLDER
        )
        parts = [part for part in name.split() if part[:1].isalpha()]
        if not parts:
            source = PLACEHOLDER
        elif len(parts) == 1:
            source = parts[0][:2]
        else:
            source = parts[0][0] + parts[-1][0]
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
        slot = int(digest, 16) % len(AVATAR_COLORS)
        roster.append(
            {
                "id": entry.get("id"),
                "name": name,
                "initials": source.upper(),
                "color": AVATAR_COLORS[slot],
            }
        )
    return roster


def render_frame(rows: list[dict], when: datetime) -> Image.Image:
    """One table frame in the house leaderboard style."""
    height = HEADER_H + len(rows) * ROW_H
    img = Image.new("RGB", (WIDTH, height), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (WIDTH, HEADER_H)], fill=ROW_ALT)
    draw.text(
        (16, HEADER_H // 2),
        TITLE,
        font=_font(11, bold=True),
        fill=LIGHT,
        anchor="lm",
    )
    draw.text(
        (WIDTH - 16, HEADER_H // 2),
        when.astimezone().strftime("%a %H:%M"),
        font=_font(11, bold=True),
        fill=LIGHT,
        anchor="rm",
    )
    draw.line([(0, HEADER_H), (WIDTH, HEADER_H)], fill=SEP)

    for index, row in enumerate(rows):
        top = HEADER_H + index * ROW_H
        mid = top + ROW_H // 2
        if index % 2:
            draw.rectangle([(0, top), (WIDTH, top + ROW_H)], fill=ROW_ALT)
        rank_color = ORANGE if row["rank"] <= TOP_RANKS else LIGHT
        draw.text(
            (24, mid),
            str(row["rank"]),
            font=_font(15, bold=True),
            fill=rank_color,
            anchor="lm",
        )
        draw.ellipse(
            [(58 - AVATAR_R, mid - AVATAR_R), (58 + AVATAR_R, mid + AVATAR_R)],
            fill=row["color"],
        )
        draw.text(
            (58, mid),
            row["initials"],
            font=_font(12, bold=True),
            fill=WHITE,
            anchor="mm",
        )
        draw.text(
            (84, mid),
            row["name"],
            font=_font(15, bold=True),
            fill=DARK,
            anchor="lm",
        )
        draw.text(
            (WIDTH - 70, mid),
            f"{row['distance'] / 1000:.1f}km",
            font=_font(15, bold=True),
            fill=ORANGE,
            anchor="rm",
        )
        draw.text(
            (WIDTH - 18, mid),
            f"{row['runs']}x",
            font=_font(11),
            fill=LIGHT,
            anchor="rm",
        )
        draw.line([(0, top + ROW_H), (WIDTH, top + ROW_H)], fill=SEP)
    return img


def build_frames(
    snapshots: list[dict], now: datetime
) -> list[tuple[datetime, list[dict]]]:
    """Frames for the week containing ``now``, roster-frozen and ranked."""
    start = _week_start(now)
    dated = sorted(
        (stamp, snap)
        for snap in snapshots
        if (stamp := _timestamp(snap)) is not None and start <= stamp <= now
    )
    if len(dated) < MIN_SNAPSHOTS:
        return []

    roster = _roster(dated[-1][1]["entries"])
    frames = []
    for stamp, snap in dated:
        live = {entry.get("id"): entry for entry in snap["entries"]}
        rows = [
            {
                "name": member["name"],
                "initials": member["initials"],
                "color": member["color"],
                "distance": (live.get(member["id"]) or {}).get("distance") or 0,
                "runs": (live.get(member["id"]) or {}).get("num_activities")
                or 0,
            }
            for member in roster
        ]
        rows.sort(key=lambda item: (-item["distance"], item["name"]))
        for position, row in enumerate(rows):
            row["rank"] = position + 1
        frames.append((stamp, rows))

    if len(frames) > MAX_FRAMES:
        stride = len(frames) // MAX_FRAMES
        frames = frames[::stride]
    return frames


def generate_weekly_gif(now: datetime | None = None) -> Path | None:
    """Build the week's GIF. Returns the path, or None when skipped."""
    if not LEADERBOARD_GIF_ENABLED:
        log.info("GIF: disabled via LEADERBOARD_GIF_ENABLED")
        return None
    moment = now or datetime.now().astimezone()
    if moment.tzinfo is None:
        moment = moment.astimezone()

    frames = build_frames(load_snapshots(), moment)
    if len(frames) < MIN_SNAPSHOTS:
        log.warning(
            "GIF: %d frame(s) this week - nothing to render", len(frames)
        )
        return None

    ratio = GIF_WIDTH / WIDTH
    images = [
        render_frame(rows, stamp).resize(
            (GIF_WIDTH, round((HEADER_H + len(rows) * ROW_H) * ratio)),
            Image.Resampling.LANCZOS,
        )
        for stamp, rows in frames
    ]
    palette = [
        image.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
        for image in images
    ]
    path = Path(OUTPUT_DIR) / f"leaderboard_{moment:%Y-%m-%d}.gif"
    path.parent.mkdir(parents=True, exist_ok=True)
    palette[0].save(
        path,
        save_all=True,
        append_images=palette[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
    )
    log.info(
        "GIF: wrote %s (%d frames, %.0f KB)",
        path,
        len(frames),
        path.stat().st_size / 1024,
    )
    return path
