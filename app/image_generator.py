"""Strava-styled club leaderboard image — mobile-first.

No header, no footer.
Columns: Rank | Athlete | DISTANCE | Runs | Longest | Avg Pace | Elev Gain
Distance column is highlighted with an orange tint.
"""
import logging
import io
import os

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Colours ──────────────────────────────────────────────
ORANGE    = "#FC4C02"
ORANGE_BG = "#FFF4EE"   # subtle band behind distance
WHITE     = "#FFFFFF"
DARK      = "#1A1A1A"
GREY      = "#A0A0A0"
SEP       = "#EAEAEA"
ROW_ALT   = "#F9F9FA"

# ── Layout (820 px wide, phone-friendly) ────────────────
W   = 820
LBL = 26            # slim label strip
ROW = 60            # athlete row height
AV  = 40            # avatar diameter

# Column start positions
PX_RANK = 14
PX_AV   = 52
PX_NAME = 102
# Highlighted Distance band
DX_L = 218
DX_R = 290
PX_DIST = 254       # centre of distance band
PX_RUNS = 340
PX_LONG = 405
PX_PACE = 475
PX_ELEV = 550

# ── Medals ───────────────────────────────────────────────
MEDAL = {1: "#FC4C02", 2: "#63829C", 3: "#A0A0A0"}
MEDAL_TXT = WHITE

# ── Font ────────────────────────────────────────────────
_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "fonts", "NotoSans.ttf")
_fc: dict = {}

def _ft(s: int):
    k = ("r", s)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(_FONT, s)
    return _fc[k]

def _fb(s: int):
    k = ("b", s)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(_FONT, s)
    return _fc[k]

def _pace(v: float) -> str:
    if not v or v <= 0:
        return "—"
    spk = 1000.0 / v
    return f"{int(spk//60)}:{int(spk%60):02d}"

def _avatar(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        s = min(img.size)
        l, t = (img.size[0]-s)//2, (img.size[1]-s)//2
        return img.crop((l,t,l+s,t+s)).resize((AV,AV), Image.LANCZOS)
    except Exception:
        return None

def _circle(img: Image.Image) -> Image.Image:
    s = img.size[0]
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse((0,0,s-1,s-1), fill=255)
    out = Image.new("RGBA", (s, s), (0,0,0,0))
    out.paste(img, (0,0))
    out.putalpha(mask)
    return out

def _ph() -> Image.Image:
    img = Image.new("RGBA", (AV, AV), ORANGE)
    return _circle(img)

# ── Build image ──────────────────────────────────────────
def generate(entries: list[dict]) -> Image.Image:
    n = len(entries)
    H = LBL + n * ROW
    img = Image.new("RGB", (W, H), WHITE)
    dr  = ImageDraw.Draw(img)

    # ── label strip ──
    dr.rectangle([(0,0),(W,LBL)], fill=ROW_ALT)
    f_lbl = _fb(10)
    dr.text((PX_NAME, 7), "ATHLETE",    fill=GREY, font=f_lbl)
    dr.text((DX_L,      7), "DISTANCE", fill=ORANGE, font=f_lbl)
    dr.text((PX_RUNS,   7), "RUNS",     fill=GREY, font=f_lbl)
    dr.text((PX_LONG,   7), "LONGEST",  fill=GREY, font=f_lbl)
    dr.text((PX_PACE,   7), "AVG PACE", fill=GREY, font=f_lbl)
    dr.text((PX_ELEV,   7), "ELEV GAIN",fill=GREY, font=f_lbl)
    dr.line([(0,LBL),(W,LBL)], fill=SEP, width=1)

    y0 = LBL
    f_name = _fb(14)
    f_stat = _ft(12)
    f_dist = _fb(17)
    f_rank = _fb(11)

    for i, entry in enumerate(entries):
        ry = y0 + i * ROW
        rank = i + 1
        a = entry.get("athlete", {})
        name = f"{a.get('firstname','')} {a.get('lastname','')}".strip()
        name = name or a.get("username", "---")

        # alternate row tint
        if i % 2 == 1:
            dr.rectangle([(0,ry),(W,ry+ROW)], fill=ROW_ALT)

        # ── highlighted distance band ──
        dr.rectangle([(DX_L,ry),(DX_R,ry+ROW)], fill=ORANGE_BG)
        dr.line([(DX_L,ry),(DX_L,ry+ROW)], fill=SEP, width=1)
        dr.line([(DX_R,ry),(DX_R,ry+ROW)], fill=SEP, width=1)

        # rank badge
        if rank <= 3:
            cx, cy, r = PX_RANK+7, ry+ROW//2+2, 12
            dr.ellipse((cx-r,cy-r,cx+r,cy+r), fill=MEDAL[rank])
            bb = dr.textbbox((0,0), str(rank), font=f_rank)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            dr.text((cx-tw/2, cy-th/2), str(rank),
                    fill=MEDAL_TXT, font=f_rank)
        else:
            dr.text((PX_RANK+3, ry+ROW//2-4), str(rank),
                    fill=GREY, font=f_rank)

        # avatar
        avu = a.get("profile") or a.get("profile_medium", "")
        av  = _avatar(avu) if avu else None
        if av is None:
            av = _circle(_ph())
        img.paste(av, (PX_AV, ry+(ROW-AV)//2), av)

        # athlete name
        dr.text((PX_NAME, ry+ROW//2-6), name, fill=DARK, font=f_name)

        # distance (large orange, inside band)
        dist_m = entry.get("distance") or 0
        txt = f"{dist_m/1000:.1f}"
        tw = dr.textlength(txt, font=f_dist)
        dr.text((PX_DIST-tw/2, ry+ROW//2-8), txt,
                fill=ORANGE, font=f_dist)

        # stats — all on one line, right of name
        sy = ry + ROW//2 + 9
        dr.text((PX_RUNS, sy), str(int(entry.get("num_activities") or 0)),
                fill=DARK, font=f_stat)

        bl = (entry.get("best_activities_distance") or 0) / 1000
        dr.text((PX_LONG, sy), f"{bl:.1f}" if bl else "—",
                fill=DARK, font=f_stat)

        dr.text((PX_PACE, sy), _pace(entry.get("velocity") or 0),
                fill=DARK, font=f_stat)

        el = entry.get("elev_gain") or 0
        dr.text((PX_ELEV, sy), f"{int(el)}m" if el else "—",
                fill=DARK, font=f_stat)

        # row separator
        dr.line([(0,ry+ROW),(W,ry+ROW)], fill=SEP, width=1)

    return img
