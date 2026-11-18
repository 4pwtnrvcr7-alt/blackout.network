"""New site theme (Matt, Nov 17 2026 12:10 AM ET): "/" is the cinematic onboarding, the dashboard lives on /live.

Routes (addons.py): /bnt/<asset>          shared theme + homepage + /live overview CSS/JS (theme_static/), immutable when ?v= is given
                    /bnt/media/<clip>     background loops + posters (theme_static/media/*.b64, decoded once, HTTP Range for iOS)
                    /api/live/summary     small read-only summary of /api/state for the homepage numbers and the /live overview (60 s cache)
server.py calls home_page() for "/" and live_overview_html() for "/live". Kill switch: BN_NEW_HOME=0 (Render env) serves the old "/".
Media is committed as base64 text because the deploy path only carries text; it is decoded in memory on first request.
No scanner, scoring or write paths are touched here."""
import base64, hashlib, html, json, os, re, sys, threading, time
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "theme_static")
MEDIA = os.path.join(STATIC, "media")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
TYPES = {".css": "text/css", ".js": "application/javascript", ".json": "application/json"}
ASSETS = ("theme.css", "theme.js", "home.css", "home.js", "live.css", "live.js", "land.json", "snap.js", "tabhero.css", "tabhero.js")
MTYPES = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".webm": "video/webm"}

def enabled(): return os.environ.get("BN_NEW_HOME", "1").strip() != "0"

_V = {"t": 0, "v": {}, "m": "0"}
def versions():
    """Content hash per asset (short), plus one media version; recomputed at most every 20 s."""
    if time.time() - _V["t"] > 20:
        v = {}
        for a in ASSETS:
            try: v[a] = hashlib.sha1(open(os.path.join(STATIC, a), "rb").read()).hexdigest()[:10]
            except Exception: v[a] = "0"
        h = hashlib.sha1()
        try:
            for n in sorted(os.listdir(MEDIA)): h.update(n.encode()); h.update(str(os.path.getsize(os.path.join(MEDIA, n))).encode())
        except Exception: pass
        _V.update(t=time.time(), v=v, m=h.hexdigest()[:10])
    return _V["v"], _V["m"]

def url(a): return f"/bnt/{a}?v={versions()[0].get(a, '0')}"

def head_links():
    """Shared theme on every full HTML page (server.pwa_head)."""
    return (f'<link rel="stylesheet" href="{url("theme.css")}"><script src="{url("theme.js")}" defer></script>').encode()

# ---------- media (Range) ----------
_media, _mlock = {}, threading.Lock()
def _media_bytes(name):
    if not re.fullmatch(r"[a-z]+-[dm]\.(mp4|jpg|webm)", name): return None
    with _mlock:
        if name not in _media:
            p = os.path.join(MEDIA, name + ".b64")
            if os.path.exists(p): raw = open(p, "rb").read()
            else:   # large clips ship as ordered text parts (<name>.b64.p00, .p01, ...) because the repo tools commit text only
                parts = sorted(f for f in os.listdir(MEDIA) if re.fullmatch(re.escape(name) + r"\.b64\.p\d\d", f))
                if not parts: return None
                raw = b"".join(open(os.path.join(MEDIA, f), "rb").read() for f in parts)
            _media[name] = base64.b64decode(raw)
        return _media[name]

def _raw(h, code, body, ctype, cache, extra=()):
    h.send_response(code); h.send_header("Content-Type", ctype)
    h.send_header("Cache-Control", cache); h.send_header("X-Content-Type-Options", "nosniff")
    for k, v in extra: h.send_header(k, v)
    h.send_header("Content-Length", str(len(body))); h.end_headers()
    if getattr(h, "command", "GET") != "HEAD": h.wfile.write(body)

def _serve_media(name, qs, h):
    b = _media_bytes(name)
    if b is None: return _raw(h, 404, b"not found", "text/plain; charset=utf-8", "no-store")
    ct = MTYPES[os.path.splitext(name)[1]]
    cache = "public, max-age=31536000, immutable" if qs.get("v") else "public, max-age=3600"
    rng = h.headers.get("Range") or ""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
    if m and (m.group(1) or m.group(2)):
        n = len(b)
        if m.group(1): s = int(m.group(1)); e = min(int(m.group(2)) if m.group(2) else n - 1, n - 1)
        else: s = max(0, n - int(m.group(2))); e = n - 1
        if s >= n or s > e: return _raw(h, 416, b"", ct, cache, (("Content-Range", f"bytes */{n}"), ("Accept-Ranges", "bytes")))
        return _raw(h, 206, b[s:e + 1], ct, cache, (("Content-Range", f"bytes {s}-{e}/{n}"), ("Accept-Ranges", "bytes")))
    return _raw(h, 200, b, ct, cache, (("Accept-Ranges", "bytes"),))

# ---------- live summary ----------
def _srv():
    m = sys.modules.get("server")
    return m if m is not None and hasattr(m, "api_state") else sys.modules.get("__main__")

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception: ET = timezone(timedelta(hours=-5))
def _t(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None
def _et(s, fmt="%-I:%M %p ET"):
    d = _t(s)
    return d.astimezone(ET).strftime(fmt) if d else ""

_EMO = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")
def _clean(t): return re.sub(r"\s{2,}", " ", _EMO.sub("", str(t or ""))).strip()
def _headline(t):
    """Nov 17 3 AM: clean short display headline (display only; scanner data/scoring untouched). Mirrors wire_page_static/app.js cleanTitle."""
    t = _clean(t)
    g = re.match(r"^(Green|Orange|Red) (?:notification|alert) for (.+?)(?:\.\s|\.$|$)", t, re.I)
    if g:
        ev = re.sub(r"^(an?|the) ", "", g.group(2), flags=re.I); return ev[:1].upper() + ev[1:] + " (" + g.group(1).lower() + " alert)"
    g = re.match(r"^(Green|Orange|Red) (earthquake|flood|drought|tropical cyclone|volcano|wildfire|forest fire)\b.{0,80}?\bin ([A-Z][A-Za-z .-]{1,40}?)(?= \d| \(|,|\.|$)", t)
    if g: return g.group(2)[:1].upper() + g.group(2)[1:] + " in " + g.group(3).strip() + " (" + g.group(1).lower() + " alert)"
    b = re.match(r"^[A-Za-z /&-]{3,40} \| (.{12,})$", t)
    if b: t = b.group(1)
    t = re.sub(r"^\d{1,2}/10\s+", "", t)
    r = re.match(r"^(.{30,160}?[a-z0-9)]) (?:At least|According to|Officials|Authorities|It is|This is)\b", t)
    if r: t = r.group(1)
    return _short(t, 120)
def _short(t, n):
    if len(t) <= n: return t
    return t[:n].rsplit(" ", 1)[0].rstrip(" ,;:|-") + "\u2026"
CAT_NAMES = {"natural disaster": "Weather & quakes", "war/conflict": "Conflict", "disease": "Health", "cyber": "Cyber", "financial": "Markets & banking", "political": "Politics"}

_sum = {"t": 0, "v": None}
_slock = threading.Lock()
def summary(fresh=False):
    """fresh=True (a module refresh button) rebuilds once the copy is 15 s old; otherwise 60 s."""
    with _slock:
        if _sum["v"] and time.time() - _sum["t"] < (15 if fresh else 60): return _sum["v"]
    st = _srv().api_state()
    m = st.get("main") or []
    rk = lambda x: int(x.get("rank") or 0)
    ranks = {str(k): 0 for k in range(11)}
    for x in m: ranks[str(max(0, min(10, rk(x))))] += 1
    bands = {"calm": sum(1 for x in m if rk(x) <= 3), "elevated": sum(1 for x in m if 4 <= rk(x) <= 6), "high": sum(1 for x in m if rk(x) >= 7)}
    fam = lambda x: int(x.get("n_families") or x.get("eff_families") or len(x.get("families") or []) or 0)
    tops = sorted([x for x in m if fam(x) >= 2], key=lambda x: (rk(x), x.get("score") or 0), reverse=True)[:6]
    top = [{"title": _headline(x.get("title")), "full": _short(_clean(x.get("title")), 400), "loc": _clean(x.get("location"))[:60], "cat": x.get("category") or "", "rank": rk(x),
            "sources": fam(x), "rising": bool(x.get("rising")), "first_seen_et": _et(x.get("first_seen"), "%b %-d, %-I:%M %p ET"),
            "url": "/wire/" + str(x.get("cluster_id") or "")} for x in tops]
    # Gauge (Matt Nov 17 1:08 AM): average rank of the current top stories, i.e. the rank 7+ items on the main feed
    # (The Wire's High section, the Top Signals / newsletter pool). Fewer than 3 -> the top 10 by rank. Read-only; no scoring change.
    lead = [x for x in m if rk(x) >= 7]
    if len(lead) < 3: lead = sorted(m, key=lambda x: (rk(x), x.get("score") or 0), reverse=True)[:10]
    # Gauge explainer (Matt Nov 17 2:26 AM): just the highest threat right now, the top-ranked active alert on the main feed.
    hx = max(m, key=lambda x: (rk(x), x.get("score") or 0)) if m else None
    hi = {"title": _headline(hx.get("title")), "rank": rk(hx), "url": "/wire/" + str(hx.get("cluster_id") or "")} if hx else None
    vol = {}
    for v in st.get("volume") or []:
        dd = vol.setdefault(v.get("d"), {}); dd[v.get("category")] = dd.get(v.get("category"), 0) + int(v.get("n") or 0)
    days = sorted(k for k in vol if k)
    lab = lambda k, f: datetime.strptime(k, "%Y-%m-%d").strftime(f) if re.fullmatch(r"\d{4}-\d\d-\d\d", str(k)) else str(k)
    today = days[-1] if days else None
    cats = {CAT_NAMES.get(k, str(k).title()): n for k, n in (vol.get(today) or {}).items() if k in CAT_NAMES}
    src = st.get("sources") or []; sc = (st.get("scans") or [{}])[0] or {}
    last = sc.get("finished") or st.get("generated")
    out = {"generated": st.get("generated"), "wire": len(m), "watch": st.get("watchlist_count") or 0, "ranks": ranks, "bands": bands,
           "level": round(sum(rk(x) for x in lead) / len(lead), 1) if lead else 0.0, "level_n": len(lead), "level_hi": len(lead) > 0 and all(rk(x) >= 7 for x in lead),
           "wire_avg": round(sum(rk(x) for x in m) / len(m), 1) if m else 0.0, "max_rank": max([rk(x) for x in m] or [0]), "hi": hi,
           "top": top, "geo": [[round(float(x["lat"]), 2), round(float(x["lon"]), 2), rk(x)] for x in m if x.get("lat") is not None and x.get("lon") is not None],
           "volume": [{"d": lab(k, "%a"), "n": sum(vol[k].values())} for k in days], "cats": cats, "today": lab(today, "%a %b %-d") if today else "",
           "sources_ok": sum(1 for s in src if s.get("ok")), "sources_total": len(src),
           "last_scan": last, "last_scan_et": _et(last), "fetched": int(sc.get("fetched") or 0), "new_items": int(sc.get("new_items") or 0),
           "interval": st.get("interval_minutes")}
    with _slock: _sum.update(t=time.time(), v=out)
    return out

# ---------- routes ----------
def handle_stream(path, qs, h):
    if path == "/api/live/summary":
        try: return h.send(200, summary(fresh=(qs.get("fresh") or ["0"])[0] == "1"))
        except Exception as ex:
            import traceback; traceback.print_exc(); return h.send(503, {"error": "summary unavailable"})
    if path.startswith("/bnt/media/"):
        return _serve_media(path[len("/bnt/media/"):], qs, h)
    a = path[len("/bnt/"):] if path.startswith("/bnt/") else ""
    if a in ASSETS:
        b = open(os.path.join(STATIC, a), "rb").read()
        return _raw(h, 200, b, TYPES[os.path.splitext(a)[1]] + "; charset=utf-8", "public, max-age=31536000, immutable" if qs.get("v") else "public, max-age=300")
    if path in ("/credits", "/credits/"):
        return h.send(200, credits_page(), "text/html")
    if a == "credits.txt":
        return _raw(h, 200, CREDITS.encode(), "text/plain; charset=utf-8", "public, max-age=3600")
    return _raw(h, 404, b'{"error":"not found"}', "application/json; charset=utf-8", "no-store")

def handle_get(path, qs):   # not used (handle_stream takes every path); kept for tools that probe add-ons
    return 404, {"error": "not found"}

CREDITS = """BLACKOUT.NETWORK homepage footage credits
Section 1 (hero): NASA, International Space Station imagery of Hurricane Erin, 2025. Public domain.
Section 2 (live map): BLACKOUT.NETWORK Heat Map, own screen capture.
Section 3 (ranking): NASA, International Space Station imagery of Hurricane Dorian, 2019. Public domain.
Section 4 (coverage): NASA Goddard / Solar Dynamics Observatory, solar flare, 2016. Public domain.
Section 5 (languages): NASA, International Space Station, Earth limb, 2024. Public domain.
Section 6 (newsletter): NASA, International Space Station, Earth from orbit, 2019. Public domain.
Section 7 (dashboard): BLACKOUT.NETWORK live dashboard, own capture.
NASA imagery is used under NASA's media usage guidelines; NASA does not endorse BLACKOUT.NETWORK.
"""


# ---------- /credits (Matt 12:07 PM: one shared credits page fed from this ledger; footer link "Image credits" on every page) ----------
CREDITS_LEDGER = [
 ("intro", "Intro (/)", [
  ("Section 1 background video", "NASA, International Space Station imagery of Hurricane Erin, 2025", "Public domain (NASA media guidelines)"),
  ("Section 2 background video", "BLACKOUT.NETWORK Heat Map, own screen capture", "BLACKOUT.NETWORK"),
  ("Section 3 background video", "NASA, International Space Station imagery of Hurricane Dorian, 2019", "Public domain"),
  ("Section 4 background video", "NASA Goddard / Solar Dynamics Observatory, solar flare, 2016", "Public domain"),
  ("Section 5 background video", "NASA, International Space Station, Earth limb, 2024", "Public domain"),
  ("Section 6 background video", "NASA, International Space Station, Earth from orbit, 2019", "Public domain"),
  ("Section 7 background video", "BLACKOUT.NETWORK live dashboard, own capture", "BLACKOUT.NETWORK")]),
 ("live", "Live (/live)", [
  ("Hero background video (desktop/tablet)", "NASA, \"Earth Views from the ISS - No Music\" (NHQ_2020_1221), 2020; segment graded grey with a cool tone, crossfaded loop", "Public domain"),
  ("Hero image (phones, reduced motion, Save-Data)", "NASA JSC, ISS Expedition 60, iss060e022358 (stars over Earth's limb); grey with a cool tone", "Public domain")]),
 ("latest", "Latest pages (/live#streams, #noise, #heatmap, #trends, #broadcasts, #radio)", [
  ("Live TV & Radio header video", "NASA JSC, \"4K Earth Views Extended Cut for Earth Day 2021\" (jsc2021m000138), ISS solar array over Earth", "Public domain"),
  ("Background Noise header video", "NASA JSC, jsc2021m000138, cloud fields over the Earth limb", "Public domain"),
  ("Heat Map header video", "NASA Goddard, \"Lights of Human Activity Shine in NASA's Image of Earth at Night\" (2017), Suomi NPP VIIRS city lights, slowed", "Public domain"),
  ("Trends header video", "NASA JSC, jsc2021m000138, mountain ridges and cloud bands from orbit", "Public domain"),
  ("Broadcast transcripts header video", "NASA JSC, jsc2021m000138, open-ocean cloud field", "Public domain"),
  ("Live Radio header video", "NASA JSC, jsc2021m000138, International Space Station modules over a storm system", "Public domain"),
  ("Note", "Header videos are graded grey and looped; phones and reduced-motion settings get a still frame from the same clip.", "")]),
 ("wire", "The Wire (/wire and story pages)", [
  ("List hero", "NASA JSC, ISS Expedition 70, iss070e062746 (city lights of North America), 2024", "Public domain"),
  ("Tropical cyclone stories (illustrative)", "NASA JSC, ISS Expedition 63, iss063e057876 (Hurricane Hanna), 2020. Illustrative, not the storm in the story", "Public domain"),
  ("Second cyclone story (illustrative)", "NASA JSC, ISS Expedition 57, iss057e023128 (Hurricane Michael), 2018. Illustrative", "Public domain"),
  ("Section band \"Watchlist\"", "NASA JSC, ISS Expedition 67, iss067e302248 (Mediterranean at night), 2022", "Public domain"),
  ("Health, conflict, finance and cyber graphics", "Original abstract graphics made for BLACKOUT.NETWORK (no real event)", "BLACKOUT.NETWORK"),
  ("Note on illustrative photos", "Storm and other story photos are illustrative: they show the same kind of event seen from orbit, not the specific event in the story.", "")]),
 ("crime", "Crime (/crime)", [
  ("Hero background video (desktop/tablet) and still", "\"Time Lapse 4K Midnight City\" (view from Blackpool Tower at night) by netLike, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:Time_Lapse_4K_Midnight_City.webm); 10-second segment, graded grey with a cool tone, cropped", "CC BY 3.0"),
  ("Reports and statistics panel", "\"Las Vegas Metropolitan Police\" by Tom\u00e1s Del Coro, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:Las_Vegas_Metropolitan_Police_(51346158527).jpg); graded grey with a cool tone, cropped", "CC BY-SA 2.0"),
  ("Cities and US counties panel; World panel", "\"City Timelapse - Free video\" (Stockholm at night) by Free Videos, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:City_Timelapse_-_Free_video.webm); two still frames, graded grey with a cool tone, cropped", "CC BY 3.0"),
  ("Note", "Atmospheric background imagery only. It does not show any incident, place or person named in the reports on the page.", "")]),
 ("stories", "Story pages (/wire/<id>, when Story v3 is on)", [
  ("MERS in Qatar hero (desktop video and still; phone still)", "NIAID, colorized scanning electron micrograph of Vero E6 cells infected with MERS-CoV (Flickr, 2017); graded monochrome for this page. Not a photograph of the patients or farms in this story.", "Public domain (U.S. government work)"),
  ("MERS in Qatar inline micrograph", "CDC / Maureen Metcalfe, Cynthia Goldsmith and Azaibi Tamin, transmission electron micrograph of MERS-CoV particles.", "Public domain"),
  ("Ebola in Congo (UNICEF child-toll story) hero", "CDC / Dr. Frederick Murphy, transmission electron micrograph of an Ebola virus particle. Laboratory image, not a photograph of this outbreak.", "Public domain"),
  ("Cyclone Akvan hero diagram", "Original BLACKOUT.NETWORK locator diagram. Storm position from GDACS / JTWC as of 17 Nov 2026; landfall stretch as reported from IMD via The Hindu. Not a satellite photograph of the storm.", "BLACKOUT.NETWORK"),
  ("Ebola reconstruction (human travel) hero diagram", "Original BLACKOUT.NETWORK diagram of places named in the Science reconstruction, plotted approximately. Not a surveyed map.", "BLACKOUT.NETWORK"),
  ("Fed AI / bank-run warning hero diagram", "Original BLACKOUT.NETWORK typographic diagram using a phrase from Governor Barr's 16 Nov 2026 speech. Not a photograph of any person or building.", "BLACKOUT.NETWORK")]),
]
def _nl_credits():
    """Newsletter topic divider images (newsletter_pool.json): one row per image, licence and author."""
    try:
        import json
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "newsletter_pool.json")))
        return [("newsletter", "Newsletter section images", [(f"{im['topic'].title()} divider ({im['name'].split('-')[0]})",
                 f"{im['title']}, {im['artist']}, via Wikimedia Commons ({im['page']})", im["license"]) for im in d.get("images") or []]
                 + [("Note", "Generic topic images that open each newsletter section. They do not show the events in the stories.", "")])]
    except Exception:
        return []
CREDITS_LEDGER += _nl_credits()
CREDITS_PAGE_KEY = {"/": "intro", "/live": "live", "/dashboard": "live", "/wire": "wire"}

def _credits_og():
    try:
        import og
        return og.tags(title="Image credits | BLACKOUT.NETWORK",
                       desc="Sources and licences for the images and video used on BLACKOUT.NETWORK.",
                       url="https://blackout.network/credits", key="credits")
    except Exception:
        return ('<meta property="og:type" content="website"><meta property="og:site_name" content="BLACKOUT.NETWORK">'
                '<meta property="og:title" content="Image credits | BLACKOUT.NETWORK">'
                '<meta property="og:description" content="Sources and licences for the images and video used on BLACKOUT.NETWORK.">'
                '<meta property="og:url" content="https://blackout.network/credits">'
                '<meta property="og:image" content="https://blackout.network/og/credits.png?v=5">'
                '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
                '<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://blackout.network/og/credits.png?v=5">'
                '<meta name="twitter:title" content="Image credits | BLACKOUT.NETWORK">')

def credits_page():
    try:
        import sitenav as SN, sitenav_ui as UI
        top, head = SN.header_html(""), UI.THEME_SCRIPT + '<script src="/sitenav.js" defer></script>'
    except Exception:
        top, head = "", ""
    secs = "".join(
        f'<section class="cr-sec" id="{k}"><h2>{html.escape(name)}</h2><ul>'
        + "".join(f'<li><b>{html.escape(a)}</b><span>{html.escape(b)}</span><em>{html.escape(c)}</em></li>' for a, b, c in rows)
        + "</ul></section>" for k, name, rows in CREDITS_LEDGER)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Image credits | BLACKOUT.NETWORK</title><meta name="description" content="Sources and licences for the images and video used on BLACKOUT.NETWORK.">'
            '<link rel="canonical" href="https://blackout.network/credits">' + _credits_og() +
            '<link rel="stylesheet" href="/sitenav.css">' + head +
            '<style>body{margin:0;background:#05060a;color:#ECEEF5;font:15px/1.6 Inter,system-ui,sans-serif}main{max-width:900px;margin:0 auto;padding:48px 20px 64px}'
            'h1{font:800 clamp(30px,4vw,46px)/1.05 Montserrat,system-ui,sans-serif;text-transform:uppercase;margin:0 0 10px}main>p.cr-lede{color:#9aa0aa;margin:0 0 36px;max-width:640px;display:block!important;-webkit-line-clamp:unset!important;overflow:visible!important;text-overflow:clip!important;white-space:normal!important}'
            '.cr-sec{border-top:1px solid rgba(236,238,245,.14);padding:22px 0 8px;scroll-margin-top:80px}.cr-sec h2{font:700 13px/1.2 Inter,system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;margin:0 0 14px}'
            '.cr-sec ul{list-style:none;margin:0;padding:0}.cr-sec li{display:grid;grid-template-columns:190px minmax(0,1fr) 210px;gap:6px 18px;padding:10px 0;border-bottom:1px solid rgba(236,238,245,.07)}'
            '.cr-sec b{font-weight:600}.cr-sec span{color:#C9CDD3}.cr-sec em{font-style:normal;color:#8b9099;font-size:13px}'
            '.cr-sec:target h2{color:#fff}@media(max-width:700px){.cr-sec li{grid-template-columns:1fr}}</style></head><body>' + top +
            '<main id="main"><h1>Image credits</h1><p class="cr-lede">Where every photo and video on this site comes from. NASA imagery is used under NASA\'s media usage guidelines; '
            'NASA does not endorse BLACKOUT.NETWORK.</p>' + secs + '</main></body></html>')

# ---------- "/" ----------
def _ic(p): return f'<svg viewBox="0 0 24 24" aria-hidden="true">{p}</svg>'
CHIPS = [
 ("Energy grid", '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>', "Grid load, outages and stress across North American power regions.", "/live#grid"),
 ("Markets & banking", '<path d="M3 20h18M5 16l4-5 4 3 6-8"/>', "Index moves, bank stress and the money stories behind them.", "/live#finance"),
 ("Solar & seismic", '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>', "Solar flares, the Kp index and earthquakes worldwide.", "/live#solar"),
 ("Health & outbreaks", '<path d="M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z"/>', "Outbreak reports from health agencies, ranked on The Wire.", "/wire"),
 ("Conflict", '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>', "Strikes, attacks and escalations, each linked to its sources.", "/wire"),
 ("Internet & cloud", '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>', "Country-level internet outages and cloud provider status.", "/live#network"),
 ("Weather", '<path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.5A3.5 3.5 0 0 1 17 18z"/>', "Severe weather warnings, radar and storms on one map.", "/live#weather"),
 ("AI threats", '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>', "Deepfakes, AI-driven attacks and the policy fights around them.", "/live#ai"),
]

def _menu():
    try:
        import sitenav, sitenav_ui
        secs = sitenav_ui.menu3_sections(sitenav)
    except Exception:
        secs = []
    out = []
    for i, (sid, name, desc, rows) in enumerate(secs):
        li = "".join(f'<li><a href="{E(re.sub(r"^/#", "/live#", href))}">{E(label)}</a></li>' for _, label, href in rows if href)
        out.append(f'<div class="bnt-acc"><button class="bnt-acc-h" aria-expanded="false" aria-controls="hm_{E(sid)}"><span>{E(name)}<small>{E(desc)}</small></span></button>'
                   f'<div class="bnt-acc-b" id="hm_{E(sid)}" hidden><div class="bnt-acc-in"><ul>{li}</ul></div></div></div>')
    return "".join(out)

def _newsletter_form():
    try:
        s = _srv()
        nl = s._addon_mod("newsletter") if s is not None and hasattr(s, "_addon_mod") else __import__("newsletter")
        return nl.form_html("card")
    except Exception:
        import traceback; traceback.print_exc()
        return '<p class="nl-sm"><a href="/newsletter">Sign up for the free brief</a></p>'

# Nov 17 (Matt 8:53 AM): the intro is always reachable from the wordmark and menu; the "skip next time" option and redirect are off. BN_INTRO_SKIP=1 restores them.
INTRO_SKIP = __import__("os").environ.get("BN_INTRO_SKIP", "0") == "1"
SKIPBOX = '<label class="h-skipbox"><input type="checkbox" id="h_skip"> Skip this intro next time</label>' if INTRO_SKIP else ""
HEAD_JS = ("(function(){try{var h=location.hash,s=location.search;"
           "if(h==='#heatmap'||h==='#map'){location.replace('/map'+s);return}"
           "if(h&&h!=='#'&&h!=='#bn-menu'&&!/^#(s[1-7]|intro|top)$/.test(h)){location.replace('/live'+s+h);return}"
           "var app=(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone===true;"
           + ("if(!/[?&]intro=1/.test(s)&&(app||localStorage.getItem('bn_skip_intro')==='1')){location.replace('/live'+s);return}" if INTRO_SKIP else "")
           + "}catch(e){}document.documentElement.classList.add('bnt-homepage')})()")
DESC = "Global threat monitoring: independent, sourced early-warning signals on US and world threats, ranked 0 to 10 and updated around the clock. Not official alerts."
ARROW = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M8 2v12M3 9l5 5 5-5"/></svg>'

def _home_page_raw():
    _, mv = versions()
    chips = "".join(
        f'<div class="h-chip bnt-peek" tabindex="0" aria-expanded="false"><span class="h-ct">{_ic(ic)}{E(t)}</span>'
        f'<div class="bnt-peek-d"><div><p>{E(dsc)} <a href="{E(href)}" class="h-cl">Open &rarr;</a></p></div></div></div>' for t, ic, dsc, href in CHIPS)
    wm = '<span class="bnt-wm">blackout.network</span>'
    m4 = __import__("os").environ.get("BN_MENU_V2", "1") != "0"   # Push H: SpaceX-language full-screen menu (BN_MENU_V2=0 = side drawer)
    m4cls = " h-menu4" if m4 else ""
    m4btn = ('<span class="bn-bl"><span class="bn-bl-a">Menu</span><span class="bn-bl-b">Close</span></span>' if m4 else "")
    hx = '<span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span>'
    mlead = ('<div class="h-m4lead"><a href="#s1" data-h-close>Intro</a><a href="/wire">The Wire</a><a href="/live">Live</a><a href="/newsletter">Newsletter</a></div>' if m4
             else '<a class="h-mlive" href="/live">Live dashboard</a><a class="h-mlive" href="/wire">The Wire</a>')
    snap = snap_on() and home_snap_on()   # Matt 4:07 PM: the intro scrolls freely and smoothly like the Wire, no section snap
    snapattr = " data-bn-snap" if snap else ""
    snapjs = f'<script src="{url("snap.js")}" defer></script>' if snap else ""
    return f'''<!doctype html><html lang="en" data-bnt-home><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<script>{HEAD_JS}</script>
<title>Global threat monitoring | BLACKOUT.NETWORK</title>
<meta name="description" content="{E(DESC)}">
<link rel="canonical" href="https://blackout.network/">
<meta property="og:type" content="website"><meta property="og:site_name" content="BLACKOUT.NETWORK"><meta property="og:title" content="Global threat monitoring | BLACKOUT.NETWORK">
<meta property="og:description" content="{E(DESC)}"><meta property="og:url" content="https://blackout.network/">
<meta property="og:image" content="https://blackout.network/og/home.png?v=5"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Global threat monitoring | BLACKOUT.NETWORK">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://blackout.network/og/home.png?v=5"><meta name="twitter:site" content="@BlkoutNtw">
<meta name="twitter:title" content="Global threat monitoring | BLACKOUT.NETWORK"><meta name="twitter:description" content="{E(DESC)}">
<link rel="preload" href="/fonts/montserrat-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" as="image" href="/bnt/media/hero-d.jpg?v={mv}" media="(min-width:901px)"><link rel="preload" as="image" href="/bnt/media/hero-m.jpg?v={mv}" media="(max-width:900px)">
<link rel="stylesheet" href="/api/translate/app.css"><link rel="stylesheet" href="/api/newsletter/app.css">
<link rel="stylesheet" href="{url("theme.css")}"><link rel="stylesheet" href="{url("home.css")}">
<script>window.BNT_MEDIA_V="{mv}"</script>
</head><body class="bnt-home" data-bn-noreport>
<a class="h-skip" href="#s6">Skip to the free brief</a>
<header class="h-nav" id="h_nav">
 <a class="h-wm" href="/live" aria-label="BLACKOUT.NETWORK live dashboard">{wm}</a>
 <nav class="h-links" aria-label="Primary"><a href="/map">Live map</a><a href="/wire">The Wire</a><a href="#s3">How it ranks</a><a href="#s6">Free brief</a></nav>
 <div class="h-right"><a class="h-go" href="/live">Open dashboard</a><button class="h-burger" type="button" data-h-menu aria-label="Open menu" aria-controls="h_menu" aria-expanded="false">{hx}{m4btn}</button></div>
</header>
<ol class="h-pager" id="h_pager" aria-hidden="true"></ol>
<main id="flow"{snapattr}>
<section class="h-sec"{" data-snap" if snap else ""} id="s1" data-clip="hero"><div class="h-copy">
 <p class="bnt-eyebrow">Early-warning signals &middot; 24/7</p>
 <h1 class="h-h">Global threat<br>monitoring</h1>
 <p class="h-lede">We scan official agencies, sensors and wires around the clock. Most events land here within minutes. Some reach the headlines hours or days later. Some never do.</p>
 <a class="bnt-btn" href="#s2">See what's happening {ARROW}</a>
</div><p class="h-credit">Footage: NASA (ISS, Hurricane Erin, 2025)</p></section>

<section class="h-sec"{" data-snap" if snap else ""} id="s2" data-clip="live"><div class="h-copy">
 <p class="bnt-eyebrow">The live scanner</p>
 <h2 class="h-h">Watch the world<br>as it happens</h2>
 <p class="h-lede">Quakes, storms, outbreaks, outages and conflict, pinned to one live map and sorted by what matters most.</p>
 <div class="h-stats" aria-live="polite"><div><b id="h_n_wire">&ndash;</b><span>alerts on The Wire</span></div><div><b id="h_n_src">&ndash;</b><span>sources online</span></div><div><b id="h_n_high">&ndash;</b><span>ranked High (7&ndash;10)</span></div><p class="h-asof" id="h_asof"></p></div>
 <a class="bnt-btn" href="/map">Open the live map</a>
</div><p class="h-credit">Screen capture: BLACKOUT.NETWORK Heat Map</p></section>

<section class="h-sec"{" data-snap" if snap else ""} id="s3" data-clip="noise"><div class="h-copy">
 <p class="bnt-eyebrow">Global threat monitoring</p>
 <h2 class="h-h">Every alert,<br>ranked 0 to 10</h2>
 <p class="h-lede">Each item is scored on impact and on how many independent sources back it up. The serious ones rise to the top. Nothing is hidden: the full feed is always one tap away.</p>
 <div class="h-scale" aria-label="Rank scale 0 to 10"><div class="h-bar" id="h_bar"></div><div class="h-nums"><span>0</span><span>1</span><span>2</span><span>3</span><span>4</span><span>5</span><span>6</span><span>7</span><span>8</span><span>9</span><span>10</span></div>
 <div class="bnt-key"><span class="c">Calm <b>0&ndash;3</b></span><span class="e">Elevated <b>4&ndash;6</b></span><span class="h">High <b>7&ndash;10</b></span></div></div>
 <a class="bnt-btn" href="/scoring">How we score</a>
</div><p class="h-credit">Footage: NASA (ISS, Hurricane Dorian, 2019)</p></section>

<section class="h-sec"{" data-snap" if snap else ""} id="s4" data-clip="cover"><div class="h-copy">
 <p class="bnt-eyebrow">What we watch</p>
 <h2 class="h-h">One screen for<br>every kind of threat</h2>
 <div class="h-chips">{chips}</div>
 <button class="bnt-btn" type="button" data-h-menu>Explore every section</button>
</div><p class="h-credit">Footage: NASA Goddard / SDO (solar flare, 2016)</p></section>

<section class="h-sec"{" data-snap" if snap else ""} id="s5" data-clip="planet"><div class="h-copy">
 <p class="bnt-eyebrow">For everyone, everywhere</p>
 <h2 class="h-h"><span class="h-rot" id="h_rot">Free for everyone<br>on the planet</span></h2>
 <p class="h-lede">Read the whole site in your language. No account and no paywall. Built for professionals, businesses, families, and anyone coordinating or getting prepared.</p>
 <div class="h-langs" id="h_langs" aria-hidden="true"></div>
 <a class="bnt-btn" href="#h_foot" id="h_lang_btn">Choose your language</a>
</div><p class="h-credit">Footage: NASA (ISS, Earth limb, 2024)</p></section>

<section class="h-sec"{" data-snap" if snap else ""} id="s6" data-clip="email"><div class="h-copy">
 <p class="bnt-eyebrow">Stay connected</p>
 <h2 class="h-h">Get the brief.<br>Get the alerts.</h2>
 <p class="h-lede">A sourced brief at 7 AM and 7 PM ET, plus emergency email alerts when something serious breaks. Email is your backup: it still reaches you on any device if you lose your phone.</p>
 <div id="nl_app" class="h-optin" data-mode="card">{_newsletter_form()}</div>
 <button class="h-moreopt" id="h_moreopt" type="button" aria-expanded="false" aria-controls="nl_app">More options: how often, your area, topics</button>
 <div class="h-extras"><span>Extra layers:</span>
  <button type="button" id="h_install">{_ic('<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>')}Add to home screen</button>
  <button type="button" data-bn-alerts>{_ic('<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4"/>')}Turn on alerts</button>
 </div>
</div><p class="h-credit">Footage: NASA (ISS, Earth from orbit, 2019)</p></section>

<section class="h-sec"{" data-snap" if snap else ""} id="s7" data-clip="dash"><div class="h-copy c">
 <p class="bnt-eyebrow">The live dashboard</p>
 <h2 class="h-h">Global threat monitoring</h2>
 <p class="h-lede">Everything in one place, updated around the clock.</p>
 <a class="bnt-btn y" href="/live">Enter the dashboard</a>
 {SKIPBOX}
</div><p class="h-credit">Screen capture: BLACKOUT.NETWORK live dashboard</p>
<footer class="h-foot" id="h_foot"><span class="bntr-foot" hidden></span>
 <a href="/privacy">Privacy</a><a href="/tos">Terms</a><a href="/sources">Sources</a><a href="/scoring">How we score</a><a href="/bnt/credits.txt">Footage credits</a>
 <header class="h-lang" aria-label="Language"><span class="ctl"></span></header>
 <p class="h-legal">BLACKOUT.NETWORK &middot; Independent signals, not an official alert service.</p>
</footer></section>
</main>
<div class="h-scrim" id="h_scrim"></div>
<aside class="h-menu{m4cls}" id="h_menu" aria-hidden="true" aria-label="Site menu">
 <button class="h-x" type="button" aria-label="Close menu">&times;</button>
 <a class="h-wm" href="/live" style="display:block;margin:0 0 18px;font-size:18px">{wm}</a>
 {mlead}
 {_menu()}
 <div class="h-mfoot"><a class="bnt-btn y" href="#s6" data-h-close>Get the free brief</a><a class="bnt-btn" href="/live">Open dashboard</a></div>
</aside>
<script src="{url("theme.js")}"></script><script src="{url("home.js")}" defer></script>{snapjs}
<script src="/api/newsletter/app.js" defer></script><script src="/api/translate/app.js" defer></script>
</body></html>'''

def home_page():
    h = _home_page_raw()
    if credits_page_on():
        h = re.sub(r'<p class="h-credit">[^<]*</p>', "", h)
        h = h.replace('<a href="/bnt/credits.txt">Footage credits</a>', '<a href="/credits#intro">Image credits</a>')
    # Matt 5:28 PM: follow band sits on the page black, above a normal footer (not over the last hero).
    m = re.search(r'<footer class="h-foot"[^>]*>.*?</footer>', h, re.S)
    if m:
        foot = m.group(0)
        h = h[:m.start()] + h[m.end():]
        try:
            import growth
            band = growth.follow_html()
        except Exception:
            band = ""
        h = h.replace("</main>", "</main>\n" + band + foot, 1)
    return h

# ---------- "/live" overview (top of the dashboard home view) ----------
def snap_on():
    """Shared full-section snapping (theme_static/snap.js). BN_SNAP=0 = off (free scrolling everywhere)."""
    return os.environ.get("BN_SNAP", "1") != "0"

def home_snap_on():
    """Section snap on the intro homepage "/". Off by default (Matt 4:07 PM Nov 17: smooth free scroll like the Wire). BN_HOME_SNAP=1 = snap back on.
    /live and the other tab heroes keep BN_SNAP."""
    return os.environ.get("BN_HOME_SNAP", "0") == "1"

def credits_page_on():
    """Matt 12:07 PM: no credits on top of images/video; every page links "Image credits" -> /credits. BN_CREDITS_PAGE=0 = old overlays."""
    return os.environ.get("BN_CREDITS_PAGE", "1") != "0"

def live_hero_on():
    """Live full-bleed hero (SpaceX-style imagery rollout, step 1). BN_LIVE_HERO=0 = off (previous look)."""
    return os.environ.get("BN_LIVE_HERO", "1") != "0"

def live_acq_on():
    """Compact /live vacuum-strip loader. Default on; BN_LIVE_ACQ=0 restores a bare first paint."""
    return os.environ.get("BN_LIVE_ACQ", "1") != "0"

def tab_hero_on():
    """Latest tab heroes (/live#streams, #noise, #heatmap, #trends, #broadcasts, #radio): full-screen looping NASA video on
    desktop/tablet, still image on phones / reduced motion / Save-Data, snapped (BN_SNAP), data below scrolls freely. BN_TAB_HERO=0 = off."""
    return os.environ.get("BN_TAB_HERO", "1") != "0"

# hash -> media key (files <key>vid-d.mp4/.webm/.jpg and <key>hero-m.jpg in theme_static/media). One unique clip per tab, never reused.
TAB_HEROES = {"streams": "tv", "noise": "nz", "heatmap": "hm", "trends": "tr", "broadcasts": "bc", "radio": "rd"}
# hero titles follow the menu labels (Matt 2:16 PM): only these differ from the tab page titles
TAB_HERO_TITLES = {"streams": "Live TV & Radio", "broadcasts": "Broadcast transcripts", "radio": "Live Radio"}

def tab_hero_html():
    if not tab_hero_on(): return ""
    import json as _j
    snap = f'<script src="{url("snap.js")}" defer></script>' if snap_on() else ""
    return (f'<link rel="stylesheet" href="{url("tabhero.css")}">'
            '<section id="bn_th" class="bn-th" data-bn-snap data-snap-hero data-snap-offset="header.bn-top" hidden aria-label="Page header">'
            '<div class="bn-th-s" data-snap><div class="bn-th-bg" aria-hidden="true"><picture><source media="(max-width:700px)" srcset="">'
            '<img alt="" decoding="async"></picture><video class="bn-th-v" muted loop playsinline preload="none" disablepictureinpicture tabindex="-1"></video></div>'
            '<div class="bn-th-c"><p class="bn-th-k">Latest</p></div>'
            '<a class="bn-th-cue" href="#bn_th_end" aria-label="Scroll to the data"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></a>'
            '</div></section><div id="bn_th_end"></div>'
            f'<script>window.BN_TAB_HEROES={_j.dumps(TAB_HEROES)};window.BN_TAB_HERO_TITLES={_j.dumps(TAB_HERO_TITLES)};</script><script src="{url("tabhero.js")}" defer></script>' + snap)


# First-paint /live vacuum strip (Matt 8:19–8:20 PM ET, Nov 17): compact 52px widget under the
# header. Canvas particles drift in from the edges and are pulled into an intake that rides a
# hairline bar; the only readout is a tabular 0–100%. BN_LIVE_ACQ=0 turns the strip off.
_LIVE_ACQ = (
    '<div class="l-acq" id="bntl_acq" role="status" aria-live="polite" aria-label="Loading 0 percent">'
    '<canvas class="l-acq-cv" id="bntl_acq_cv" width="640" height="52" aria-hidden="true"></canvas>'
    '<div class="l-acq-readout"><span class="l-acq-pct" id="bntl_acq_pct">00</span><span class="l-acq-unit">%</span></div>'
    '</div>'
)
_LIVE_SK_SIG = (
    '<div class="bnt-card l-sig l-sk-card" aria-hidden="true">'
    '<span class="l-sk l-sk-sm"></span><span class="l-sk l-sk-lg"></span><span class="l-sk l-sk-md"></span>'
    '</div>'
)
_LIVE_SK_MAP = '<div class="l-sk-map" aria-hidden="true"><i></i></div>'
_LIVE_SK_DIST = "".join(f'<div aria-hidden="true"><i class="l-sk-bar"></i><span>{k}</span></div>' for k in range(11))
_LIVE_SK_CAT = (
    '<div class="l-catrow l-sk-row" aria-hidden="true"><span class="l-sk l-sk-sm"></span>'
    '<div class="b"><i class="l-sk-scan"></i></div><b class="l-sk l-sk-xs"></b></div>'
)

def live_overview_html():
    hero = live_hero_on()
    acq = live_acq_on()
    bg = ('<div class="l-bg" aria-hidden="true"><picture><source media="(max-width:700px)" srcset="/bnt/media/lvhero-m.jpg?v=1">'
          '<img src="/bnt/media/lvvid-d.jpg?v=1" alt="" decoding="async" fetchpriority="high"></picture>'
          '<video class="l-vid" muted loop playsinline preload="none" disablepictureinpicture tabindex="-1"'
          ' data-webm="/bnt/media/lvvid-d.webm?v=1" data-mp4="/bnt/media/lvvid-d.mp4?v=1"></video></div>'
          '<script>(function(){var v=document.currentScript.previousElementSibling.querySelector("video"),n=navigator.connection||{},'
          'mm=function(q){return window.matchMedia&&matchMedia(q).matches};'
          'if(!v||innerWidth<=700||mm("(prefers-reduced-motion: reduce)")||n.saveData)return;var sec=v.closest("section");'
          'function go(){if(sec&&sec.offsetWidth===0)return false;'   # /live#tab: overview hidden, no download until shown
          '[["webm","video/webm"],["mp4","video/mp4"]].forEach(function(a){var s=document.createElement("source");s.src=v.getAttribute("data-"+a[0]);s.type=a[1];v.appendChild(s)});'
          'v.muted=true;v.autoplay=true;v.preload="auto";v.addEventListener("playing",function(){v.classList.add("on")},{once:true});'
          'v.load();var p=v.play();if(p&&p.catch)p.catch(function(){});return true}'
          'setTimeout(function(){if(!go()){var iv=setInterval(function(){if(go())clearInterval(iv)},1000)}},400)})()</script>') if hero else ""
    return f'''<link rel="stylesheet" href="{url("live.css")}"><section class="bnt-live{' l-loading' if acq else ''}{' l-hasbg' if hero else ''}" id="bntl" aria-label="Live overview"{' aria-busy="true"' if acq else ''}>{bg}<div class="l-glow" aria-hidden="true" data-bn-par="0.12"><i></i><i></i><i></i></div><div class="l-wrap">
{_LIVE_ACQ if acq else ""}
<div class="l-intro"><div><p class="bnt-eyebrow">Live &middot; worldwide</p><h2 class="l-h1">Right now</h2>
<p class="l-sub" id="bntl_asof"><i></i>Loading the latest scan&hellip; &middot; <a href="/?intro=1">Watch the intro</a></p></div>
<div class="bnt-key"><span class="c">Calm <b>0&ndash;3</b></span><span class="e">Elevated <b>4&ndash;6</b></span><span class="h">High <b>7&ndash;10</b></span></div></div>
<div class="l-hero"><div class="bnt-card l-gcard"><div class="l-kr"><p class="k">Top stories · Average rank</p><span id="bntl_ug"></span></div><div class="l-gauge" id="bntl_g"><div class="l-sk-gauge" aria-hidden="true"></div></div><div class="l-gtext"><p class="plain" id="bntl_gt">&nbsp;</p></div></div>
<div class="l-tiles">
<a class="bnt-card l-tile h" href="/wire"><p class="k">High &middot; 7&ndash;10</p><b id="bntl_th">&ndash;</b><div class="l-meter" id="bntl_mh"></div></a>
<a class="bnt-card l-tile e" href="/wire"><p class="k">Elevated &middot; 4&ndash;6</p><b id="bntl_te">&ndash;</b><div class="l-meter" id="bntl_me"></div></a>
<a class="bnt-card l-tile c" href="/wire"><p class="k">Calm &middot; 0&ndash;3</p><b id="bntl_tc">&ndash;</b><div class="l-meter" id="bntl_mc"></div></a>
<a class="bnt-card l-tile s" href="/sources"><div class="l-ring" id="bntl_ring"><span class="l-sk-ring" aria-hidden="true"></span></div><div><p class="k">Sources online</p><p class="plain" id="bntl_src">&nbsp;</p></div></a>
<div class="l-tstamp"><span id="bntl_ut"></span></div>
</div></div>
<div class="l-head"><h3>Top signals</h3><span id="bntl_us"></span><a class="l-more" href="/wire">Full Wire &rarr;</a></div>
<div class="l-sigs" id="bntl_sigs">{(_LIVE_SK_SIG * 3)}</div>
<div class="l-split"><div class="bnt-card"><div class="l-head"><h3>Map</h3><span class="l-hint" id="bntl_maph"></span><span id="bntl_um"></span><a class="l-more" href="/map">Full-screen map &rarr;</a></div><div class="l-map" id="bntl_map">{_LIVE_SK_MAP}</div></div>
<div class="bnt-card"><div class="l-head"><h3>Rank spread</h3><span id="bntl_ud"></span></div><div class="l-dist" id="bntl_dist">{_LIVE_SK_DIST}</div></div></div>
<div class="l-split even"><div class="bnt-card l-vol"><div class="l-head"><h3>Per day</h3><span class="l-hint">7 days</span><span id="bntl_uv"></span></div><div id="bntl_vol"><div class="l-sk-vol" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div></div>
<div class="bnt-card"><div class="l-head"><h3>Today</h3><span class="l-hint" id="bntl_cath"></span><span id="bntl_uc"></span></div><div class="l-cats" id="bntl_cats">{(_LIVE_SK_CAT * 4)}</div></div></div>
<div class="bnt-card l-cta"><div><h3>Get the brief</h3><p class="plain">7 AM and 7 PM ET.</p></div><a class="bnt-btn y" href="/newsletter">Get the free brief</a></div>
</div></section><script src="{url("live.js")}" defer></script>'''
