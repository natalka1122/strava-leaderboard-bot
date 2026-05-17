"""Strava-styled club leaderboard image — mobile-first.

Columns: Rank | Athlete | Distance | Runs | Longest | Avg Pace | Elev Gain | Time
Distance column highlighted with orange background.
"""
import io
import logging
import os

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# ── Colors ──────────────────────────────────────────────
ORANGE        = "#FC4C02"
ORANGE_BG     = "#FFF3E8"
WHITE         = "#FFFFFF"
DARK          = "#1A1A1A"
MEDIUM        = "#4A4A4A"
LIGHT_GREY    = "#B0B0B0"
SEPARATOR     = "#E5E5E5"
ROW_ALT       = "#F7F8FA"
MEDAL_GOLD    = "#FFB800"
MEDAL_SILVER  = "#A0B0C0"
MEDAL_BRONZE  = "#C88A5E"

# ── Layout ──────────────────────────────────────────────
WIDTH         = 820
HEADER_H      = 32
ROW_H         = 68
AVATAR        = 46           # avatar diameter
AVATAR_PAD    = 11           # avatar top padding within row

# Column x-positions
X_RANK        = 16
X_AVATAR      = 56
X_NAME        = 110
X_DIST_START  = 232
X_DIST_END    = 310          # 78px orange band  
X_DIST_CTR    = (X_DIST_START + X_DIST_END) // 2  # center = 271
X_RUNS        = 365
X_LONGEST     = 435
X_PACE        = 510
X_ELEV        = 590
X_TIME        = 670

# ── Fonts ───────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_font_cache: dict[(str, int), ImageFont.FreeTypeFont] = {}

def _f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("b" if bold else "r", size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(_FONT_DIR, "NotoSans.ttf"), size)
    return _font_cache[key]

# ── Formatters ──────────────────────────────────────────
def _km(meters: float) -> str:
    if meters <= 0:
        return "—"
    return f"{meters/1000:.1f}km"

def _elev(meters: float) -> str:
    if meters <= 0:
        return "—"
    return f"{int(meters)}m"

def _pace(m_per_s: float) -> str:
    if m_per_s <= 0:
        return "—"
    s = 1000.0 / m_per_s
    return f"{int(s//60)}:{int(s%60):02d}"

def _time(secs: int) -> str:
    if secs <= 0:
        return "—"
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ── Avatars ─────────────────────────────────────────────
def _avatar(url: str) -> Image.Image:
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        w, h = img.size
        d = min(w, h)
        img = img.crop(((w-d)//2, (h-d)//2, w-d//2, h-d//2))
        img = img.resize((AVATAR, AVATAR), Image.LANCZOS)
        return _circle(img)
    except Exception:
        return _placeholder()

def _circle(img: Image.Image) -> Image.Image:
    mask = Image.new("L", (AVATAR, AVATAR), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR, AVATAR), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(0.5))
    out = Image.new("RGBA", (AVATAR, AVATAR), (0, 0, 0, 0))
    out.paste(img, (0, 0))
    out.putalpha(mask)
    return out

def _placeholder() -> Image.Image:
    img = Image.new("RGBA", (AVATAR, AVATAR), ORANGE)
    return _circle(img)

# ── Medal badge ────────────────────────────────────────
_MEDALS = {1: MEDAL_GOLD, 2: MEDAL_SILVER, 3: MEDAL_BRONZE}

def _medal(draw: ImageDraw, rank: int, cx: int, cy: int) -> None:
    color = _MEDALS[rank]
    # Outer circle + inner text
    r = 14
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color)
    txt = str(rank)
    bb = draw.textbbox((0, 0), txt, font=_f(12, True))
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((cx-tw/2, cy-th/2), txt, fill=WHITE, font=_f(12, True))

def _rank(draw: ImageDraw, rank: int, cx: int, cy: int) -> None:
    r = 9
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=ROW_ALT)
    txt = str(rank)
    bb = draw.textbbox((0, 0), txt, font=_f(10))
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((cx-tw/2, cy-th/2), txt, fill=LIGHT_GREY, font=_f(10))

# ── Build image ────────────────────────────────────────
def generate(entries: list[dict]) -> Image.Image:
    n = len(entries)
    H = HEADER_H + n * ROW_H
    img = Image.new("RGB", (WIDTH, H), WHITE)
    dr = ImageDraw.Draw(img)

    # ── Header ──
    dr.rectangle([(0, 0), (WIDTH, HEADER_H)], fill=ROW_ALT)
    dr.line([(0, HEADER_H), (WIDTH, HEADER_H)], fill=SEPARATOR, width=1)

    lf = _f(9, True)
    hy = (HEADER_H - _f(9).getbbox("Ag")[3]) // 2 + 2
    dr.text((X_NAME,   hy), "ATHLETE",   fill=LIGHT_GREY, font=lf)
    dr.text((X_DIST_START+4, hy), "DISTANCE", fill=ORANGE, font=lf)
    dr.text((X_RUNS,   hy), "RUNS",      fill=LIGHT_GREY, font=lf)
    dr.text((X_LONGEST,hy), "LONGEST",   fill=LIGHT_GREY, font=lf)
    dr.text((X_PACE,   hy), "AVG PACE",  fill=LIGHT_GREY, font=lf)
    dr.text((X_ELEV,   hy), "ELEV GAIN", fill=LIGHT_GREY, font=lf)
    dr.text((X_TIME,   hy), "TIME",      fill=LIGHT_GREY, font=lf)

    # ── Rows ──
    fn = _f(13, True)
    fs = _f(11)
    fd = _f(15, True)

    for i, entry in enumerate(entries):
        ry = HEADER_H + i * ROW_H
        rank = i + 1
        a = entry.get("athlete", {})
        name = f"{a.get('firstname','')} {a.get('lastname','')}".strip() or a.get("username","---")

        # Alternate row
        if i % 2 == 1:
            dr.rectangle([(0, ry), (WIDTH, ry+ROW_H)], fill=ROW_ALT)

        # Distance band
        dr.rounded_rectangle([X_DIST_START, ry+8, X_DIST_END, ry+ROW_H-8],
                             radius=6, fill=ORANGE_BG)

        # Rank
        if rank <= 3:
            _medal(dr, rank, X_RANK+10, ry+ROW_H//2)
        else:
            _rank(dr, rank, X_RANK+10, ry+ROW_H//2)

        # Avatar
        av = _avatar(a.get("profile") or a.get("profile_medium", ""))
        img.paste(av, (X_AVATAR, ry+AVATAR_PAD), av)

        # Name
        dr.text((X_NAME, ry+ROW_H//2-7), name, fill=DARK, font=fn)

        # Distance
        dt = _km(entry.get("distance") or 0)
        tw = dr.textlength(dt, font=fd)
        dr.text((X_DIST_CTR-tw/2, ry+ROW_H//2-9), dt, fill=ORANGE, font=fd)

        # Stats (bottom row of row)
        sy = ry + ROW_H - 18
        dr.text((X_RUNS,   sy), str(int(entry.get("num_activities") or 0)), fill=MEDIUM, font=fs)
        dr.text((X_LONGEST,sy), _km(entry.get("best_activities_distance") or 0), fill=MEDIUM, font=fs)
        dr.text((X_PACE,   sy), _pace(entry.get("velocity") or 0),             fill=MEDIUM, font=fs)
        dr.text((X_ELEV,   sy), _elev(entry.get("elev_gain") or 0),            fill=MEDIUM, font=fs)
        dr.text((X_TIME,   sy), _time(entry.get("moving_time") or 0),           fill=MEDIUM, font=fs)

        # Separator
        dr.line([(0, ry+ROW_H), (WIDTH, ry+ROW_H)], fill=SEPARATOR, width=1)

    return img
