"""Preppers add-on (tab "🎒 Preppers", REFERENCE group, deep link #preppers). Static, research-only reference:
a rated directory of preparedness suppliers and free official guidance (preppers_data.py), custom SVG emblems per source
(generated here, no logos or trademarks), and a client-side supply planner. No affiliate links, nothing purchased, no tracking.
Never touches scanner.py, scoring, push.py, jets.py, config.json or blackout.db."""
import json, os, re, hashlib, importlib
import preppers_data as D
BASE = os.path.dirname(os.path.abspath(__file__)); STATIC = os.path.join(BASE, "preppers_static"); BADGES = os.path.join(STATIC, "badges")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
RUBRIC = [("rep", "Reputation & longevity"), ("qual", "Product quality & independent reviews"), ("value", "Value for money"),
          ("trans", "Transparency & warranty"), ("avail", "Availability")]

def slug(n): return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:60]
def band(r): return "blue" if r >= 9 else "green" if r >= 7 else "amber" if r >= 4 else "red"
BANDC = {"blue": "#58a6ff", "green": "#3fb950", "amber": "#faad14", "red": "#f85149"}

# ---- custom emblems: category glyph + monogram + per-source hue/pattern seeded from the name (no logos) ----
GLYPH = {  # simple 24x24 line glyphs, drawn by hand for this site
 "water": '<path d="M12 3C9 8 6 11 6 14.5a6 6 0 0 0 12 0C18 11 15 8 12 3Z"/>',
 "food": '<rect x="6" y="5" width="12" height="15" rx="2"/><path d="M6 9h12M6 16h12"/>',
 "medical": '<path d="M9 4h6v5h5v6h-5v5H9v-5H4V9h5Z"/>',
 "power": '<path d="M13 2 5 14h6l-1 8 8-12h-6Z"/>',
 "comms": '<path d="M12 21V10"/><circle cx="12" cy="8" r="2"/><path d="M7 4a8 8 0 0 0 0 9M17 4a8 8 0 0 1 0 9"/>',
 "ammo": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".8"/>',
 "ranges": '<circle cx="12" cy="12" r="8"/><path d="M12 2v6M12 16v6M2 12h6M16 12h6"/>',
 "camping": '<path d="M3 20 12 4l9 16Z"/><path d="M12 20v-6"/>',
 "tools": '<path d="M4 20 14 10"/><path d="M14 10c-1-3 1-6 4-6l-2 3 1 2 2 1 3-2c0 3-3 5-6 4"/>',
 "bags": '<rect x="5" y="7" width="14" height="14" rx="3"/><path d="M9 7V5a3 3 0 0 1 6 0v2M8 14h8"/>',
 "sanitation": '<circle cx="9" cy="14" r="5"/><circle cx="16" cy="7" r="3"/><circle cx="18" cy="15" r="2"/>',
 "heat": '<path d="M12 3c1 4 6 6 6 11a6 6 0 0 1-12 0c0-3 2-4 3-6 1 2 2 3 3 3 0-3-1-5 0-8Z"/>',
 "security": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6Z"/>',
 "docs": '<path d="M3 7h7l2 2h9v10H3Z"/>',
 "special": '<circle cx="7" cy="9" r="2"/><circle cx="12" cy="6" r="2"/><circle cx="17" cy="9" r="2"/><path d="M8 18c0-4 8-4 8 0 0 2-8 2-8 0Z"/>',
 "seeds": '<path d="M12 21v-9"/><path d="M12 12C12 7 8 5 4 5c0 4 3 7 8 7Z"/><path d="M12 14c0-4 3-6 8-6 0 4-3 6-8 6Z"/>',
 "nav": '<circle cx="12" cy="12" r="9"/><path d="m15 9-2 4-4 2 2-4Z"/>',
 "training": '<path d="M2 9 12 5l10 4-10 4Z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/>',
 "community": '<circle cx="8" cy="8" r="3"/><circle cx="16" cy="8" r="3"/><path d="M2 20c0-4 3-6 6-6s6 2 6 6M10 20c0-4 3-6 6-6s6 2 6 6"/>',
 "books": '<path d="M4 5h6a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H4ZM20 5h-6a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h6Z"/>',
}
def _pattern(k, c):
    return [f'<path d="M-10 10 10-10M-10 30 30-10M-10 50 50-10M-10 70 70-10M-10 90 90-10M10 90 90 10M30 90 90 30M50 90 90 50M70 90 90 70" stroke="{c}" stroke-width="5"/>',
            "".join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="{c}"/>' for x in range(6, 90, 12) for y in range(6, 90, 12)),
            "".join(f'<path d="M0 {y} 80 {y}" stroke="{c}" stroke-width="2"/><path d="M{y} 0 {y} 80" stroke="{c}" stroke-width="2"/>' for y in range(8, 80, 16)),
            "".join(f'<path d="M-4 {y} 10 {y-9} 24 {y} 38 {y-9} 52 {y} 66 {y-9} 80 {y} 94 {y-9}" fill="none" stroke="{c}" stroke-width="3"/>' for y in range(10, 96, 14)),
            "".join(f'<circle cx="62" cy="18" r="{r}" fill="none" stroke="{c}" stroke-width="3"/>' for r in range(8, 90, 11)),
            "".join(f'<path d="M{x} 0 {x+40} 80" stroke="{c}" stroke-width="7"/>' for x in range(-40, 90, 22)),
            "".join(f'<polygon points="{x},{y-6} {x+6},{y} {x},{y+6} {x-6},{y}" fill="{c}"/>' for x in range(8, 90, 16) for y in range(8 + (x // 16 % 2) * 8, 90, 16)),
            "".join(f'<path d="M0 {y} Q20 {y-8} 40 {y} T80 {y}" fill="none" stroke="{c}" stroke-width="3"/>' for y in range(6, 90, 10))][k]
def mono(name):
    w = [x for x in re.findall(r"[A-Za-z0-9]+", re.sub(r"\(.*?\)|^(the|a)\s", "", name, flags=re.I)) if x.lower() not in ("of", "and", "the", "for", "a", "s")]
    if not w: return "?"
    if w[0].isupper() and 2 <= len(w[0]) <= 4: return w[0]
    if len(w) == 1: return w[0][:2].upper()
    return (w[0][0] + w[1][0]).upper()
def _x(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
def badge(e):
    h = hashlib.sha256(e["name"].encode()).digest(); hue = (h[0] * 360 // 256 + D_CATHUE.get(e["cat"], 0)) % 360
    pat = h[1] % 8; tilt = (h[2] % 5 - 2) * 4; m = mono(e["name"]); rc = BANDC[band(e["rating"])]
    fs = 30 if len(m) <= 2 else 23 if len(m) == 3 else 18
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80" role="img" aria-label="{_x(e['name'])} emblem">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl({hue},55%,32%)"/><stop offset="1" stop-color="hsl({(hue+38)%360},60%,14%)"/></linearGradient>
<clipPath id="c"><rect x="3" y="3" width="74" height="74" rx="16"/></clipPath></defs>
<rect x="3" y="3" width="74" height="74" rx="16" fill="url(#g)"/>
<g clip-path="url(#c)" opacity=".16" transform="rotate({tilt} 40 40)">{_pattern(pat, f"hsl({hue},80%,80%)")}</g>
<rect x="3" y="3" width="74" height="74" rx="16" fill="none" stroke="{rc}" stroke-width="3"/>
<g transform="translate(8 8) scale(.85)" fill="none" stroke="hsl({hue},90%,85%)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{GLYPH.get(e['cat'], '')}</g>
<text x="40" y="{60 if len(m) <= 2 else 58}" text-anchor="middle" font-family="system-ui,Segoe UI,Roboto,sans-serif" font-weight="800" font-size="{fs}" fill="#fff" letter-spacing=".5">{_x(m)}</text>
<circle cx="64" cy="16" r="9" fill="#0b0d10" stroke="{rc}" stroke-width="2"/><text x="64" y="20" text-anchor="middle" font-family="system-ui,sans-serif" font-weight="800" font-size="11" fill="{rc}">{e['rating']}</text>
</svg>'''
D_CATHUE = {c[0]: i * 17 for i, c in enumerate(D.CATS)}

def build():
    out = []; seen = set()
    lc = {}
    try: lc = json.load(open(os.path.join(STATIC, "linkcheck.json")))
    except Exception: pass
    for line in D.ROWS.strip().splitlines():
        name, url, cat, tags, region, tier, sc, note = [x.strip() for x in line.split("|")]
        parts = dict(zip([k for k, _ in RUBRIC], [int(c) for c in sc])); r = sum(parts.values())
        sid = slug(name)
        while sid in seen: sid += "-x"
        seen.add(sid)
        strong = [l for k, l in RUBRIC if parts[k] == 2]; weak = [l for k, l in RUBRIC if parts[k] == 0]; mid = [l for k, l in RUBRIC if parts[k] == 1]
        why = ("Full marks on all five criteria" if len(strong) == 5 else
               (f"Strong: {', '.join(s.split(' &')[0].lower() for s in strong[:3])}" if strong else "No top scores") +
               (f" · weaker: {', '.join(s.split(' &')[0].lower() for s in (weak + mid)[:2])}" if weak or mid else ""))
        out.append({"id": sid, "name": name, "url": url, "cat": cat, "tags": [t.strip() for t in tags.split(",") if t.strip()], "region": region,
                    "tier": tier, "note": note, "rating": r, "band": band(r), "parts": parts, "why": why,
                    "link": (lc.get("codes") or {}).get(url), "badge": f"api/preppers/badges/{sid}.svg"})
    return out

def write_badges():
    os.makedirs(BADGES, exist_ok=True); n = 0
    for e in build():
        p = os.path.join(BADGES, e["id"] + ".svg"); s = badge(e)
        if not os.path.exists(p) or open(p).read() != s: open(p, "w").write(s); n += 1
    return n

_cache = {"mt": None, "d": None}
def payload():
    mt = (os.path.getmtime(D.__file__), os.path.getmtime(__file__))
    if _cache["mt"] != mt:
        importlib.reload(D); entries = build()
        counts = {c: sum(1 for e in entries if e["cat"] == c) for c, _, _ in D.CATS}
        lc = {}
        try: lc = json.load(open(os.path.join(STATIC, "linkcheck.json")))
        except Exception: pass
        _cache.update(mt=mt, d={"entries": entries, "cats": [{"id": c, "label": l, "icon": i, "n": counts[c]} for c, l, i in D.CATS],
            "research": [{"name": a, "url": b, "cred": c, "desc": d} for a, b, c, d in D.RESEARCH],
            "rubric": [{"k": k, "label": l} for k, l in RUBRIC], "linkcheck": {"checked": lc.get("checked"), "note": lc.get("note")},
            "note": "Informational only, not an endorsement. No affiliate links; blackout.network earns nothing from these. Check local laws, especially for firearms, ammunition, fuel storage and radio transmitting."})
    return _cache["d"]

def handle_get(path, qs):
    n = path[len("/api/preppers/"):] if path.startswith("/api/preppers/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    m = re.fullmatch(r"badges/([a-z0-9\-]+)\.svg", n)
    if m:
        p = os.path.join(BADGES, m.group(1) + ".svg")
        if os.path.exists(p):
            with open(p, "rb") as fh: return 200, fh.read(), "image/svg+xml"
        return 404, {"error": "no such badge"}
    if path in ("/api/preppers", "/api/preppers/"): return 200, payload()
    return 404, {"error": "not found"}

if __name__ == "__main__": print(write_badges(), "badges written")
