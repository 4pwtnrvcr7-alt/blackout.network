"""Per-item Post on X: share landing pages, 1200x630 cards and hashtags.

X intent URLs cannot attach images, so every shareable item gets a deep-link URL
(/share/<kind>/<id>) whose HTML carries per-item og:image + twitter:card
summary_large_image meta, then sends people to the right view of the site.
Hashtags reuse x_share (the Wire/story generator) for place/topic tags and add
kind tags. Nothing here posts, schedules or calls a social API.
"""
from __future__ import annotations
import base64, html, io, json, os, re
from pathlib import Path
from urllib.parse import quote, urlencode

SITE = "https://blackout.network"
BASE = Path(__file__).resolve().parent
NM = BASE / "netmap_static"
VER = "1"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

KINDS = {
    "planet": "Solar system", "moon": "Solar system", "sun": "Solar system", "craft": "Spacecraft",
    "roadster": "Spacecraft", "site": "Surface site", "sat": "Satellites", "launch": "Launch",
    "cloud": "Cloud region", "network": "Network status", "outage": "Outage", "weather": "Weather",
    "solar": "Space weather", "page": "BLACKOUT.NETWORK", "dc": "Data center", "cable": "Undersea cable",
    "power": "Power outage", "grid": "Power grid", "water": "Water treatment",
}
PLANETS = {"sun", "mercury", "venus", "earth", "moon", "mars", "jupiter", "saturn", "uranus", "neptune"}
# craft photos that are public domain / CC0 only (Aditya, JUICE are CC BY-SA: never on a card)
CRAFT_PHOTO = {"ace", "clipper", "dscovr", "juno", "jwst", "lucy", "newhorizons", "parker", "psyche", "roadster",
               "soho", "solo", "stereoa", "voyager1", "voyager2", "wind"}
SAT_PHOTO = {"starlink": "starlink", "gps": "gps", "goes": "goes", "iss": "iss", "iridium": "iridium"}
SAT_OK_LIC = ("starlink", "gps", "goes")  # CC0 / US-government photos (see learn/CREDITS.txt)

KIND_TAGS = {
    "planet": ["#Space", "#Astronomy"], "moon": ["#Moon", "#Space", "#Astronomy"], "sun": ["#Sun", "#Space", "#Astronomy"],
    "craft": ["#Spacecraft", "#Space"], "roadster": ["#Starman", "#SpaceX", "#Space"],
    "site": ["#Space", "#Exploration"], "sat": ["#Satellites", "#Orbit", "#Space"],
    "launch": ["#Launch", "#Spaceflight", "#Rocket"], "cloud": ["#Cloud", "#Outage", "#Tech"],
    "network": ["#Outage", "#Internet", "#Tech"], "outage": ["#Outage", "#Internet", "#Tech"],
    "weather": ["#Weather", "#Radar", "#Forecast"], "solar": ["#SpaceWeather", "#Sun", "#Aurora"],
    "page": ["#Infrastructure", "#Grid"], "water": ["#Water", "#DrinkingWater"], "dc": ["#DataCenter", "#Cloud", "#Tech"], "cable": ["#UnderseaCables", "#Internet", "#Tech"],
    "power": ["#PowerOutage", "#Grid", "#Energy"], "grid": ["#PowerGrid", "#Energy", "#Grid"],
}
PROVIDER_TAGS = [
    (r"\baws\b|amazon web", ["#AWS"]), (r"azure", ["#Azure", "#Microsoft"]), (r"m365|microsoft 365|office 365", ["#Microsoft365"]),
    (r"\bgcp\b|google cloud", ["#GoogleCloud"]), (r"workspace", ["#GoogleWorkspace"]), (r"cloudflare", ["#Cloudflare"]),
    (r"akamai", ["#Akamai"]), (r"starlink", ["#Starlink"]), (r"verizon", ["#Verizon"]), (r"at&t|\batt\b", ["#ATT"]),
    (r"t-mobile", ["#TMobile"]), (r"comcast|xfinity", ["#Xfinity"]),
]
VEHICLE_TAGS = [
    (r"falcon|starship|dragon", ["#SpaceX"]), (r"starship", ["#Starship"]), (r"falcon 9", ["#Falcon9"]), (r"falcon heavy", ["#FalconHeavy"]),
    (r"soyuz|angara|proton", ["#Roscosmos"]), (r"long march|chang zheng", ["#China", "#LongMarch"]),
    (r"electron|neutron", ["#RocketLab"]), (r"atlas|vulcan", ["#ULA"]), (r"ariane|vega", ["#Arianespace"]),
    (r"\bsls\b", ["#Artemis", "#NASA"]), (r"new glenn|new shepard", ["#BlueOrigin"]), (r"\bh3\b|h-?iia|epsilon", ["#JAXA"]),
    (r"pslv|gslv|lvm3", ["#ISRO"]), (r"nuri", ["#KARI"]), (r"antares|minotaur", ["#NorthropGrumman"]),
]

# ----------------------------------------------------------------------------- text helpers
def clean(s, n=120):
    s = re.sub(r"[\x00-\x1f\x7f<>]", " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n].rstrip()


def _tags_from(patterns, hay):
    out = []
    for rx, tg in patterns:
        if re.search(rx, hay, re.I):
            for t in tg:
                if t not in out:
                    out.append(t)
    return out


def _name_tag(name):
    import x_share
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name or "") if w]
    if not words or len(words) > 3:
        return None
    t = x_share.to_tag(" ".join(words))
    return t if t and len(t) <= 20 else None


def tags_for(kind, name="", loc="", detail="", text=""):
    """3 to 5 hashtags: item-specific, place/topic (x_share generator), then kind tags."""
    import x_share
    kind = kind if kind in KINDS else "page"
    hay = f"{name} {detail}"
    specific = []
    if kind == "site":
        base = re.sub(r"\s*\(.*$", "", name or "")
        for body in ("moon", "mars"):
            if any((r.get("name") or "") == base for r in sites().get(body) or []):
                specific.append("#Moon" if body == "moon" else "#Mars")
        t = _name_tag(base)
        if t:
            specific.insert(0, t)
    elif kind in ("planet", "moon", "sun", "craft", "sat"):
        t = _name_tag(name)
        if t:
            specific.append(t)
    if kind == "launch":
        specific += _tags_from(VEHICLE_TAGS, hay)[:2]
    if kind in ("cloud", "network", "outage", "dc"):
        specific += _tags_from(PROVIDER_TAGS, hay)[:2]
    place = []
    try:
        item = {"title": clean(f"{name} {loc}", 200), "headline": clean(name, 200), "location": clean(loc, 120),
                "category": "", "brief": "", "rank": 0}
        gen = set(getattr(x_share, "GENERIC_TAGS", []) or [])   # drop the Wire's generic #News padding; kind tags fill instead
        place = [t for t in x_share.hashtags(item) if t and t not in gen]
    except Exception:
        place = []
    if kind in ("planet", "moon", "sun", "craft", "roadster", "sat"):
        place = []  # location tags make no sense for bodies in space
    out = []
    for t in specific[:2] + place[:2] + KIND_TAGS.get(kind, []) + specific[2:] + place[2:]:
        if t and t.lower() not in [x.lower() for x in out]:
            out.append(t)
        if len(out) >= 5:
            break
    for pad in ("#Space" if kind in ("planet", "moon", "sun", "craft", "roadster", "site", "sat", "launch") else "#Infrastructure", "#Grid"):
        if len(out) >= 3:
            break
        if pad.lower() not in [x.lower() for x in out]:
            out.append(pad)
    return out[:5]


# ----------------------------------------------------------------------------- catalogs
_SITES = None
def sites():
    global _SITES
    if _SITES is None:
        try:
            _SITES = json.loads((NM / "planets" / "sites.json").read_text())
        except Exception:
            _SITES = {}
    return _SITES


def find_site(sid):
    d = sites()
    for body in ("moon", "mars"):
        for r in d.get(body) or []:
            if r.get("id") == sid:
                return body, r
    for r in d.get("features") or []:
        if r.get("id") == sid:
            return r.get("body") or "", r
    return None, None


CRAFT_NAMES = {"voyager1": "Voyager 1", "voyager2": "Voyager 2", "jwst": "James Webb Space Telescope", "newhorizons": "New Horizons",
               "stereoa": "STEREO-A", "soho": "SOHO", "solo": "Solar Orbiter", "parker": "Parker Solar Probe", "clipper": "Europa Clipper",
               "juno": "Juno", "lucy": "Lucy", "psyche": "Psyche", "dscovr": "DSCOVR", "ace": "ACE", "wind": "Wind", "juice": "JUICE", "aditya": "Aditya-L1"}

PLANET_FACTS = {
    "sun": ("Sun", "Our star holds 99.86% of the solar system's mass and its light takes about 8 minutes to reach Earth."),
    "mercury": ("Mercury", "Mercury circles the Sun in just 88 Earth days, the fastest orbit of any planet."),
    "venus": ("Venus", "Venus spins backwards and its day is longer than its year, with surface temperatures near 465 C (870 F)."),
    "earth": ("Earth", "Earth is the only world known to host life and it races around the Sun at about 67,000 mph (107,000 km/h)."),
    "moon": ("Moon", "The Moon drifts about 1.5 inches (3.8 cm) farther from Earth every year."),
    "mars": ("Mars", "Mars is home to Olympus Mons, a volcano about 2.5 times the height of Mount Everest."),
    "jupiter": ("Jupiter", "Jupiter's Great Red Spot is a storm wider than Earth that has raged for centuries."),
    "saturn": ("Saturn", "Saturn is the least dense planet: it would float in a big enough bathtub."),
    "uranus": ("Uranus", "Uranus rolls around the Sun tipped on its side, so each pole gets 42 years of sunlight, then 42 of darkness."),
    "neptune": ("Neptune", "Neptune's winds top 1,200 mph (2,000 km/h), the fastest in the solar system."),
}


def _launch_by_id(lid):
    try:
        import netlaunch
        d = netlaunch.launches_cached() or {}
        if isinstance(d, (bytes, bytearray, str)):   # launches_cached() returns the JSON bytes
            d = json.loads(d)
        for L in d.get("launches") or []:
            if L.get("id") == lid:
                return L
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------------- spec
def spec(kind, ident, q=None):
    """Resolve what the share page and card say. q holds client-supplied n/d/l/p (sanitised, capped)."""
    q = q or {}
    g = lambda k, n=120: clean((q.get(k) or [""])[0] if isinstance(q.get(k), list) else q.get(k), n)
    kind = kind if kind in KINDS else "page"
    ident = re.sub(r"[^A-Za-z0-9_.:-]", "", str(ident or ""))[:60] or "home"
    name, detail, loc = g("n", 90), g("d", 140), g("l", 80)
    dest = "/grid"
    img = None  # (type, key)
    label = KINDS[kind]
    if kind in ("planet", "moon", "sun") or ident in PLANETS and kind == "planet":
        pid = ident.lower()
        if pid in PLANET_FACTS:
            name, detail = PLANET_FACTS[pid][0], PLANET_FACTS[pid][1][:140]
        dest = f"/grid?sky={quote(pid)}#sky"
        img = ("planet", pid)
    elif kind == "roadster" or (kind == "craft" and ident == "roadster"):
        kind, name, ident = "roadster", "Tesla Roadster (Starman)", "roadster"
        detail = detail or "Elon Musk's Tesla Roadster, launched on Falcon Heavy in 2018, is still circling the Sun."
        dest, img = "/grid?sky=roadster#sky", ("craft", "roadster")
    elif kind == "craft":
        if not name and ident in CRAFT_NAMES:
            name = CRAFT_NAMES[ident]
        dest, img = f"/grid?sky={quote(ident)}#sky", ("craft", ident)
    elif kind == "site":
        body, rec = find_site(ident)
        if rec:
            name = f"{rec['name']}" + (f" ({rec['place']})" if rec.get("place") else "")
            name = name[:90]
            detail = clean(rec.get("text") or "", 140)
            dest = f"/grid?sky={quote(body or 'moon')}&site={quote(ident)}#sky"
            img = ("planet", body or "moon")
            label = "Moon landing" if body == "moon" else "Mars landing" if body == "mars" else "Surface feature"
        else:
            dest = "/grid#sky"
    elif kind == "sat":
        dest, img = f"/grid?sat={quote(ident)}#sky", ("sat", ident)
    elif kind == "launch":
        L = _launch_by_id(ident)
        if L:
            mis = L.get("mission") or ""
            veh = L.get("vehicle") or ""
            name = f"{veh}: {mis}"[:90] if mis else veh
            detail = clean(f"{L.get('location') or L.get('pad') or ''}", 140)
            img = ("rocket", f"{veh}|{mis}|{L.get('name') or ''}")
        dest = f"/grid?launch={quote(ident)}"
    elif kind in ("cloud", "network", "outage", "dc", "cable", "power", "grid"):
        pp = g("p", 80)
        if re.fullmatch(r"/grid(/[A-Za-z0-9_-]{1,30}){1,3}", pp or ""):
            dest = pp
        elif re.fullmatch(r"[a-z0-9-]{2,30}", pp.lower() or ""):
            dest = f"/grid/{pp.lower()}"
        else:
            dest = "/grid"
    elif kind == "weather":
        dest = "/weather"
    elif kind == "solar":
        dest = "/live#solar"
    else:
        p = g("p", 80)
        dest = p if re.fullmatch(r"/[A-Za-z0-9/_#?=&.-]{0,78}", p or "") and "//" not in p else "/"
        pk = ident
        img = ("page", pk)
    if kind in ("weather", "solar", "page") and not img:
        img = ("page", ident)
    return dict(kind=kind, id=ident, name=name or "BLACKOUT.NETWORK", detail=detail, loc=loc, dest=dest, img=img, label=label)


def share_url(kind, ident, name="", detail="", loc="", path=""):
    qs = {}
    if name: qs["n"] = clean(name, 90)
    if detail: qs["d"] = clean(detail, 140)
    if loc: qs["l"] = clean(loc, 80)
    if path: qs["p"] = path
    ident = re.sub(r"[^A-Za-z0-9_.:-]", "", str(ident or ""))[:60] or "home"
    return f"{SITE}/share/{quote(kind)}/{quote(ident)}" + ("?" + urlencode(qs) if qs else "")


def _wlen(text, url):
    return len(text) + (1 + 23 if url else 0)


def intent(kind, ident, text, name="", detail="", loc="", path=""):
    """Server-side x.com intent URL: crafted text + 3-5 tags + the per-item share URL."""
    url = share_url(kind, ident, name, detail, loc, path)
    tags = tags_for(kind, name, loc, detail, text)
    t = clean(text, 400)
    while True:
        full = (t + " " + " ".join(tags)).strip()
        if _wlen(full, url) <= 280:
            break
        if len(tags) > 3:
            tags = tags[:-1]
            continue
        cut = max(20, 280 - 24 - len(" ".join(tags)) - 2)
        t = t[:cut].rsplit(" ", 1)[0].rstrip(",;:-– ") + "…"
        full = (t + " " + " ".join(tags)).strip()
        break
    return f"https://x.com/intent/post?text={quote(full, safe='')}&url={quote(url, safe='')}"


def button_html(kind, ident, text, name="", detail="", loc="", path="", cls="w2-btn w2-btn-s"):
    href = intent(kind, ident, text, name, detail, loc, path)
    return (f'<a class="{E(cls)}" href="{E(href)}" target="_blank" rel="noopener">Post on X</a>')


# ----------------------------------------------------------------------------- card image
def _b64img(path):
    from PIL import Image
    p = Path(str(path) + ".b64")
    if p.is_file():
        return Image.open(io.BytesIO(base64.b64decode(p.read_bytes())))
    if Path(path).is_file():
        return Image.open(path)
    return None


def _bg(img):
    if not img:
        return None
    t, k = img
    try:
        if t == "planet" and k in PLANETS and k != "sun":
            return _b64img(NM / "planets" / f"{k}.jpg")
        if t == "craft" and k in CRAFT_PHOTO:
            return _b64img(NM / "learn" / f"s3_{k}.jpg")
        if t == "sat" and k in SAT_OK_LIC:
            return _b64img(NM / "learn" / f"{k}.jpg")
        if t == "rocket":
            import netlaunch
            names = k.split("|")
            ph = netlaunch.rocket_photo(*names)
            if ph and re.match(r"^(Public domain|CC0)", ph.get("license") or ""):
                return _b64img(NM / "rockets" / os.path.basename(ph["url"]))
        if t == "page":
            import og
            sp = og.page_spec(k)
            if sp and sp.get("bg"):
                return og._open_bg(*sp["bg"])
    except Exception:
        return None
    return None


def card_png(kind, ident, q=None):
    if kind not in KINDS:
        raise ValueError("unknown share kind")   # callers (share_card.og_share) turn this into a 404
    import og
    from PIL import ImageDraw
    s = spec(kind, ident, q)
    bg = _bg(s["img"])
    im = og.render(s["name"], bg_im=bg, tagline=False)
    d = ImageDraw.Draw(im)
    og._draw_tracked(d, (72, 96), s["label"].upper(), og.inter(14, bold=True), og.MUTED, tracking=3.6)
    if s["detail"] and kind not in ("planet", "moon", "sun", "site"):
        sub = clean(s["detail"], 70)
        og._draw_tracked(d, (72, 570), sub, og.inter(20), og.WORD, tracking=0.6)
    return og.png_bytes(im)


# ----------------------------------------------------------------------------- pages
def page_html(kind, ident, q=None):
    s = spec(kind, ident, q)
    import og
    qs = {k: v for k, v in (("n", s["name"] if s["name"] != "BLACKOUT.NETWORK" else ""), ("d", s["detail"]), ("l", s["loc"])) if v}
    pth = (q or {}).get("p")
    pth = pth[0] if isinstance(pth, list) and pth else (pth or "")
    if pth:
        qs["p"] = clean(pth, 80)
    url = f"{SITE}/share/{quote(s['kind'])}/{quote(s['id'])}" + ("?" + urlencode(qs) if qs else "")
    imgq = ("?" + urlencode({**qs, "v": VER})) if qs else f"?v={VER}"
    img = f"{SITE}/og/share/{quote(s['kind'])}/{quote(s['id'])}.png{imgq}"
    title = f"{s['name']} | BLACKOUT.NETWORK"
    desc = s["detail"] or "Global threat monitoring: independent, sourced early-warning signals. Not official alerts."
    meta = og.tags(title=title, desc=desc, url=url, image=img, og_type="article")
    dest = s["dest"]
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{E(title)}</title><meta name=\"description\" content=\"{E(desc)}\">"
        f"<link rel=\"canonical\" href=\"{E(url)}\"><meta name=\"robots\" content=\"noindex,follow\">{meta}"
        f"<meta http-equiv=\"refresh\" content=\"0;url={E(dest)}\">"
        f"<script>try{{history.scrollRestoration='manual'}}catch(e){{}}location.replace({json.dumps(dest)})</script>"
        "</head><body style=\"background:#05060a;color:#ECEEF5;font:15px/1.5 Inter,system-ui,sans-serif;padding:48px 24px\">"
        f"<p><a href=\"{E(dest)}\" style=\"color:#fff\">{E(s['name'])}</a></p>"
        f"<p style=\"color:#9aa0aa\">{E(desc)}</p>"
        "</body></html>"
    ).encode("utf-8")


JS = BASE / "netmap_static" / "bnshare.js"


def handle_get(path, qs=None):
    p = (path or "").split("?")[0].rstrip("/")
    try:
        if p == "/api/share/bnshare.js":
            return 200, JS.read_bytes(), "application/javascript"
        if p == "/api/share/tags":
            g = lambda k, n=120: clean((qs or {}).get(k, [""])[0], n)
            kind = g("k", 20)
            tg = tags_for(kind, g("n", 90), g("l", 80), g("d", 140), g("t", 300))
            return 200, {"tags": tg}
        m = re.fullmatch(r"/share/([a-z]{2,12})/([A-Za-z0-9_.:-]{1,60})", p)
        if m:
            return 200, page_html(m.group(1), m.group(2), qs), "text/html"
        m = re.fullmatch(r"/og/share/([a-z]{2,12})/([A-Za-z0-9_.:-]{1,60})", p[:-4] if p.endswith(".png") else p)
        if m:
            return 200, card_png(m.group(1), m.group(2), qs), "image/png"
    except Exception:
        import traceback; traceback.print_exc()
        if p.startswith("/og/"):
            try:
                import og
                return 200, og.png_for("home"), "image/png"
            except Exception:
                pass
    return 404, {"error": "not found"}
