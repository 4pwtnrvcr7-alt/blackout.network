"""Engraved graphics for the newsletter. Pure Python PNGs: no paid API, no JavaScript, no tile key.

The basemap is the site's own Natural Earth file (signal_map_static/world.geojson), drawn
server-side. Dots use the same rank colours as the signal map (low / elevated / high) and a
category legend. Section plates and event icons are monochrome line engravings in the
BLACKOUT gold-on-black palette. SVG sources for the icons live next to this module's
drawings so the email can ship PNG, which Gmail and Outlook actually show.
"""
import base64, html, json, math, os, struct, zlib

BASE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.path.join(BASE, "signal_map_static", "world.geojson")
LOGO = os.path.join(BASE, "static", "social", "brand_tile_v2_dark_168.png")

BG = (11, 13, 16)
LAND = (22, 28, 36)
COAST = (255, 194, 26)
GOLD = (255, 194, 26)
INK = (245, 245, 247)
MUTED = (120, 126, 136)
RED = (200, 16, 46)
# Signal-map rank colours (signal_map_static/app.css).
RANK_COLOR = {"low": (85, 183, 255), "mid": (245, 165, 36), "high": (255, 77, 79)}
CAT_COLOR = {
    "war/conflict": (200, 16, 46),
    "natural disaster": (85, 183, 255),
    "disease": (63, 174, 128),
    "political": (255, 194, 26),
    "cyber": (168, 140, 255),
    "financial": (255, 150, 70),
    "space weather": (190, 210, 255),
    "other": (161, 161, 166),
}

# 5x7 uppercase. Bits are row-major, 5 wide.
_FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01111 10000 10000 10000 10000 10000 01111",
    "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01111 10000 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "11111 00100 00100 00100 00100 00100 11111",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00110 01000 10000 11111",
    "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    "/": "00001 00010 00100 01000 10000 00000 00000",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    ">": "10000 01000 00100 00010 00100 01000 10000",
}


def _chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def png_bytes(pix):
    h, w = len(pix), len(pix[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in pix)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


def data_uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def _blank(w, h, color=BG):
    return [[color for _ in range(w)] for _ in range(h)]


def _text(pix, text, x, y, color=GOLD, scale=2):
    cx = x
    for ch in text.upper():
        rows = _FONT.get(ch, _FONT[" "]).split()
        for ry, bits in enumerate(rows):
            for rx, bit in enumerate(bits):
                if bit != "1": continue
                for dy in range(scale):
                    for dx in range(scale):
                        px, py = cx + rx * scale + dx, y + ry * scale + dy
                        if 0 <= py < len(pix) and 0 <= px < len(pix[0]): pix[py][px] = color
        cx += 6 * scale
    return cx


def _hline(pix, y, color, x0=0, x1=None):
    if not (0 <= y < len(pix)): return
    x1 = len(pix[0]) if x1 is None else x1
    for x in range(max(0, x0), min(len(pix[0]), x1)): pix[y][x] = color


def _line(pix, x0, y0, x1, y1, color):
    h, w = len(pix), len(pix[0])
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for s in range(steps + 1):
        x = int(x0 + (x1 - x0) * s / steps)
        y = int(y0 + (y1 - y0) * s / steps)
        if 0 <= x < w and 0 <= y < h: pix[y][x] = color


def _fill_ring(pix, ring, color):
    h, w = len(pix), len(pix[0])
    pts = []
    prev = None
    for lon, lat in ring:
        if prev and abs(lon - prev[0]) > 180:
            if len(pts) >= 3: _fill_pts(pix, pts, color)
            pts = []
        x = int((lon + 180.0) / 360.0 * (w - 1))
        y = int((90.0 - lat) / 180.0 * (h - 1))
        pts.append((x, y)); prev = (lon, lat)
    if len(pts) >= 3: _fill_pts(pix, pts, color)


def _fill_pts(pix, pts, color):
    h, w = len(pix), len(pix[0])
    buckets = {}
    seq = pts + [pts[0]]
    for (x0, y0), (x1, y1) in zip(seq, seq[1:]):
        if y0 == y1: continue
        if y0 > y1: x0, y0, x1, y1 = x1, y1, x0, y0
        dy = y1 - y0
        y_start, y_end = max(0, y0), min(h, y1)
        for y in range(y_start, y_end):
            x = x0 + (x1 - x0) * (y - y0) / dy
            buckets.setdefault(y, []).append(x)
    for y, xs in buckets.items():
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            a, b = int(xs[i]), int(xs[i + 1])
            if b < a: a, b = b, a
            row = pix[y]
            for x in range(max(0, a), min(w, b + 1)): row[x] = color


_LAND = {"pix": None}


def _land():
    if _LAND["pix"] is not None: return _LAND["pix"]
    w, h = 640, 320
    pix = _blank(w, h, BG)
    # engraved latitude lines
    for lat in (-60, -30, 0, 30, 60):
        y = int((90 - lat) / 180 * (h - 1))
        _hline(pix, y, (28, 32, 40))
    try:
        with open(WORLD, encoding="utf-8") as fh: geo = json.load(fh)
    except Exception:
        geo = {"features": []}
    for feat in geo.get("features") or []:
        g = feat.get("geometry") or {}
        polys = g.get("coordinates") or []
        if g.get("type") == "Polygon": polys = [polys]
        for poly in polys:
            if not poly: continue
            ring = poly[0]
            if len(ring) > 240: ring = ring[:: max(1, len(ring) // 180)]
            _fill_ring(pix, ring, LAND)
            # coast as a gold hairline: trace the ring
            prev = None
            for lon, lat in ring:
                x = int((lon + 180.0) / 360.0 * (w - 1))
                y = int((90.0 - lat) / 180.0 * (h - 1))
                if prev and abs(lon - prev[0]) <= 180: _line(pix, prev[2], prev[3], x, y, (70, 62, 32))
                prev = (lon, lat, x, y)
    _LAND["pix"] = pix
    return pix


def _project(lon, lat, w, h):
    return int((float(lon) + 180.0) / 360.0 * (w - 1)), int((90.0 - float(lat)) / 180.0 * (h - 1))


def story_map(points):
    """points: [{lon, lat, n, category, rank}]. Numbered dots on the engraved basemap."""
    base = _land()
    h, w = len(base), len(base[0])
    pix = [row[:] for row in base]
    legend = []
    for p in points:
        if p.get("lon") is None or p.get("lat") is None: continue
        x, y = _project(p["lon"], p["lat"], w, h)
        cat = p.get("category") or "other"
        col = CAT_COLOR.get(cat, CAT_COLOR["other"])
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                if dx * dx + dy * dy <= 36 and 0 <= y + dy < h and 0 <= x + dx < w:
                    pix[y + dy][x + dx] = col
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                if 28 <= dx * dx + dy * dy <= 40 and 0 <= y + dy < h and 0 <= x + dx < w:
                    pix[y + dy][x + dx] = INK
        _text(pix, str(p.get("n") or ""), x - 3, y - 4, BG, 1)
        if cat not in legend: legend.append(cat)
    # legend strip
    lx = 8
    for cat in legend[:6]:
        col = CAT_COLOR.get(cat, MUTED)
        for dy in range(6):
            for dx in range(6):
                if 0 <= 8 + dy < h and 0 <= lx + dx < w: pix[8 + dy][lx + dx] = col
        lx = _text(pix, cat.replace("natural disaster", "disaster")[:18], lx + 10, 6, INK, 1) + 8
    return png_bytes(pix)


def section_plate(title):
    """Guilloche band with the section name etched in gold."""
    w, h = 560, 56
    pix = _blank(w, h, (14, 16, 20))
    for i, amp in enumerate((3, 5, 2)):
        phase = i * 1.7
        y0 = 14 + i * 12
        prev = None
        for x in range(8, w - 8):
            y = int(y0 + math.sin(x / 18.0 + phase) * amp)
            if prev: _line(pix, prev[0], prev[1], x, y, (90, 74, 28) if i != 1 else GOLD)
            prev = (x, y)
    _hline(pix, 2, GOLD); _hline(pix, h - 3, GOLD)
    label = title.upper()[:28]
    tw = len(label) * 12
    _text(pix, label, max(12, (w - tw) // 2), 18, INK, 2)
    return png_bytes(pix)


def _icon_canvas():
    return _blank(48, 48, (14, 16, 20))


def _stroke_circle(pix, cx, cy, r, color):
    for a in range(0, 360, 6):
        rad = math.radians(a)
        x, y = int(cx + r * math.cos(rad)), int(cy + r * math.sin(rad))
        if 0 <= y < len(pix) and 0 <= x < len(pix[0]): pix[y][x] = color


# Compact editorial marks. One filled symbol per story kind, drawn to the edges of a
# 144px tile so a 72px header slot stays full. No scene, halo, or baked-in words.
TILE = (27, 41, 51)
MARK = {
    "missile": ((255, 194, 26), "#FFC21A"),
    "conflict": ((224, 138, 74), "#E08A4A"),
    "politics": ((126, 164, 204), "#7EA4CC"),
    "outbreak": ((94, 174, 156), "#5EAE9C"),
    "quake": ((176, 146, 196), "#B092C4"),
    "storm": ((126, 164, 204), "#7EA4CC"),
    "flood": ((96, 170, 184), "#60AAB8"),
    "fire": ((214, 146, 78), "#D6924E"),
    "grid": ((240, 196, 96), "#F0C460"),
    "cyber": ((156, 146, 196), "#9C92C4"),
    "space": ((186, 196, 214), "#BAC4D6"),
    "financial": ((214, 166, 86), "#D6A656"),
    "rights": ((214, 198, 156), "#D6C69C"),
    "surveillance": ((168, 184, 196), "#A8B8C4"),
    "protest": ((204, 166, 122), "#CCA67A"),
    "border": ((186, 176, 146), "#BAB092"),
    "place": ((244, 241, 232), "#F4F1E8"),
    "other": ((255, 194, 26), "#FFC21A"),
    "nuclear": ((214, 176, 96), "#D6B060"),
    "terror": ((196, 122, 96), "#C47A60"),
}


def _setpx(pix, x, y, color):
    if 0 <= y < len(pix) and 0 <= x < len(pix[0]): pix[y][x] = color


def _disk(pix, cx, cy, r, color):
    r2 = r * r
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2: _setpx(pix, x, y, color)


def _rect(pix, x0, y0, x1, y1, color):
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)): _setpx(pix, x, y, color)


def _poly(pix, pts, color):
    _fill_pts(pix, [(int(round(x)), int(round(y))) for x, y in pts], color)


def _thick(pix, x0, y0, x1, y1, color, r):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for s in range(int(steps) + 1):
        _disk(pix, x0 + (x1 - x0) * s / steps, y0 + (y1 - y0) * s / steps, r, color)


def _ring(pix, cx, cy, r, color, w):
    _disk(pix, cx, cy, r, color)
    _disk(pix, cx, cy, max(1, r - w), TILE)


ICON_DIR = os.path.join(BASE, "static", "newsletter", "icons")

def symbol_png(kind):
    """144×144 Material Symbols glyph (2× for a 72px slot). Transparent, gold, no baked background."""
    path = os.path.join(ICON_DIR, (kind if os.path.exists(os.path.join(ICON_DIR, kind + ".png")) else "other") + ".png")
    with open(path, "rb") as fh:
        return fh.read()


def mark_hex(kind):
    return MARK.get(kind, MARK["other"])[1]


def section_kind(title):
    t = title or ""
    if t.startswith("Near you") or t.startswith("Crime") or t.startswith("Watch:"): return "place"
    if "Politic" in t: return "politics"
    if t.startswith("Also notable"): return "financial"
    if t.startswith("Patterns") or "follow" in t.lower() or t.startswith("Developing") or t.startswith("Watchlist"): return "other"
    return "conflict"


_SYM = {}
def symbol_src(kind):
    if kind not in _SYM: _SYM[kind] = data_uri(symbol_png(kind))
    return _SYM[kind]


def event_icon(kind):
    pix = _icon_canvas()
    g = GOLD
    if kind == "quake":
        _line(pix, 8, 30, 16, 18, g); _line(pix, 16, 18, 24, 34, g); _line(pix, 24, 34, 32, 14, g); _line(pix, 32, 14, 40, 28, g)
        _hline(pix, 36, MUTED, 6, 42)
    elif kind == "storm":
        _stroke_circle(pix, 24, 16, 6, g)
        _line(pix, 10, 28, 38, 22, g); _line(pix, 14, 34, 36, 30, g)
    elif kind == "flood":
        for i, y in enumerate((18, 26, 34)):
            prev = None
            for x in range(6, 42):
                yy = y + int(math.sin(x / 4 + i) * 2)
                if prev: _line(pix, prev[0], prev[1], x, yy, g)
                prev = (x, yy)
    elif kind == "fire":
        _line(pix, 24, 40, 16, 24, g); _line(pix, 16, 24, 24, 28, g); _line(pix, 24, 28, 20, 12, g)
        _line(pix, 24, 40, 32, 22, g); _line(pix, 32, 22, 24, 26, g); _line(pix, 24, 26, 30, 10, g)
    elif kind == "outbreak":
        _stroke_circle(pix, 24, 24, 10, g); _stroke_circle(pix, 24, 24, 3, RED)
        _line(pix, 24, 8, 24, 14, g); _line(pix, 24, 34, 24, 40, g); _line(pix, 8, 24, 14, 24, g); _line(pix, 34, 24, 40, 24, g)
    elif kind == "missile":
        _line(pix, 8, 36, 36, 12, g); _line(pix, 36, 12, 30, 12, g); _line(pix, 36, 12, 36, 18, g)
        _line(pix, 14, 30, 10, 38, MUTED); _line(pix, 18, 32, 12, 40, MUTED)
    elif kind == "conflict":
        _line(pix, 10, 38, 24, 8, g); _line(pix, 38, 38, 24, 8, g); _line(pix, 16, 28, 32, 28, g)
    elif kind == "grid":
        _line(pix, 24, 6, 24, 18, g); _line(pix, 14, 18, 34, 18, g); _line(pix, 16, 18, 10, 40, g); _line(pix, 32, 18, 38, 40, g)
        _line(pix, 10, 40, 38, 40, MUTED)
    elif kind == "cyber":
        _text(pix, "</>", 6, 16, g, 2)
    else:
        _stroke_circle(pix, 24, 24, 12, g); _line(pix, 24, 14, 24, 26, g); _line(pix, 24, 30, 24, 32, g)
    return png_bytes(pix)


def trajectory_gauge(label):
    """Semicircle gauge. Easing sits left, Steady in the middle, Rising on the right."""
    w, h = 168, 72
    pix = _blank(w, h, (14, 16, 20))
    cx, cy, r = 84, 58, 46
    for a in range(180, 361, 3):
        rad = math.radians(a)
        x, y = int(cx + r * math.cos(rad)), int(cy - r * math.sin(rad))
        col = (63, 174, 128) if a < 230 else (GOLD if a < 310 else RED)
        if 0 <= y < h and 0 <= x < w: pix[y][x] = col
    needle = {"Easing": 210, "Steady": 270, "Rising": 330}.get(label, 270)
    rad = math.radians(needle)
    _line(pix, cx, cy, int(cx + 36 * math.cos(rad)), int(cy - 36 * math.sin(rad)), INK)
    _text(pix, label[:7], 8, 58, GOLD, 1)
    return png_bytes(pix)


def category_bars(counts):
    """counts: {category: n} for stories in this issue."""
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
    if not items: return None
    w, h = 560, 28 + 22 * len(items)
    pix = _blank(w, h, (14, 16, 20))
    _text(pix, "STORIES BY CATEGORY", 12, 6, GOLD, 1)
    mx = max(n for _, n in items) or 1
    for i, (cat, n) in enumerate(items):
        y = 24 + i * 22
        _text(pix, cat.replace("natural disaster", "disaster")[:16], 8, y, INK, 1)
        col = CAT_COLOR.get(cat, MUTED)
        bw = int(280 * n / mx)
        for dy in range(10):
            for x in range(150, 150 + max(bw, 4)):
                if x < w: pix[y + dy][x] = col
        _text(pix, str(n), 150 + max(bw, 4) + 6, y, GOLD, 1)
    return png_bytes(pix)


def event_kind(title, category):
    t = (title or "").lower()
    if re_nuclear(t): return "nuclear"
    if re_terror(t): return "terror"
    if re_missile(t): return "missile"
    if re_quake(t): return "quake"
    if "flood" in t: return "flood"
    if re_fire(t): return "fire"
    if re_storm(t): return "storm"
    if re_disease(t): return "outbreak"
    if re_grid(t) or re_supply(t): return "grid"
    if re_surveil(t): return "surveillance"
    if re_protest(t): return "protest"
    if re_border(t): return "border"
    if re_rights(t): return "rights"
    if re_cyber(t): return "cyber"
    if category == "war/conflict": return "conflict"
    if category == "disease": return "outbreak"
    if category == "natural disaster": return "storm"
    if category == "political": return "politics"
    if category == "space weather" or "solar flare" in t or "geomagnetic" in t: return "space"
    if category == "financial": return "financial"
    return "other"


def re_missile(t): return "missile" in t or "ballistic" in t
def re_nuclear(t):
    import re
    return re.search(r"\b(?:nuclear|warhead|radioactive|atomic)\b", t) is not None
def re_terror(t):
    import re
    return re.search(r"\b(?:terror(?:ist|ism)?|bombing)\b", t) is not None
def re_quake(t):
    import re
    return re.search(r"earthquake|\bquake\b|\bmagnitude\b|\bm\s*[4-9](?:\.\d)?\b", t) is not None
def re_fire(t):
    import re
    return re.search(r"wildfire|\bfire\b", t) is not None
def re_storm(t):
    import re
    return re.search(r"hurricane|typhoon|tornado|storm", t) is not None
def re_disease(t):
    import re
    return re.search(r"outbreak|avian|influenza|\bflu\b|ebola|cholera|measles|mpox|dengue|pandemic|epidemic", t) is not None
def re_grid(t):
    import re
    return re.search(r"blackout|power outage|grid", t) is not None
def re_cyber(t):
    import re
    return re.search(r"ransomware|cyber|hack(?:ed|ers)?|breach", t) is not None
def re_surveil(t):
    import re
    return re.search(r"surveillance|privacy|censor|digital id|digital identity|cbdc|big tech|deplatform", t) is not None
def re_protest(t):
    import re
    return re.search(r"protest|unrest|riot|uprising|demonstration", t) is not None
def re_border(t):
    import re
    return re.search(r"border security|border patrol|southern border|northern border|port of entry", t) is not None
def re_rights(t):
    import re
    return re.search(r"civil libert|constitution|free speech|first amendment|second amendment|due process|gun rights|gun control|supreme court|appeals court|court ruling|emergency powers|mandate|election integrity", t) is not None
def re_supply(t):
    import re
    return re.search(r"supply chain|food supply|food shortage|fuel shortage|drinking water", t) is not None


_ICON = {}
def icon_src(kind):
    if kind not in _ICON: _ICON[kind] = data_uri(event_icon(kind))
    return _ICON[kind]


_PLATE = {}
def plate_src(title):
    if title not in _PLATE: _PLATE[title] = data_uri(section_plate(title))
    return _PLATE[title]


def logo_src():
    try:
        with open(LOGO, "rb") as fh: raw = fh.read()
        if raw[:8] == b"\x89PNG\r\n\x1a\n": return data_uri(raw)
    except Exception:
        pass
    return data_uri(event_icon("other"))


def img(src, alt, width, height):
    return (f'<img src="{src}" width="{width}" height="{height}" alt="{alt}" '
            f'style="display:block;width:{width}px;max-width:100%;height:auto;border:0">')


ENGRAVED = os.path.join(BASE, "static", "newsletter", "engraved")
_FILE = {}
_SCENE = {
    "storm": "scene-storm", "quake": "scene-quake", "flood": "scene-flood", "fire": "scene-fire",
    "outbreak": "scene-outbreak", "missile": "scene-missile", "conflict": "banner-threats",
    "grid": "scene-grid", "cyber": "scene-cyber", "space": "scene-space",
    "politics": "banner-politics", "financial": "banner-markets", "other": "banner-threats",
    "rights": "scene-rights", "surveillance": "scene-surveillance", "protest": "scene-protest",
    "border": "scene-border",
}
_BANNER = {
    "Top threats": "banner-threats", "Analyst brief": "banner-threats",
    "Politics & Government": "banner-politics", "Still developing": "banner-threats",
    "Developing stories": "banner-community", "Also notable": "banner-markets",
    "Watchlist: unconfirmed": "banner-community", "Patterns": "banner-community",
    "Stories you follow": "banner-community", "Watch: new on BLACKOUT.NETWORK": "banner-prepare",
}


def _file_src(name):
    if name in _FILE: return _FILE[name]
    path = os.path.join(ENGRAVED, name + ".png")
    try:
        with open(path, "rb") as fh: raw = fh.read()
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            _FILE[name] = data_uri(raw)
            return _FILE[name]
    except Exception:
        pass
    return None


def scene_src(kind):
    src = _file_src(_SCENE.get(kind) or _SCENE["other"])
    return src or data_uri(event_icon(kind if kind in ("quake", "storm", "flood", "fire", "outbreak", "missile", "conflict", "grid", "cyber") else "other"))


def banner_src(title):
    """Engraved banner, or '' when the file is missing or too empty to show. Callers then use a text header."""
    if (title or "").startswith("Near you"): name = "banner-prepare"
    elif (title or "").startswith("Crime"): name = "banner-community"
    else: name = _BANNER.get(title, "banner-threats")
    path = os.path.join(ENGRAVED, name + ".png")
    try:
        if os.path.getsize(path) < 3500: return ""
    except OSError:
        return ""
    return _file_src(name) or ""


def trend_word(trajectory):
    if trajectory == "Rising": return "UPTREND"
    if trajectory == "Easing": return "DOWNTREND"
    return "STEADY"


def trend_lozenge_html(trajectory, detail="", inline=False):
    """Live-text trend badge. The word is the meaning; the colour only reinforces it."""
    word = trend_word(trajectory)
    if word == "UPTREND":
        bg, fg, arrow = "#C8102E", "#FFFFFF", "▲"
    elif word == "DOWNTREND":
        bg, fg, arrow = "#146C43", "#FFFFFF", "▼"
    else:
        bg, fg, arrow = "#3A3D44", "#F5F5F7", "→"
    face = "Inter,Arial,Helvetica,sans-serif"
    pill = (f'<span style="display:inline-block;background:{bg};color:{fg};font:700 15px/20px {face};'
            f'padding:6px 10px;border-radius:999px">{arrow}&nbsp;{word}</span>')
    if inline: return pill
    extra = ""
    if detail:
        extra = f'<div style="font:400 14px/19px {face};color:#C4CDD2;margin-top:6px">{html.escape(detail)}</div>'
    return f'<div style="margin-top:8px">{pill}</div>{extra}'


def trend_badge_html(trajectory, detail):
    """Full-width arrow badge. Colours are inline so a dark-mode client does not wash them out."""
    word = trend_word(trajectory)
    if word == "UPTREND":
        bg, arrow, ac = "#C8102E", "▲", "#FFC21A"
    elif word == "DOWNTREND":
        bg, arrow, ac = "#146C43", "▼", "#D1FAE5"
    else:
        bg, arrow, ac = "#3A3D44", "→", "#E6E9EE"
    detail = html.escape(detail or "")
    face = "Arial,Helvetica,sans-serif"
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:12px 0 14px 0"><tr>'
            f'<td bgcolor="{bg}" style="background:{bg};border-radius:16px;padding:14px 18px">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td valign="middle" style="font:700 64px/1 {face};color:{ac};padding:0 16px 0 0">{arrow}</td>'
            f'<td valign="middle"><div style="font:700 22px/1.1 {face};letter-spacing:1.6px;color:#FFFFFF">{word}</div>'
            f'<div style="font:600 16px/1.3 {face};color:#F5F5F7;margin-top:4px">{detail}</div>'
            f'</td></tr></table></td></tr></table>')


def trend_chart(vals, label="24h"):
    """Wide report-count chart. The shade follows the series: amber-red when the later bars are higher, green when lower."""
    if not vals or len(vals) < 2: return None
    w, h = 520, 148
    pix = _blank(w, h, BG)
    k = max(1, len(vals) // 3)
    a, b = sum(vals[:k]) / k, sum(vals[-k:]) / k
    if b >= a * 1.34 and b >= a + 1:
        fill, line, word = (120, 32, 40), (255, 120, 90), "UP"
    elif a >= b * 1.34 and a >= b + 1:
        fill, line, word = (18, 78, 52), (90, 200, 140), "DOWN"
    else:
        fill, line, word = (42, 46, 54), (190, 196, 204), "FLAT"
    _text(pix, f"{label} {word}", 14, 8, line, 2)
    top, bot = 40, 128
    mx = max(vals) or 1
    n = len(vals)
    xs, ys = [], []
    for i, v in enumerate(vals):
        xs.append(18 + int(i * (w - 36) / (n - 1)))
        ys.append(bot - int((bot - top) * (v / mx)))
    for i in range(n - 1):
        x0, x1 = xs[i], xs[i + 1]
        span = max(1, x1 - x0)
        for x in range(x0, min(w, x1 + 1)):
            y = int(ys[i] + (ys[i + 1] - ys[i]) * ((x - x0) / span))
            for yy in range(max(top, y), bot):
                if (yy + x) % 2 == 0: pix[yy][x] = fill
    for i in range(n - 1):
        _line(pix, xs[i], ys[i], xs[i + 1], ys[i + 1], line)
        _line(pix, xs[i], min(h - 1, ys[i] + 1), xs[i + 1], min(h - 1, ys[i + 1] + 1), line)
    _hline(pix, bot, (90, 94, 102), 16, w - 16)
    _text(pix, "EARLIER", 16, bot + 4, MUTED, 1)
    _text(pix, "NOW", w - 36, bot + 4, MUTED, 1)
    return png_bytes(pix)
