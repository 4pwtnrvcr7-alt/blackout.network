"""BLACKOUT.NETWORK design v3, phase 1 (2026-11-02): tokens, full-page menu, accordions, and two data-fed Wire bands.

Serves /bn-v3.css and /bn-v3.js (injected on every full page by server.version_assets) and the Wire bands:
  * "Top of mind"   <- data/top_of_mind.json   (up to 4 cards; the team edits this file)
  * "What's coming" <- data/whats_coming.json  (dated items 0-14 days ahead)
Both bands render server-side into dashboard.html (<!--BN_V3_WIRE-->), so they work without JavaScript, and are refreshed
from /api/v3/wire. A card or item without its required fields (or without an http(s) source link) is dropped; when nothing
valid is left the band is not rendered at all. Nothing is ever filled in or guessed here: no data file = no band.
Kill switch: BN_DESIGN_V3=0 turns the whole v3 layer off (no CSS/JS injection, no bands)."""
import os, json, html, time, datetime
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
ET = ZoneInfo("America/New_York")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
ENABLED = lambda: os.environ.get("BN_DESIGN_V3", "1") != "0"
MAX_CARDS, MAX_ITEMS, HORIZON_DAYS = 4, 10, 14
CARD_MAX_AGE_H = float(os.environ.get("BN_TOM_MAX_AGE_H", "96"))   # a card older than this is treated as stale and hidden

# Topic illustrations (inline SVG, animated in bn-v3.css; currentColor = the card's category accent).
ART = {
 "conflict": '<svg viewBox="0 0 120 80" aria-hidden="true" focusable="false"><circle class="v3a-ring" cx="60" cy="40" r="30"/><circle class="v3a-ring v3a-d2" cx="60" cy="40" r="18"/><path class="v3a-sweep" d="M60 40 L60 10 A30 30 0 0 1 86 25 Z"/><path class="v3a-cross" d="M60 4v14M60 62v14M24 40h14M82 40h14"/><circle class="v3a-blip" cx="74" cy="28" r="3"/><circle class="v3a-blip v3a-d3" cx="46" cy="52" r="2.4"/></svg>',
 "unrest": '<svg viewBox="0 0 120 80" aria-hidden="true" focusable="false"><path class="v3a-wave" d="M4 52 Q19 38 34 52 T64 52 T94 52 T124 52"/><path class="v3a-wave v3a-d2" d="M4 62 Q19 50 34 62 T64 62 T94 62 T124 62"/><g class="v3a-crowd"><circle cx="30" cy="30" r="5"/><circle cx="48" cy="26" r="5"/><circle cx="66" cy="30" r="5"/><circle cx="84" cy="26" r="5"/><path d="M22 46q8-10 16 0M40 42q8-10 16 0M58 46q8-10 16 0M76 42q8-10 16 0"/></g></svg>',
 "elections": '<svg viewBox="0 0 120 80" aria-hidden="true" focusable="false"><rect class="v3a-box" x="34" y="34" width="52" height="38" rx="4"/><path class="v3a-slot" d="M48 34h24"/><rect class="v3a-ballot" x="50" y="6" width="20" height="26" rx="2"/><path class="v3a-tick" d="M55 19l4 4 7-8"/><g class="v3a-bars"><rect x="8" y="56" width="6" height="16"/><rect x="16" y="48" width="6" height="24"/><rect x="98" y="52" width="6" height="20"/><rect x="106" y="44" width="6" height="28"/></g></svg>',
 "economy": '<svg viewBox="0 0 120 80" aria-hidden="true" focusable="false"><path class="v3a-grid" d="M8 70h104M8 50h104M8 30h104"/><path class="v3a-line" d="M8 62 L28 54 L44 58 L62 40 L78 44 L96 24 L112 18"/><circle class="v3a-dot" cx="112" cy="18" r="3.5"/><text class="v3a-pct" x="14" y="22">%</text></svg>',
 "other": '<svg viewBox="0 0 120 80" aria-hidden="true" focusable="false"><circle class="v3a-ring" cx="60" cy="40" r="26"/><path class="v3a-line" d="M20 40h20l6-14 10 28 8-20 6 6h30"/></svg>',
}
CAT_ALIAS = {"war": "conflict", "conflict": "conflict", "unrest": "unrest", "migration": "unrest", "elections": "elections", "election": "elections",
             "politics": "elections", "economy": "economy", "inflation": "economy", "rates": "economy"}
CAT_VAR = {"conflict": "conflict", "unrest": "unrest", "elections": "elections", "economy": "economy", "space": "space", "weather": "weather",
           "seismic": "seismic", "cyber": "cyber", "disease": "disease", "health": "health", "grid": "grid", "aviation": "aviation", "government": "government"}

def _url_ok(u): return isinstance(u, str) and (u.startswith("https://") or u.startswith("http://")) and len(u) < 600
def _internal_ok(u): return isinstance(u, str) and u.startswith("/") and not u.startswith("//") and len(u) < 200
def _txt(x, n): return " ".join(str(x).split())[:n] if isinstance(x, (str, int, float)) and str(x).strip() else ""

def _parse_ts(s):
    if not s: return None
    try:
        d = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=ET)
    except Exception: return None

def _load(name):
    p = os.path.join(DATA, name)
    try:
        with open(p, encoding="utf-8") as f: return json.load(f), os.path.getmtime(p)
    except Exception: return None, None

def _sources(c):
    out = []
    for s in ([c.get("source")] if isinstance(c.get("source"), dict) else []) + [x for x in (c.get("sources") or []) if isinstance(x, dict)]:
        if _url_ok(s.get("url")) and _txt(s.get("name"), 60): out.append({"name": _txt(s["name"], 60), "url": s["url"]})
    seen, uniq = set(), []
    for s in out:
        if s["url"] not in seen: seen.add(s["url"]); uniq.append(s)
    return uniq[:3]

def top_of_mind(now=None):
    """Valid cards only (max 4). Required: title, status, latest, why, as_of, and at least one http(s) source with a name."""
    d, mt = _load("top_of_mind.json")
    if not isinstance(d, dict) or not isinstance(d.get("cards"), list): return {"cards": [], "updated": None}
    now = now or datetime.datetime.now(datetime.timezone.utc); cards = []
    for c in d["cards"]:
        if not isinstance(c, dict): continue
        t, st, la, wy = _txt(c.get("title"), 60), _txt(c.get("status"), 140), _txt(c.get("latest"), 260), _txt(c.get("why"), 240)
        src = _sources(c); ts = _parse_ts(c.get("as_of"))
        if not (t and st and la and wy and src and ts): continue
        if (now - ts).total_seconds() > CARD_MAX_AGE_H * 3600 or ts > now + datetime.timedelta(hours=1): continue
        cat = CAT_ALIAS.get(str(c.get("category", "")).lower(), "other")
        cards.append({"id": _txt(c.get("id"), 40) or t.lower().replace(" ", "-"), "title": t, "category": cat, "status": st, "latest": la,
                      "why": wy, "as_of": ts.isoformat(), "sources": src, "link": c.get("link") if _internal_ok(c.get("link")) else None,
                      "level": c.get("level") if c.get("level") in ("low", "elevated", "high", "critical") else None})
        if len(cards) >= MAX_CARDS: break
    return {"cards": cards, "updated": d.get("updated")}

def whats_coming(now=None):
    """Dated items from today to +14 days (ET), soonest first. Required: date (YYYY-MM-DD), title, and an http(s) source."""
    d, mt = _load("whats_coming.json")
    if not isinstance(d, dict) or not isinstance(d.get("items"), list): return {"items": [], "updated": None}
    today = (now or datetime.datetime.now(ET)).astimezone(ET).date(); items = []
    for it in d["items"]:
        if not isinstance(it, dict): continue
        try: day = datetime.date.fromisoformat(str(it.get("date", ""))[:10])
        except Exception: continue
        t, src = _txt(it.get("title"), 90), _sources(it)
        dd = (day - today).days
        if not (t and src) or dd < 0 or dd > HORIZON_DAYS: continue
        tm = _txt(it.get("time"), 12)
        cat = str(it.get("category", "")).lower(); cat = CAT_VAR.get(CAT_ALIAS.get(cat, cat), "other")
        items.append({"date": day.isoformat(), "days": dd, "time": tm, "title": t, "detail": _txt(it.get("detail"), 160), "category": cat,
                      "kind": "hazard" if it.get("kind") == "hazard" else "event", "sources": src,
                      "link": it.get("link") if _internal_ok(it.get("link")) else None})
    items.sort(key=lambda x: (x["date"], x["time"] or "99"))
    return {"items": items[:MAX_ITEMS], "updated": d.get("updated")}

def _fmt_asof(iso):
    try:
        d = datetime.datetime.fromisoformat(iso).astimezone(ET)
        return d.strftime("%b %-d, %-I:%M %p ET")
    except Exception: return ""

def _src_links(srcs, cls="v3-src"):
    return " ".join(f'<a class="{cls}" href="{E(s["url"])}" target="_blank" rel="noopener noreferrer">{E(s["name"])}</a>' for s in srcs)

def tom_html(tom=None):
    tom = tom if tom is not None else top_of_mind()
    if not tom["cards"]: return ""
    out = ['<section class="v3-band v3-tom" id="top-of-mind" aria-labelledby="v3_tom_h"><div class="v3-band-h"><span class="v3-live" aria-hidden="true"></span>'
           '<h2 id="v3_tom_h">Top of mind</h2><span class="v3-band-sub">The four stories shaping risk right now. Sourced, updated by the BLACKOUT.NETWORK desk.</span></div><div class="v3-tom-grid">']
    for i, c in enumerate(tom["cards"]):
        lvl = f' data-level="{c["level"]}"' if c["level"] else ""
        more = f'<a class="v3-more" href="{E(c["link"])}">Follow on BLACKOUT.NETWORK</a>' if c["link"] else ""
        out.append(f'<article class="v3-card v3-cat-{c["category"]}" style="--i:{i}" id="tom-{E(c["id"])}"{lvl}>'
                   f'<div class="v3-art">{ART.get(c["category"], ART["other"])}</div>'
                   f'<div class="v3-card-b"><h3>{E(c["title"])}</h3><p class="v3-status">{E(c["status"])}</p>'
                   f'<dl><dt>Latest</dt><dd>{E(c["latest"])}</dd><dt>Why it matters now</dt><dd>{E(c["why"])}</dd></dl>'
                   f'<p class="v3-meta"><span>As of {E(_fmt_asof(c["as_of"]))}</span><span class="v3-srcs">Source: {_src_links(c["sources"])}</span></p>{more}</div></article>')
    out.append('</div></section>')
    return "".join(out)

def wc_html(wc=None):
    wc = wc if wc is not None else whats_coming()
    if not wc["items"]: return ""
    today = datetime.datetime.now(ET).date()
    ticks = "".join(f'<i style="--d:{n}"' + (' class="v3-wk"' if (today + datetime.timedelta(days=n)).weekday() == 0 else "") + '></i>' for n in range(HORIZON_DAYS + 1))
    out = ['<section class="v3-band v3-wc" id="whats-coming" aria-labelledby="v3_wc_h"><div class="v3-band-h">'
           '<h2 id="v3_wc_h">What\'s coming</h2><span class="v3-band-sub">Dated hazards and events in the next 14 days, each linked to its source.</span></div>'
           f'<div class="v3-track" aria-hidden="true"><div class="v3-track-line"></div><div class="v3-ticks">{ticks}</div>'
           + "".join(f'<span class="v3-pin v3-cat-{it["category"]}" style="--d:{it["days"]};--i:{n}"></span>' for n, it in enumerate(wc["items"])) +
           '<span class="v3-today">Today</span><span class="v3-end">+14 days</span></div><ol class="v3-wc-list">']
    for n, it in enumerate(wc["items"]):
        day = datetime.date.fromisoformat(it["date"])
        when = "Today" if it["days"] == 0 else "Tomorrow" if it["days"] == 1 else f'In {it["days"]} days'
        tm = f' · {E(it["time"])}' if it["time"] else ""
        link = f' <a class="v3-more" href="{E(it["link"])}">Our coverage</a>' if it["link"] else ""
        out.append(f'<li class="v3-wc-it v3-cat-{it["category"]} v3-{it["kind"]}" style="--i:{n}" data-date="{it["date"]}">'
                   f'<time datetime="{it["date"]}"><b>{day.strftime("%a")}</b><span>{day.strftime("%b %-d")}</span></time>'
                   f'<div><p class="v3-wc-t">{E(it["title"])}</p>'
                   + (f'<p class="v3-wc-d">{E(it["detail"])}</p>' if it["detail"] else "") +
                   f'<p class="v3-meta"><span class="v3-when">{when}{tm}</span><span class="v3-srcs">Source: {_src_links(it["sources"])}</span>{link}</p></div></li>')
    out.append('</ol></section>')
    return "".join(out)

def wire_html():
    if not ENABLED(): return ""
    try: return tom_html() + wc_html()
    except Exception: return ""

def _static(name, ctype):
    with open(os.path.join(BASE, "static", name), "rb") as f: return 200, f.read(), ctype

def handle_get(path, qs):
    if path == "/bn-v3.css": return _static("bn-v3.css", "text/css")
    if path == "/bn-v3.js": return _static("bn-v3.js", "application/javascript")
    if path == "/api/v3/wire":
        if not ENABLED(): return 200, {"enabled": False, "html": ""}
        tom, wc = top_of_mind(), whats_coming()
        return 200, {"enabled": True, "top_of_mind": tom, "whats_coming": wc, "html": tom_html(tom) + wc_html(wc), "generated": int(time.time())}
    return 404, {"error": "not found"}
