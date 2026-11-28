"""BLACKOUT.NETWORK newsletter: the 24-hour weather strip, drawn as an email-safe PNG (Matt, Nov 27 2026).

One image per reader and issue, made from the reader's own NWS hourly forecast. The email carries the numbers inside a signed URL,
  https://blackout.network/nlwx/<data>.<sig>.png
so nothing is stored, the picture is frozen at send time, and nobody can make the server draw arbitrary data (HMAC over the data,
keyed from NEWSLETTER_SECRET). Without a secret no image URL is made and the email falls back to its live-text version.

The strip (1200 px wide = 600 px @2x, imperial units, dark SpaceX look, no yellow/green):
  * day / night shading behind every row (night columns darker) with 'NOW' and 3-hour ticks;
  * temperature curve (white) with NOW / HIGH / LOW marked;
  * chance of rain as bars (cool blue-grey), 100% guide line, the peak labelled;
  * wind as arrows pointing the way the wind is blowing, with mph every 3 hours;
  * humidity as a brightness strip with % every 3 hours;
  * an NWS alert band over the hours it covers (red only for the warning types flagged red).
Pillow only; drawn at 2x and smoothed; palette-quantised so it stays under ~100 KB.
"""
import base64, hashlib, hmac, io, json, math, os, re, zlib
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(BASE, "static", "newsletter", "fonts")
URL_RE = re.compile(r"/nlwx/([A-Za-z0-9_-]{8,2400})\.([0-9a-f]{20})(?:\.png)?")

W = 1200
BG, CARD, NIGHT, DAY, LINE = (0, 0, 0), (14, 15, 17), (10, 11, 13), (24, 26, 30), (46, 49, 54)
TX, BODY, MU, DIM = (255, 255, 255), (199, 199, 204), (142, 142, 147), (110, 110, 115)
RAIN, RED = (127, 166, 214), (255, 77, 79)
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# ------------------------------------------------------------------ signed, compact URL payload
def _key():
    s = os.environ.get("NEWSLETTER_SECRET", "")
    if len(s) < 32:
        try:
            import newsletter as N; s = N.env().get("NEWSLETTER_SECRET", "")
        except Exception:
            s = ""
    return hashlib.sha256(("nlwx|" + s).encode()).digest() if len(s) >= 32 else None

def pack(series):
    """series: {"t0": start epoch s, "tz": '-05:00' style minutes offset int, "z": 'EST', "h": [[temp, rh, wind, dir, pop, day], ...],
    "al": [[start_idx, end_idx, red(0/1), 'Event']]} -> url-safe string."""
    raw = zlib.compress(json.dumps(series, separators=(",", ":")).encode(), 9)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def unpack(tok):
    raw = base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4))
    d = zlib.decompressobj(); out = d.decompress(raw, 20000)
    if d.unconsumed_tail: raise ValueError("too large")
    return json.loads(out)

def url(series, base="https://blackout.network"):
    k = _key()
    if not k: return None
    tok = pack(series)
    sig = hmac.new(k, tok.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{base.rstrip('/')}/nlwx/{tok}.{sig}.png"

def _valid(s):
    try:
        H = s["h"]
        if not (8 <= len(H) <= 30): return False
        for r in H:
            if len(r) != 6: return False
            if not all(isinstance(x, (int, float)) or x is None for x in r): return False
        return isinstance(s["t0"], (int, float)) and isinstance(s["z"], str) and len(s["z"]) <= 5 and isinstance(s.get("tz", 0), int)
    except Exception:
        return False

# ------------------------------------------------------------------ drawing
_FC = {}
def font(weight, px):
    from PIL import ImageFont
    k = (weight, px)
    if k not in _FC:
        _FC[k] = ImageFont.truetype(os.path.join(FONTS, "Inter-Bold.ttf" if weight == "b" else "Inter-Medium.ttf"), px)
    return _FC[k]

def _spline(pts, steps=10):
    """Catmull-Rom through the hourly points (smooth, never overshoots badly with clamped tangents)."""
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, n - 1)]
        for s in range(steps):
            t = s / steps; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    out.append(pts[-1])
    return out

def render(series):
    """-> PNG bytes."""
    from PIL import Image, ImageDraw
    S = 2                                   # supersample
    H = series["h"]; n = len(H)
    t0 = datetime.utcfromtimestamp(series["t0"] + series.get("tz", 0) * 60)   # local wall time of column 0
    hour0 = t0.hour
    L, R = 44, 44; PW = W - L - R; cw = PW / n
    cx = lambda i: L + cw * (i + 0.5)
    al = [a for a in series.get("al") or [] if 0 <= a[0] < n]
    # vertical plan
    y = 28; secs = {}
    secs["alert"] = (y, 74) if al else None
    if al: y += 74 + 22
    secs["temp"] = (y + 64, 340); y += 64 + 340 + 26
    secs["rain"] = (y + 64, 190); y += 64 + 190 + 26
    secs["wind"] = (y + 64, 156); y += 64 + 156 + 26
    secs["rh"] = (y + 64, 56); y += 64 + 56 + 54 + 12
    secs["axis"] = (y, 56); y += 56 + 22
    Ht = y
    im = Image.new("RGB", (W * S, Ht * S), CARD); d = ImageDraw.Draw(im, "RGBA")
    sc = lambda v: int(round(v * S))
    def text(xy, s, f, fill, anchor="la"): d.text((sc(xy[0]), sc(xy[1])), s, font=f, fill=fill, anchor=anchor)
    F = lambda w, px: font(w, px * S)
    top, bot = (secs["alert"][0] if al else secs["temp"][0] - 64), secs["rh"][0] + secs["rh"][1] + 50
    # day / night columns behind everything
    for i, r in enumerate(H):
        x0 = L + cw * i
        d.rectangle([sc(x0), sc(top - 6), sc(x0 + cw + 0.6), sc(bot + 14)], fill=DAY if r[5] else NIGHT)
    # 3-hour ticks
    for i in range(n):
        if (hour0 + i) % 3 == 0:
            x = L + cw * i
            d.line([sc(x), sc(top - 6), sc(x), sc(bot + 14)], fill=(255, 255, 255, 26), width=S)
    # alert band
    if al:
        ay, ah = secs["alert"]
        for a in al:
            x0 = L + cw * a[0]; x1 = L + cw * min(n, a[1] + 1)
            col = RED if a[2] else (230, 230, 235)
            d.rounded_rectangle([sc(x0 + 2), sc(ay + 44), sc(x1 - 2), sc(ay + ah)], radius=sc(8), fill=col + (70,), outline=col + (255,), width=sc(3))
            f = F("b", 38); lab = a[3].upper()
            lw = f.getlength(lab) / S
            tx = min(max(x0 + 2, L), W - R - lw)
            text((tx, ay + 34), lab, f, col if a[2] else TX, "ls")
    # section labels
    def label(sec, s, right=None):
        y0 = secs[sec][0] - 56
        text((L, y0), s, F("b", 40), MU)
        if right: text((W - R, y0), right, F("m", 38), DIM, "ra")
    # ---- temperature
    ty, th = secs["temp"]
    temps = [r[0] for r in H]; lo_t, hi_t = min(temps), max(temps); span = max(8, hi_t - lo_t)
    pad = 54
    ymap = lambda v: ty + pad + (th - 2 * pad) * (1 - (v - lo_t) / span)
    label("temp", "TEMPERATURE  °F", "darker = night")
    pts = [(cx(i), ymap(v)) for i, v in enumerate(temps)]
    sp = _spline(pts)
    poly = [(sc(x), sc(yv)) for x, yv in sp] + [(sc(sp[-1][0]), sc(ty + th)), (sc(sp[0][0]), sc(ty + th))]
    # soft fill: stacked translucent bands
    fill = Image.new("RGBA", im.size, (0, 0, 0, 0)); fd = ImageDraw.Draw(fill)
    fd.polygon(poly, fill=(255, 255, 255, 30)); im.paste(Image.alpha_composite(im.convert("RGBA"), fill).convert("RGB"))
    d = ImageDraw.Draw(im, "RGBA")
    d.line([(sc(x), sc(yv)) for x, yv in sp], fill=TX, width=sc(6), joint="curve")
    def mark(i, txt, above=True, col=TX, tag=None):
        x, yv = pts[i]
        d.ellipse([sc(x - 11), sc(yv - 11), sc(x + 11), sc(yv + 11)], fill=BG, outline=col, width=sc(5))
        f = F("b", 52); s = txt
        w_ = f.getlength(s) / S; tx = min(max(x, L + w_ / 2), W - R - w_ / 2)
        text((tx, yv - 24 if above else yv + 20), s, f, col, "ms" if above else "ma")
    hi_i = temps.index(hi_t); lo_i = temps.index(lo_t)
    mark(0, f"{temps[0]}°", above=temps[0] >= (hi_t + lo_t) / 2, col=TX)
    if hi_i not in (0,): mark(hi_i, f"{hi_t}°", above=True)
    if lo_i not in (0, hi_i): mark(lo_i, f"{lo_t}°", above=False, col=BODY)
    # ---- rain
    ry, rh_ = secs["rain"]; label("rain", "CHANCE OF RAIN  %")
    base = ry + rh_
    d.line([sc(L), sc(ry), sc(W - R), sc(ry)], fill=(255, 255, 255, 40), width=S)
    text((W - R, ry - 8), "100", F("m", 34), DIM, "rs")
    peak = max(range(n), key=lambda i: H[i][4])
    for i, r in enumerate(H):
        p = r[4] or 0; bh = rh_ * p / 100
        x0 = L + cw * i + 6; x1 = L + cw * (i + 1) - 6
        d.rounded_rectangle([sc(x0), sc(base - 6), sc(x1), sc(base)], radius=sc(3), fill=(255, 255, 255, 40))     # baseline pip: shows 0%
        if p:
            d.rounded_rectangle([sc(x0), sc(base - max(bh, 8)), sc(x1), sc(base)], radius=sc(5), fill=RAIN + (int(110 + 1.45 * p),))
    if H[peak][4] and H[peak][4] >= 20:
        px_ = cx(peak); f = F("b", 48); s = f"{H[peak][4]}%"; w_ = f.getlength(s) / S
        text((min(max(px_, L + w_ / 2), W - R - w_ / 2), base - rh_ * H[peak][4] / 100 - 14), s, f, TX, "ms")
    else:
        pk = H[peak][4] or 0
        text((W / 2, ry + rh_ / 2 - 20), "Dry" if not pk else f"Mostly dry: the chance never tops {pk}%", F("b", 44), BODY, "mm")
    # ---- wind
    wy, wh = secs["wind"]; label("wind", "WIND  mph")
    for i, r in enumerate(H):
        if r[2] is None or (hour0 + i) % 3: continue
        if r[3] is None or r[2] == 0:   # calm: a dot, no direction
            d.ellipse([sc(cx(i) - 7), sc(wy + 38 - 7), sc(cx(i) + 7), sc(wy + 38 + 7)], fill=BODY)
            text((cx(i), wy + 100), str(r[2]), F("b", 46), TX, "ms"); text((cx(i), wy + 144), "calm", F("m", 32), DIM, "ms"); continue
        x = cx(i); yc = wy + 38; ang = math.radians((r[3] * 22.5 + 180) % 360)   # points the way the air is moving
        ln = 34 + min(r[2], 40) * 0.7; ux, uy = math.sin(ang), -math.cos(ang)
        x0, y0 = x - ux * ln / 2, yc - uy * ln / 2; x1, y1 = x + ux * ln / 2, yc + uy * ln / 2
        d.line([sc(x0), sc(y0), sc(x1), sc(y1)], fill=BODY, width=sc(5))
        hx, hy = -uy, ux; hl = 15
        d.polygon([(sc(x1), sc(y1)), (sc(x1 - ux * hl + hx * hl * .6), sc(y1 - uy * hl + hy * hl * .6)), (sc(x1 - ux * hl - hx * hl * .6), sc(y1 - uy * hl - hy * hl * .6))], fill=BODY)
        text((x, wy + 102), str(r[2]), F("b", 46), TX, "ms")
        text((x, wy + 144), COMPASS[r[3]], F("m", 32), DIM, "ms")
    # ---- humidity
    hy_, hh = secs["rh"]; label("rh", "HUMIDITY  %")
    for i, r in enumerate(H):
        if r[1] is None: continue
        k = max(0.0, min(1.0, (r[1] - 20) / 80)); c = tuple(int(a + (b - a) * k) for a, b in zip((30, 33, 38), (150, 176, 204)))
        x0 = L + cw * i + 2; x1 = L + cw * (i + 1) - 2
        d.rounded_rectangle([sc(x0), sc(hy_), sc(x1), sc(hy_ + hh)], radius=sc(6), fill=c)
        if (hour0 + i) % 3 == 0:
            text(((x0 + x1) / 2, hy_ + hh + 30), str(r[1]), F("b", 44), TX, "mm")
    # ---- time axis
    ay_, ah_ = secs["axis"]
    for i in range(n):
        h = (hour0 + i) % 24
        if i == 0: text((cx(i) - 18, ay_ + 28), "NOW", F("b", 38), TX, "lm")
        elif h % 3 == 0 and i >= 2:
            lab = ("12 AM" if h == 0 else "12 PM" if h == 12 else f"{h % 12} {'AM' if h < 12 else 'PM'}")
            if cx(i) + 70 < W - R + 30: text((cx(i), ay_ + 28), lab, F("m", 38), MU, "mm")
    # sun/moon change markers on the axis
    for i in range(1, n):
        if H[i][5] != H[i - 1][5]:
            x = L + cw * i; d.line([sc(x), sc(ay_ - 6), sc(x), sc(ay_ + 6)], fill=BODY, width=sc(3))
    out = im.resize((W, Ht), Image.LANCZOS)
    q = out.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    b = io.BytesIO(); q.save(b, "PNG", optimize=True)
    return b.getvalue()

_CACHE = {}
def handle_get(path, qs=None):
    """Addon entry: /nlwx/<data>.<sig>.png -> (200, png, 'image/png'); anything wrong -> 404 (never draws unsigned data)."""
    try:
        m = URL_RE.fullmatch((path or "").split("?")[0])
        k = _key()
        if not m or not k: return 404, b"not found", "text/plain"
        tok, sig = m.group(1), m.group(2)
        if not hmac.compare_digest(sig, hmac.new(k, tok.encode(), hashlib.sha256).hexdigest()[:20]): return 404, b"not found", "text/plain"
        if tok in _CACHE: return 200, _CACHE[tok], "image/png"
        s = unpack(tok)
        if not _valid(s): return 404, b"not found", "text/plain"
        png = render(s)
        if len(_CACHE) > 200: _CACHE.clear()
        _CACHE[tok] = png
        return 200, png, "image/png"
    except Exception:
        return 404, b"not found", "text/plain"

def series_from_hours(hrs, alerts=(), now_utc=None):
    """newsletter_wx hourly dict (+ the reader's alert list) -> the compact series this module draws."""
    H = hrs["hours"][:24]
    d0 = datetime.fromisoformat(H[0]["t"].replace("Z", "+00:00"))
    off = int(d0.utcoffset().total_seconds() // 60) if d0.utcoffset() is not None else 0
    t0 = int(d0.timestamp())
    rows = [[h["temp"], h["rh"], h["wind"], h["dir"], h["pop"], 1 if h["day"] else 0] for h in H]
    al = []
    for a in alerts or []:
        if not a.get("storm", True): continue
        try:
            s_ = datetime.fromisoformat((a.get("onset") or H[0]["t"]).replace("Z", "+00:00")).timestamp()
            e_ = datetime.fromisoformat((a.get("until") or H[-1]["t"]).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        i0 = max(0, int((s_ - t0) // 3600)); i1 = min(len(H) - 1, int((e_ - t0) // 3600))
        if i1 >= 0 and i0 <= len(H) - 1 and i0 <= i1:
            al.append([i0, i1, 1 if a.get("red") else 0, a.get("event", "")[:40]])
    return {"t0": t0, "tz": off, "z": (hrs.get("tzname") or "")[:5], "h": rows, "al": al[:2]}
