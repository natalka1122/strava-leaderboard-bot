"""Strava-styled club leaderboard image.

Columns: Rank | Athlete | Distance | Runs | Longest | Avg Pace | Elev Gain
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
AVATAR    = 38

# 5 stat columns share equal width, filling to 820px
COL = {
    "rank":     (10,  46),       # 36px
    "avatar":   (48,  96),       # 48px
    "name":     (98, 250),       # 152px (left-aligned)
    "distance": (250, 364),       # 114px
    "runs":     (364, 478),       # 114px
    "longest":  (478, 592),       # 114px
    "pace":     (592, 706),       # 114px
    "elev":     (706, 820),       # 114px
}


def _center(col):
    s, e = COL[col]
    return (s + e) // 2, e - s


# ── Fonts ───────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_cache: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("b" if bold else "r", size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(os.path.join(_FONT_DIR, "NotoSans.ttf"), size)
    return _cache[key]


# ── Formatters ──────────────────────────────────────────
def _km(m: float) -> str:
    return f"{m/1000:.1f}km" if m > 0 else "–"

def _elv(m: float) -> str:
    return f"{int(m)}m" if m > 0 else "–"

def _pac(v: float) -> str:
    if v <= 0:
        return "–"
    s = 1000.0 / v
    return f"{int(s//60)}:{int(s%60):02d}/km"


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
        out = Image.new("RGBA", (AVATAR, AVATAR))
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

    # ── Helper ─────────────────────────────────────────
    def _tc(text, font_sz, col, ry, color, *, bold=False, left=False):
        f = _font(font_sz, bold)
        bb = dr.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        y = ry + (ROW - th) / 2
        if left:
            x = COL[col][0]
        else:
            cx, _ = _center(col)
            x = cx - tw / 2
        dr.text((x, y), text, fill=color, font=f)

    # ── Header ─────────────────────────────────────────
    dr.rectangle([(0, 0), (WIDTH, HDR)], fill=ROW_ALT)
    dr.line([(0, HDR), (WIDTH, HDR)], fill=SEP, width=1)

    hf = _font(9, True)
    hy = (HDR - hf.getbbox("Ag")[3]) // 2 + 1
    for col, label in [
        ("rank", "#"),
        ("name", "ATHLETE"),
        ("distance", "DISTANCE"),
        ("runs", "RUNS"),
        ("longest", "LONGEST"),
        ("pace", "AVG PACE"),
        ("elev", "ELEV GAIN"),
    ]:
        cx, _ = _center(col)
        tw = dr.textlength(label, font=hf)
        dr.text((cx - tw/2, hy), label, fill=LIGHT, font=hf)

    # ── Rows ───────────────────────────────────────────
    for i, entry in enumerate(entries):
        ry = HDR + i * ROW
        rank = i + 1
        a = entry.get("athlete", {})
        name = f"{a.get('firstname','')} {a.get('lastname','')}".strip() or "–"

        if i % 2 == 1:
            dr.rectangle([(0, ry), (WIDTH, ry + ROW)], fill=ROW_ALT)

        _tc(str(rank), 14, "rank", ry, ORANGE if rank <= 3 else LIGHT)

        cx, _ = _center("avatar")
        av = _avatar(a.get("profile") or a.get("profile_medium", ""))
        img.paste(av, (cx - AVATAR // 2, ry + (ROW - AVATAR) // 2), av)

        _tc(name, 14, "name", ry, DARK, bold=True, left=True)
        _tc(_km(entry.get("distance") or 0), 14, "distance", ry, ORANGE)
        _tc(str(int(entry.get("num_activities") or 0)), 14, "runs", ry, DARK)
        _tc(_km(entry.get("best_activities_distance") or 0), 14, "longest", ry, DARK)
        _tc(_pac(entry.get("velocity") or 0), 14, "pace", ry, DARK)
        _tc(_elv(entry.get("elev_gain") or 0), 14, "elev", ry, DARK)

        dr.line([(0, ry + ROW), (WIDTH, ry + ROW)], fill=SEP, width=1)

    return img
