"""Strava-styled club leaderboard image — mobile-first.

Columns: Rank | Athlete | Distance | Runs | Longest | Avg Pace | Elev Gain | Time
"""
import io
import logging
import os

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Colors ──────────────────────────────────────────────
ORANGE    = "#FC4C02"
WHITE     = "#FFFFFF"
DARK      = "#1A1A1A"
LIGHT     = "#B0B0B0"
SEP       = "#EAEAEE"
ROW_ALT   = "#F5F6F8"

# ── Layout ──────────────────────────────────────────────
WIDTH     = 820
HDR       = 28
ROW       = 54
AVATAR    = 34
AV_Y      = 10          # avatar top offset in row

# Column start positions
X_RANK      = 16
X_AVATAR    = 52
X_NAME      = 98
# Use a single font for all content cells
X_DIST      = 270        # distance column start
X_RUNS      = 320
X_LONGEST   = 375
X_PACE      = 430
X_ELEV      = 490
X_TIME      = 545

# ── Fonts ───────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_cache: dict = {}

def _f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("b" if bold else "r", size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(
            os.path.join(_FONT_DIR, "NotoSans.ttf"), size
        )
    return _cache[key]

# ── Formatters ──────────────────────────────────────────
def _km(m: float) -> str:
    return f"{m/1000:.1f} km" if m > 0 else "—"
def _elv(m: float) -> str:
    return f"{int(m)} m" if m > 0 else "—"
def _pac(v: float) -> str:
    if v <= 0:
        return "—"
    s = 1000.0 / v
    return f"{int(s//60)}:{int(s%60):02d}"
def _tm(secs: int) -> str:
    if secs <= 0:
        return "—"
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ── Avatars ─────────────────────────────────────────────
def _avatar(url: str) -> Image.Image:
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        w, h = img.size
        d = min(w, h)
        img = img.crop(((w-d)//2, (h-d)//2, (w+d)//2, (h+d)//2))
        img = img.resize((AVATAR, AVATAR), Image.LANCZOS)
        mask = Image.new("L", (AVATAR, AVATAR), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, AVATAR, AVATAR), fill=255)
        out = Image.new("RGBA", (AVATAR, AVATAR), (0, 0, 0, 0))
        out.paste(img, (0, 0))
        out.putalpha(mask)
        return out
    except Exception:
        bg = Image.new("RGBA", (AVATAR, AVATAR), ORANGE)
        mask = Image.new("L", (AVATAR, AVATAR), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, AVATAR, AVATAR), fill=255)
        bg.putalpha(mask)
        return bg

# ── Build image ─────────────────────────────────────────
def generate(entries: list[dict]) -> Image.Image:
    n = len(entries)
    H = HDR + n * ROW
    img = Image.new("RGB", (WIDTH, H), WHITE)
    dr = ImageDraw.Draw(img)

    # All content text: one font, one size, one baseline
    font = _f(12)
    font_name = _f(12, True)

    # Baseline y for all text (same across columns)
    _bl = lambda ry: ry + ROW // 2 + 2   # vertical center adjusted for font

    # ── Header ──
    dr.rectangle([(0, 0), (WIDTH, HDR)], fill=ROW_ALT)
    dr.line([(0, HDR), (WIDTH, HDR)], fill=SEP, width=1)

    hf = _f(9, True)
    hy = (HDR - hf.getbbox("Ag")[3]) // 2 + 1
    dr.text((X_RANK,   hy), "#",     fill=LIGHT, font=hf)
    dr.text((X_NAME,   hy), "ATHLETE", fill=LIGHT, font=hf)
    dr.text((X_DIST,   hy), "DISTANCE", fill=LIGHT, font=hf)
    dr.text((X_RUNS,   hy), "RUNS",   fill=LIGHT, font=hf)
    dr.text((X_LONGEST,hy), "LONGEST", fill=LIGHT, font=hf)
    dr.text((X_PACE,   hy), "AVG PACE", fill=LIGHT, font=hf)
    dr.text((X_ELEV,   hy), "ELEV GAIN", fill=LIGHT, font=hf)
    dr.text((X_TIME,   hy), "TIME",   fill=LIGHT, font=hf)

    # ── Rows ──
    for i, entry in enumerate(entries):
        ry = HDR + i * ROW
        rank = i + 1
        a = entry.get("athlete", {})
        name = f"{a.get('firstname','')} {a.get('lastname','')}".strip()
        name = name or a.get("username", "---")

        if i % 2 == 1:
            dr.rectangle([(0, ry), (WIDTH, ry + ROW)], fill=ROW_ALT)

        # Rank
        rank_color = ORANGE if rank <= 3 else LIGHT
        dr.text((X_RANK, _bl(ry)), str(rank), fill=rank_color, font=font)

        # Avatar
        av = _avatar(a.get("profile") or a.get("profile_medium", ""))
        img.paste(av, (X_AVATAR, ry + AV_Y), av)

        # Name
        dr.text((X_NAME, _bl(ry)), name, fill=DARK, font=font_name)

        # Distance (orange, same font)
        dr.text((X_DIST, _bl(ry)), _km(entry.get("distance") or 0),
                fill=ORANGE, font=font)

        # Stats
        dr.text((X_RUNS,   _bl(ry)), str(int(entry.get("num_activities") or 0)),
                fill=DARK, font=font)
        dr.text((X_LONGEST, _bl(ry)), _km(entry.get("best_activities_distance") or 0),
                fill=DARK, font=font)
        dr.text((X_PACE,   _bl(ry)), _pac(entry.get("velocity") or 0),
                fill=DARK, font=font)
        dr.text((X_ELEV,   _bl(ry)), _elv(entry.get("elev_gain") or 0),
                fill=DARK, font=font)
        dr.text((X_TIME,   _bl(ry)), _tm(entry.get("moving_time") or 0),
                fill=DARK, font=font)

        dr.line([(0, ry + ROW), (WIDTH, ry + ROW)], fill=SEP, width=1)

    return img
