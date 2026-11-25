"""Post on X everywhere: per-item share text, hashtags, deep links, share landing pages and unique 1200x675 cards.

Nothing here posts, schedules or calls a social API. X intent URLs cannot attach images, so every "Post on X" button
shares a landing URL whose og:image is a card generated for that one item. This module renders those cards (Pillow only,
disk-cached through og._cached): /og/share/<kind>/<id>.png for the buttons built by share_cards.py / bnshare.js, and
story_png() for Wire stories (og.png_for_story). Item data always comes from server data (Horizons, launches, network
status, sites.json), never from the URL; only unresolvable items fall back to a typographic card from the sanitised n/d/l
query fields, then to share_cards.card_png.

Kinds: planet, craft, sat, launch, site (planet surface pin / feature), net (network status), cloud (cloud region),
page (weather, solar explorer, ...), story (Wire story; the story page itself is the share URL).
Hashtags come from x_share (PR #192 generator, reused not forked); non-story kinds add curated topic tags in front.
"""
from __future__ import annotations

import base64, hashlib, html, io, json, math, os, re, time, threading
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

import og
import x_share

SITE = "https://blackout.network"
W, H = 1200, 675
VERSION = "6"
BASE = Path(__file__).resolve().parent
NM = BASE / "netmap_static"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

BG = (5, 6, 10)
WHITE = (255, 255, 255)
MUTED = (160, 166, 176)
DIM = (110, 116, 128)
GREEN, AMBER, RED = (47, 178, 106), (224, 160, 48), (200, 16, 46)
SPACE_C, LAUNCH_C, WX_C, NET_C = (143, 178, 255), (96, 200, 230), (96, 165, 240), (190, 196, 208)

HOOKS = {}  # tests inject data: HOOKS["solar"] = fn -> dict etc.

# ------------------------------------------------------------------ static knowledge
PLANETS = {
    "mercury": ("Mercury", "Mercury circles the Sun every 88 days, the fastest orbit of any planet.", ["Mercury", "SolarSystem"]),
    "venus": ("Venus", "Venus is the hottest planet: about 870°F at the surface, under crushing CO2 clouds.", ["Venus", "SolarSystem"]),
    "earth": ("Earth", "Earth is the only world known to have life, and every spacecraft here is measured from it.", ["Earth", "Space"]),
    "mars": ("Mars", "NASA's Curiosity and Perseverance rovers are still exploring Mars today.", ["Mars", "NASA"]),
    "jupiter": ("Jupiter", "Jupiter's Great Red Spot is a storm wider than Earth, watched for more than 150 years.", ["Jupiter", "SolarSystem"]),
    "saturn": ("Saturn", "Saturn's rings span hundreds of thousands of miles but are mostly only tens of feet thick.", ["Saturn", "SolarSystem"]),
    "uranus": ("Uranus", "Uranus is tipped 98° on its side, so each pole gets about 42 years of sunlight, then 42 of dark.", ["Uranus", "SolarSystem"]),
    "neptune": ("Neptune", "Neptune's winds top 1,200 mph, the fastest measured on any planet.", ["Neptune", "SolarSystem"]),
    "moon": ("The Moon", "The Moon drifts about 1.5 inches farther from Earth every year.", ["Moon", "Space"]),
}
PLANET_CREDIT = {
    "mercury": "NASA/MESSENGER global mosaic", "venus": "NASA/JPL Magellan radar map", "earth": "NASA Blue Marble",
    "mars": "NASA/JPL/USGS Viking MDIM 2.1", "jupiter": "NASA/JPL/SSI Cassini PIA07782", "saturn": "NASA/JPL/SSI Cassini",
    "uranus": "NASA/JPL Voyager 2 (rendered)", "neptune": "NASA/JPL Voyager 2 (rendered)", "moon": "NASA/GSFC/ASU LRO LROC",
}
AU_MI = 92_955_807.0
PAGES = {
    "weather": dict(title="Weather map", path="/weather", kicker="WEATHER", color=WX_C, tags=["Weather", "Radar", "SevereWeather"],
                    text="Live radar, storm tracks and every active NWS alert on one dark map.", stat=("LIVE", "radar + alerts"), hero=("media", "hmvid-d.jpg"), map=(-96.0, 38.5, 30)),
    "solar": dict(title="Solar & seismic explorer", path="/solar", kicker="SPACE WEATHER", color=SPACE_C, tags=["SpaceWeather", "Sun", "Earthquake", "NASA"],
                  text="Live SDO sun video, flares, CMEs and Kp forecast, plus a test of the solar-earthquake link.", stat=("LIVE", "SDO + USGS"), hero=("media", "hero-d.jpg")),
    "sky": dict(title="The Grid: Sky view", path="/grid#sky", kicker="THE GRID · SKY", color=SPACE_C, tags=["Space", "Satellites", "Starlink", "NASA"],
                text="Every planet, rocket launch and spacecraft in 3D, live. Tap anything to fly there.", stat=("3D", "solar system"), hero=("media", "hero-d.jpg")),
    "grid": dict(title="The Grid", path="/grid", kicker="THE GRID", color=NET_C, tags=["Outage", "Internet", "Cloud", "Infrastructure"],
                 text="Live internet, cloud and power outages on one map, with a status board for 90+ networks.", stat=("LIVE", "network status"), hero=("media", "hmvid-d.jpg"), map=(-96.0, 38.5, 30)),
    "network": dict(title="Cloud & network status", path="/grid", kicker="THE GRID", color=NET_C, tags=["Outage", "Cloud", "AWS", "Azure"],
                    text="Is it down for everyone? Live status for AWS, Azure, Google Cloud, Cloudflare and more.", stat=("LIVE", "cloud status"), hero=("media", "hmvid-d.jpg")),
    "wire": dict(title="The Wire", path="/wire", kicker="THE WIRE", color=WHITE, tags=["BreakingNews", "Alerts", "Wire"],
                 text="Every ranked threat signal as it lands, each linked to its sources.", stat=("0–10", "ranked live"), hero=("wire", "iss070e062746.webp")),
    "map": dict(title="Heat map", path="/map", kicker="HEAT MAP", color=NET_C, tags=["Map", "Alerts", "Conflict", "Weather"],
                text="Seven days of ranked alerts on one full-screen heat map.", stat=("7 DAYS", "ranked alerts"), hero=("media", "hmvid-d.jpg")),
}
SAT_TAGS = {"starlink": ["Starlink", "SpaceX"], "gps": ["GPS", "Navigation"], "glonass": ["GLONASS", "Navigation"], "galileo": ["Galileo", "ESA"],
            "beidou": ["BeiDou", "Navigation"], "iridium": ["Iridium", "Satellites"], "oneweb": ["OneWeb", "Satellites"], "goes": ["GOES", "NOAA"], "iss": ["ISS", "SpaceStation"]}
PROVIDER_TAGS = {"aws": ["AWS", "Cloud"], "azure": ["Azure", "Microsoft"], "gcp": ["GoogleCloud", "Cloud"], "m365": ["Microsoft365", "Outage"],
                 "workspace": ["GoogleWorkspace", "Outage"], "cloudflare": ["Cloudflare", "Outage"], "akamai": ["Akamai", "CDN"], "linode": ["Akamai", "Cloud"]}


def _hook(name, fn):
    h = HOOKS.get(name)
    return h() if h else fn()


def _solar():
    def f():
        import netsky
        d = netsky.solar3d()
        return d if d.get("ok") else {}
    try:
        return _hook("solar", f) or {}
    except Exception:
        return {}


def _launches():
    def f():
        import netlaunch
        return netlaunch.launches_cached() or {}
    try:
        d = _hook("launches", f) or {}
        if isinstance(d, (bytes, bytearray, str)):   # netlaunch.launches_cached() returns the JSON bytes
            d = json.loads(d)
        return d.get("launches") or []
    except Exception:
        return []


def _netdata():
    def f():
        import netmap
        return netmap.data() or {}
    try:
        return _hook("net", f) or {}
    except Exception:
        return {}


def _json_file(rel):
    try:
        return json.loads((NM / rel).read_text())
    except Exception:
        return {}


def _static_bytes(rel):
    p = NM / rel
    try:
        if p.is_file():
            return p.read_bytes()
        b = Path(str(p) + ".b64")
        if b.is_file():
            return base64.b64decode(b.read_bytes())
    except Exception:
        pass
    return None


def _img(rel):
    b = _static_bytes(rel)
    try:
        return Image.open(io.BytesIO(b)).convert("RGB") if b else None
    except Exception:
        return None


# ------------------------------------------------------------------ small formatters
def _mi(au):
    mi = au * AU_MI
    if mi >= 1e9:
        return f"{mi / 1e9:.2f} billion mi"
    return f"{mi / 1e6:.0f} million mi" if mi >= 1e6 else f"{mi:,.0f} mi"


def _mph(kms):
    return f"{kms * 2236.936:,.0f} mph"


def _et(iso):
    """ISO Z -> (datetime in America/New_York, 'Nov 26, 4:12 PM ET')."""
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return None, ""
    h = d.hour % 12 or 12
    return d, f"{d.strftime('%b')} {d.day}, {h}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'} ET"


def _countdown(iso):
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    s = (d - datetime.now(timezone.utc)).total_seconds()
    if s <= 0:
        return ""
    days, rem = divmod(int(s), 86400)
    hrs, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return f"{days}d {hrs}h"
    return f"{hrs}h {mins:02d}m" if hrs else f"{mins} min"


def _first(s, n=150):
    s = re.sub(r"\s+", " ", s or "").strip()
    m = re.match(r"^(.{20,%d}?[.!?])(\s|$)" % n, s)
    if m:
        return m.group(1)
    return (s[:n].rsplit(" ", 1)[0] + "…") if len(s) > n else s


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


# ------------------------------------------------------------------ resolve an item
def resolve(kind, ident):
    """Return the item dict for one shareable thing, or None. Everything comes from server data, never from the URL."""
    kind = (kind or "").lower()
    ident = ident or ""
    fn = {"planet": _r_planet, "craft": _r_craft, "sat": _r_sat, "launch": _r_launch, "site": _r_site,
          "net": _r_net, "cloud": _r_cloud, "page": _r_page, "story": _r_story}.get(kind)
    if not fn:
        return None
    try:
        it = fn(ident)
    except Exception:
        it = None
    if it:
        it.setdefault("kind", kind)
        it.setdefault("id", ident)
    return it


def _r_planet(i):
    i = i.lower()
    if i not in PLANETS:
        return None
    name, fact, topic = PLANETS[i]
    S = _solar()
    pl = {p["id"]: p for p in (S.get("planets") or [])}
    earth = pl.get("earth")
    stats, lines = [], []
    if i == "moon":
        stats = [("238,900 mi", "from Earth"), ("27.3 days", "orbit"), ("1/6 g", "gravity")]
        lines = ["The Moon sits about 239,000 mi from Earth, and Apollo's six landing sites are all mapped in 3D.", fact]
    else:
        p = pl.get(i)
        if p:
            sun = math.sqrt(sum(c * c for c in p["pos"]))
            stats.append((f"{sun:.2f} AU", "from the Sun"))
            if earth and i != "earth":
                dd = math.sqrt(sum((a - b) ** 2 for a, b in zip(p["pos"], earth["pos"])))
                stats.insert(0, (_mi(dd), "from Earth now"))
                lines.append(f"{name} is {_mi(dd)} from Earth right now, moving {_mph(p['v_km_s'])} around the Sun.")
            else:
                lines.append(f"Earth is {_mi(sun)} from the Sun, moving {_mph(p['v_km_s'])} around it.")
            stats.append((_mph(p["v_km_s"]), "orbital speed"))
        lines.append(fact)
    lines.append("Fly there live in 3D.")
    return dict(title=name, kicker="PLANET · LIVE 3D", color=SPACE_C, stats=stats[:3], fact=fact, lines=lines, tags=topic + ["Astronomy", "NASA"],
                loc="", deep=f"/grid?sky={i}#sky", art=("planet", i), credit=PLANET_CREDIT.get(i, "NASA"),
                desc=lines[0])


def _craft_by_id(i):
    for c in _solar().get("craft") or []:
        if c.get("id") == i:
            return c
    return None


def _r_craft(i):
    i = i.lower()
    c = _craft_by_id(i)
    if not c:
        return None
    ph = {}
    try:
        import re as _re
        js = (NM / "solar3d.js").read_text()
        m = _re.search(r"var PHOTOS = (\{.*?\});\n", js)
        ph = json.loads(m.group(1)).get(i, {}) if m else {}
    except Exception:
        ph = {}
    name = "Starman's Tesla Roadster" if i == "roadster" else c.get("name") or i
    yrs = ""
    try:
        from datetime import date
        y, mth, d = map(int, (c.get("launch") or "").split("-"))
        yrs = f"{(date.today() - date(y, mth, d)).days / 365.25:.1f} yr"
    except Exception:
        pass
    stats = []
    if c.get("earth_au") is not None:
        stats.append((_mi(c["earth_au"]), "from Earth now"))
    if c.get("v_km_s") is not None:
        stats.append((_mph(c["v_km_s"]), "vs. the Sun"))
    if yrs:
        stats.append((yrs, "in space"))
    bits = []
    if c.get("earth_au") is not None:
        bits.append(f"{name} is {_mi(c['earth_au'])} from Earth right now, moving {_mph(c['v_km_s'])}." if c.get("v_km_s") else f"{name} is {_mi(c['earth_au'])} from Earth right now.")
    if i == "roadster":
        bits.append("A real Tesla with a mannequin at the wheel, flying since Feb 2018.")
    else:
        bits.append(_first(c.get("status") or "", 130))
    bits.append("Track it live in 3D.")
    return dict(title=name, kicker=("SPACECRAFT · " + (c.get("operator") or "").split(",")[0].split("(")[0].strip().upper())[:46], color=SPACE_C,
                stats=stats[:3], fact=_first(c.get("status") or "", 140), lines=bits, tags=(["Roadster", "Starman", "SpaceX"] if i == "roadster" else [x_share.to_tag(name).lstrip("#"), "Spacecraft", "NASA", "Space"]),
                loc="", deep=f"/grid?sky={i}#sky", art=("photo", f"learn/s3_{i}.jpg"), credit=(f"{ph.get('c', '')}. {ph.get('by', '')} ({ph.get('lic', '')})".strip(". ") if ph else ""), desc=bits[0])


def _r_sat(i):
    i = i.lower()
    L = _json_file("learn.json")
    s = L.get(i)
    if not s:
        return None
    name = s.get("name") or i.title()
    fact = _first(s.get("purpose") or "", 90)
    lines = [f"{name}: {fact}", _first(s.get("failure") or "", 140), "See every one of them live in 3D."]
    return dict(title=name, kicker="SATELLITES · " + (s.get("operator") or "").upper()[:30], color=SPACE_C,
                stats=[(str(s.get("first_label") or s.get("first") or "")[:11], "first launched")] if s.get("first") else [], fact=fact, lines=lines,
                tags=SAT_TAGS.get(i, [x_share.to_tag(name).lstrip("#")]) + ["Satellites", "Space"], loc="", deep=f"/grid?sky={i}#sky",
                art=("photo", s.get("image", "").replace("/api/netmap/", "") or f"learn/{i}.jpg"), credit=(s.get("credit") or "")[:110], desc=lines[0])


def _r_site(i):
    body, _, sid = i.partition("~")
    S = _json_file("planets/sites.json")
    rows = list(S.get(body) or []) + [f for f in (S.get("features") or []) if f.get("body") == body]
    st = next((r for r in rows if r.get("id") == sid), None)
    if not st:
        return None
    place = st.get("place") or ""
    nm = st.get("name") or sid
    date = st.get("date") or ""
    lines = [f"{nm}: {place}." if place else f"{nm}.", _first(st.get("text") or "", 150), "Explore it on the 3D globe."]
    return dict(title=nm, kicker=(f"{PLANETS.get(body, (body,))[0].upper()} · " + ("LANDING SITE" if date else "SURFACE FEATURE")), color=SPACE_C,
                stats=([(date[:4], "landed")] if date else []) + ([(f"{abs(st['lat']):.1f}°{'N' if st['lat'] >= 0 else 'S'}", "latitude")] if "lat" in st else []),
                fact=_first(st.get("text") or "", 140), lines=lines, tags=[nm.replace(" ", "")] + PLANETS.get(body, ("", "", []))[2][:1] + ["Space", "NASA"],
                loc=place, deep=f"/grid?sky={body}&pin={sid}#sky", art=("planet", body, st.get("lon", 0), st.get("lat", 0)),
                credit=PLANET_CREDIT.get(body, "NASA") + (" · " + st.get("source_name") if st.get("source_name") else ""), desc=lines[1])


def _launch_row(i):
    for L in _launches():
        if L.get("id") == i:
            return L
    return None


def _r_launch(i):
    L = _launch_row(i)
    if not L:
        return None
    veh = L.get("vehicle") or (L.get("name") or "").split("|")[0].strip()
    mis = L.get("mission") or (L.get("name") or "").split("|")[-1].strip()
    pad = L.get("pad") or ""
    if pad.lower().startswith("unknown"):
        pad = ""
    loc = (L.get("location") or "").replace(", People's Republic of China", ", China").replace(", United States of America", ", USA")
    place = loc.split(",")[0].strip() if loc else pad
    d, when = _et(L.get("net") or "")
    cd = _countdown(L.get("net") or "")
    st = L.get("status_name") or L.get("status") or ""
    junk = (not mis) or mis.lower().startswith("unknown") or mis == veh
    first = f"{veh}" if junk else f"{veh} | {mis}"
    if cd:
        first += f" lifts off in {cd} from {place}"
    else:
        first += f" launched from {place}" + (f" on {d.strftime('%b')} {d.day}" if d else "")
    orb = L.get("orbit_name") or L.get("orbit") or ""
    if orb and orb.upper() not in ("N/A", "UNKNOWN"):
        first += f", bound for {orb}"
    lines = [first + ".", f"Pad: {pad}." if pad else "", "Watch the launch chase in 3D."]
    big = cd or (d.strftime("%b ").upper() + str(d.day) if d else "")
    wd, _, wt = when.replace(" ET", "").partition(", ")
    stats = [(wd, f"NET {wt} ET".strip()) if when else ("", ""), (veh[:18], "vehicle"), ((L.get("orbit") or "")[:12] if (L.get("orbit") or "").upper() not in ("N/A", "UNKNOWN") else "", "orbit")]
    stats = [s for s in stats if s[0]]
    return dict(title=veh if junk else mis, kicker=f"LAUNCH · {veh}".upper()[:44], color=LAUNCH_C, stats=stats[:3], big=("T- " + cd if cd else (st or "").upper()), fact=first, lines=[x for x in lines if x],
                tags=[x_share.to_tag(veh).lstrip("#"), "RocketLaunch", "Spaceflight", x_share.to_tag(L.get("provider", "").split()[0] if L.get("provider") else "Space").lstrip("#") or "Space"],
                loc=loc, deep=f"/grid?launch={i}#sky", art=("rocket", veh, L.get("pad_lon"), L.get("pad_lat")), credit="", desc=first, place_text=place, pad=pad)


def _net_row(i):
    for n in _netdata().get("nets") or []:
        if n.get("id") == i:
            return n
    return None


LEVEL = {-1: ("NO LIVE SIGNAL", DIM), 0: ("OPERATIONAL", GREEN), 1: ("DEGRADED", AMBER), 2: ("OUTAGE", RED), 3: ("OUTAGE", RED)}


def _r_net(i):
    n = _net_row(i.lower())
    if not n:
        return None
    lv = n.get("level")
    lv = -1 if lv is None else int(lv)
    word, col = LEVEL.get(lv, LEVEL[0])
    nm = n.get("name") or i
    inc = n.get("incidents") or []
    status = (n.get("status") or "").strip().rstrip(".")
    if lv == -1:
        line = f"{nm}: no live status signal right now, so The Grid cannot confirm it either way."
    elif lv == 0:
        line = f"{nm} is operating normally on The Grid right now ({status[:1].lower() + status[1:] if status else 'no outage signal'})."
    else:
        line = f"{nm} is {'having an outage' if lv >= 2 else 'degraded'} right now: {status[:1].lower() + status[1:] if status else word.lower()}."
        if inc:
            t = inc[0].get("t") if isinstance(inc[0], dict) else str(inc[0])
            line += f" Latest: {_first(t, 90)}"
    lines = [line, f"{n.get('uptime')}% uptime over the last 30 days." if n.get("uptime") is not None else "", "Live status on The Grid."]
    grp = next((g["name"] for g in (_netdata().get("groups") or []) if g.get("id") == n.get("group")), "")
    stats = [(f"{n['uptime']}%", "30-day uptime")] if n.get("uptime") is not None else []
    stats.append((str(len(inc)), "active incidents" if inc else "active incidents"))
    if grp:
        stats.append((grp.split(" and ")[0][:22], "category"))
    topic = PROVIDER_TAGS.get(n.get("id"), []) or [x_share.to_tag(nm).lstrip("#")]
    return dict(title=nm, kicker=f"NETWORK STATUS · {grp}".upper()[:46], color=col, status=word, stats=stats[:3], fact=line, lines=[x for x in lines if x],
                tags=topic + ["Outage", "Internet"], loc="", deep=f"/grid/status/{n.get('id')}", art=("bars", n.get("days") or [], n.get("h24") or []),
                credit="Data: IODA and provider status pages", desc=line)


def _cloud_rows():
    return _netdata().get("cloud") or []


def _r_cloud(i):
    p, _, slug = i.partition("~")
    for r in _cloud_rows():
        if r.get("p") == p and _slug(r.get("name")) == slug:
            break
    else:
        return None
    pname = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud", "linode": "Akamai Cloud", "oci": "Oracle Cloud", "ibm": "IBM Cloud", "do": "DigitalOcean",
             "cloudflare": "Cloudflare", "m365": "Microsoft 365", "workspace": "Google Workspace"}.get(p, p.upper())
    lv = int(r.get("level") or 0)
    word, col = LEVEL.get(lv, LEVEL[0])
    ok_txt = {"OPERATIONAL": "no problems reported", "DEGRADED": "degraded service reported", "OUTAGE": "an outage reported", "NO LIVE SIGNAL": "no live signal"}[word]
    line = f"{pname} {r['name']} region: {ok_txt} right now."
    lines = [line, f"One of {len(_cloud_rows())} cloud regions on The Grid's live map.", "See it on the map."]
    return dict(title=f"{pname} · {r['name']}", kicker="CLOUD REGION", color=col, status=word, stats=[(f"{r['lat']:.1f}°, {r['lon']:.1f}°", "region location"), (pname, "provider")],
                fact=line, lines=lines, tags=PROVIDER_TAGS.get(p, [x_share.to_tag(pname).lstrip("#")]) + ["Cloud", "Datacenter", "Outage"], loc=r["name"],
                deep=f"/grid?cloud={quote(i, safe='~')}#map", art=("map", r["lon"], r["lat"], 26), credit="", desc=line)


def _r_page(i):
    i = i.lower()
    p = PAGES.get(i)
    if not p:
        return None
    extra = ""
    try:
        if i == "weather":
            import wxmap
            f = getattr(wxmap, "alert_count", None)
            n = f() if f else None
            if n:
                extra = f"{n} active NWS alerts right now."
    except Exception:
        pass
    lines = [(extra + " " if extra else "") + p["text"], "Open it live."]
    return dict(title=p["title"], kicker=p["kicker"], color=p["color"], stats=[p["stat"]], fact=p["text"], lines=lines, tags=list(p["tags"]), loc="",
                deep=p["path"], art=(("map",) + tuple(p["map"]) if p.get("map") else ("hero",) + tuple(p["hero"])), credit="", desc=p["text"], extra=extra)


def _story_item(cid):
    """Card data from the DB only. Never call api_state() here: on a 1-CPU Render node it can take tens of
    seconds, peg the CPU, and drop new TLS handshakes (SSL EOF on /wire/<id> while / and /healthz stay fast)."""
    cid = (cid or "").lower()
    if not re.fullmatch(r"[0-9a-f]{16}", cid):
        return None
    import wire_v2, story
    r, _al = story.load(cid)
    if not r:
        return None
    fams = [f for f in (r.get("families") or "").split(",") if f]
    it = {
        "cluster_id": cid,
        "title": r.get("title") or "",
        "brief": r.get("brief") or "",
        "rank": r.get("rank") or 0,
        "location": r.get("location") or "",
        "category": r.get("category") or "",
        "lat": r.get("lat"),
        "lon": r.get("lon"),
        "n_families": r.get("eff_families") or len(fams) or 1,
        "watchlist": r.get("watchlist") or 0,
        "hidden": r.get("hidden") or 0,
    }
    return it, wire_v2


def _r_story(cid):
    got = _hook("story", lambda: _story_item(cid)) if "story" in HOOKS else _story_item(cid)
    if not got or not got[0]:
        return None
    it, wire_v2 = got
    head = wire_v2.headline(it.get("title") or "") or it.get("title") or "Story"
    dek = ""
    try:
        dek = wire_v2.dek_for(it, head) or ""
    except Exception:
        pass
    rank = 0
    try:
        rank = int(it.get("rank") or 0)
    except Exception:
        pass
    col = RED if rank >= 7 else AMBER if rank >= 4 else GREEN
    fam = it.get("n_families") or 1
    cat = (it.get("category") or "").upper()
    tags = x_share.hashtags(dict(it, title=it.get("title") or head, headline=head))
    what = ""
    try:
        what = wire_v2.first_sentence(wire_v2.brief_parts(it.get("brief")).get("what") or "", 130)
    except Exception:
        what = ""
    norm = lambda x: re.sub(r"[^a-z0-9]+", " ", (x or "").lower()).strip()
    adds = what and len(what) > 30 and len(set(norm(what).split()) - set(norm(head).split())) >= max(4, len(set(norm(what).split())) // 2)
    dek = what if adds else f"Rank {rank}/10, reported by {fam} independent source famil{'y' if fam == 1 else 'ies'}."
    lines = [head, dek]
    photo = None
    try:   # data already on the box only (no network): the licensed photo for this story's entity or place
        import story_photo
        photo = story_photo.pick(it["cluster_id"], it.get("title") or "", it.get("location") or "", it.get("brief") or "")
        if photo and not story_photo.cached(photo["src"]):
            photo = dict(photo, pending=True)
    except Exception:
        photo = None
    have = bool(photo and not photo.get("pending"))
    card_title = _card_headline(it.get("title") or "") or _card_headline(head) or "Story"
    place, plat, plon = story_map_place(it.get("title") or "", it.get("location") or "", it.get("brief") or "", cid, it.get("lat"), it.get("lon"))
    loc = place or ""
    lon = plon if plon is not None else it.get("lon")
    lat = plat if plat is not None else it.get("lat")
    # Do not keep leftover stored coords when the Wire-map place has none or a different label.
    if place and plat is not None:
        lat, lon = plat, plon
    elif not place:
        lat, lon = None, None
    return dict(title=card_title, kicker=(cat or "THE WIRE")[:36], color=col, rank=rank, stats=[(f"{fam}", "source families")] + ([(str(loc)[:20], "location")] if loc else []),
                fact=dek or head, lines=[x for x in lines if x], tags=tags, loc=loc, deep=f"/wire/{cid}", share_url=f"{SITE}/wire/{cid}",
                art=("story", lon, lat, photo["src"] if have else None), credit="", desc=dek or head, item=it, photo=photo if have else None, photo_pending=bool(photo and photo.get("pending")))


_EDGE = r"[\s\ufeff\u200b-\u200d\u2060\xa0\-\u2010-\u2015\u2212\uFE58\uFE63\uFF0D\"“”„«»‘’‛′″'`.,;:|/\\·•]+"
_EDGE_CHARS = (
    " \t\r\n\ufeff\u200b\u200c\u200d\u2060\xa0"
    "-–—―−‐‒\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D"
    "\"“”„«»‘’‛′″'`.,;:|/\\·•"
)

def _strip_edges(t):
    """Strip leading and trailing dashes and punctuation (BOM, typographic dashes/quotes, ellipses).
    Repeat until stable so a dash+ellipsis mix at either end is fully removed."""
    t = " ".join((t or "").split())
    prev = None
    while t and t != prev:
        prev = t
        t = t.strip(_EDGE_CHARS)
        t = re.sub(r"^" + _EDGE, "", t)
        t = re.sub(_EDGE + r"$", "", t)
        t = re.sub(r"(?:\s*[\u2026…]|\s*\.{3,})\s*$", "", t).strip(_EDGE_CHARS)
    return t


_FONT_CMAP = None


def _is_latin_char(ch):
    """ASCII or a Latin-script letter (ş, ü, ñ, …). Used only when the font cmap cannot be loaded."""
    if ch.isascii():
        return True
    try:
        import unicodedata as ud
        return "LATIN" in ud.name(ch, "")
    except Exception:
        return False


def _card_font_cmap():
    """Codepoints the share-card Latin-Extended headline font can actually render."""
    global _FONT_CMAP
    if _FONT_CMAP is not None:
        return _FONT_CMAP
    cmap = {}
    try:
        from fontTools.ttLib import TTFont
        path = og.card_face_path()
        if path and Path(path).is_file():
            cmap = TTFont(str(path)).getBestCmap() or {}
    except Exception:
        cmap = {}
    _FONT_CMAP = cmap
    return _FONT_CMAP


def _strip_unrenderable(t):
    """Drop characters the card font has no glyph for (they paint as tofu boxes), then squeeze space."""
    if not t:
        return t
    cmap = _card_font_cmap()
    out = []
    for ch in t:
        if ch.isspace():
            out.append(" ")
            continue
        if cmap:
            if ord(ch) in cmap:
                out.append(ch)
            continue
        # Cmap missing: keep Latin Extended (Yaşar) but still drop Arabic etc.
        if _is_latin_char(ch):
            out.append(ch)
    return " ".join("".join(out).split())


def _clean_head(t):
    """Light cleanup only: drop a source-name fragment cut off after a colon at the very end ('...Strait of Hormuz: Crud'); nothing is reworded.
    Also drop a trailing ellipsis so the card can show the full headline. Leading/trailing dashes and punctuation are stripped.
    Characters the card font cannot render are removed, then leading punctuation is stripped again."""
    t = _strip_edges(t)
    t = _strip_unrenderable(t)
    t = _strip_edges(t)
    m = re.match(r"^(.{40,}?):\s*[A-Za-z]{1,6}$", t)
    return _strip_edges(m.group(1) if m else t)


def _card_headline(raw):
    """Headline for the share card: cleaned title, first sentence only (never two sentences squeezed in).
    _story_head may then shrink the font or cut at a clause boundary with an ellipsis."""
    t = _clean_head(raw)
    m = re.search(r"^(.+?(?<![A-Z])[.!?])\s+[@A-Z“\"«]", t)
    if m:
        t = m.group(1)
    return _strip_edges(t)


# ------------------------------------------------------------------ text + tags + urls
def tag_list(it):
    tags = []
    if it["kind"] == "story":
        raw = list(it.get("tags") or [])
        # keep to the PR #192 / min-3 generator; only pad when it returns fewer than 3
        for t in raw:
            if t not in tags:
                tags.append(t)
        for t in ("#News", "#Alerts", "#Wire"):
            if len(tags) >= 3:
                break
            if t not in tags:
                tags.append(t)
        return tags[:5]
    loc_item = {"title": it.get("loc") or "", "location": it.get("loc") or ""}
    locs = []
    if it.get("loc"):
        try:
            locs = x_share.location_tags(loc_item)[:2]
        except Exception:
            locs = []
    pool = locs + [x_share.to_tag(t) for t in it.get("tags") or []]
    for t in pool:
        if t and t not in tags and t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    for d in ("#Space", "#BlackoutNetwork") if it["kind"] in ("planet", "craft", "sat", "launch", "site") else ("#Internet", "#Outage", "#Weather"):
        if len(tags) >= 3:
            break
        if d.lower() not in [x.lower() for x in tags]:
            tags.append(d)
    return tags[:5]


def share_url(it):
    return it.get("share_url") or f"{SITE}/share/{it['kind']}/{quote(str(it['id']), safe='~:.-_')}"


def compose(it):
    tags = tag_list(it)
    url = share_url(it)
    tail = " ".join(tags)
    parts = [(p if re.search(r"[.!?…]$", p.strip()) else p.strip() + ".") for p in (it.get("lines") or []) if p]
    body = ""
    for p in parts:
        trial = (body + " " + p).strip()
        if x_share.weighted_len(trial + " " + tail, url) <= 280:
            body = trial
        elif not body:
            body = p[: 280 - 25 - len(tail) - 3].rsplit(" ", 1)[0] + "…"
            break
    text = (body + " " + tail).strip()
    while x_share.weighted_len(text, url) > 280 and tags:
        tags = tags[:-1] if len(tags) > 3 else tags
        if len(tags) <= 3:
            break
        text = (body + " " + " ".join(tags)).strip()
    return text, tags, url


def intent(it):
    text, tags, url = compose(it)
    return f"https://x.com/intent/post?text={quote(text, safe='')}&url={quote(url, safe='')}", text, tags, url


# ------------------------------------------------------------------ drawing
def _lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def _stars(im, seed, n=140):
    d = ImageDraw.Draw(im)
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    for _ in range(n):
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        x = h % W
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        y = h % H
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        b = 70 + h % 150
        d.point((x, y), fill=(b, b, min(255, b + 12)))


def _texture(body):
    if body in ("uranus", "neptune", "mercury", "venus") and not _static_bytes(f"planets/{body}.jpg"):
        return None
    t = _img(f"planets/{body}.jpg")
    if t is None:
        return None
    if t.width > 1400:
        t = t.resize((1400, 700), Image.Resampling.LANCZOS)
    return t


def _sphere(tex, d, lon0, lat0, mark=None, glow=(120, 150, 255)):
    R = d / 2.0
    px = tex.load()
    tw, th = tex.size
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    op = out.load()
    cl, sl = math.cos(lat0), math.sin(lat0)
    lx, ly, lz = -0.55, 0.45, 0.70
    n = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / n, ly / n, lz / n
    for j in range(d):
        y = (R - j - 0.5) / R
        for i in range(d):
            x = (i + 0.5 - R) / R
            r2 = x * x + y * y
            if r2 >= 1.0:
                continue
            z = math.sqrt(1.0 - r2)
            y2 = y * cl + z * sl
            z2 = z * cl - y * sl
            lat = math.asin(max(-1.0, min(1.0, y2)))
            lon = lon0 + math.atan2(x, z2)
            u = (lon / (2 * math.pi) + 0.5) % 1.0
            v = 0.5 - lat / math.pi
            c = px[int(u * tw) % tw, min(th - 1, max(0, int(v * th)))]
            sh = max(0.0, x * lx + y * ly + z * lz)
            k = 0.16 + 0.95 * sh ** 0.85
            k *= 0.72 + 0.28 * z  # limb darkening
            a = int(255 * min(1.0, (1.0 - math.sqrt(r2)) * R / 1.4))
            op[i, j] = (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)), a)
    if mark is not None:  # (lon_rad, lat_rad) pin ring
        mlon, mlat = mark
        cx = math.cos(mlat) * math.sin(mlon - lon0)
        cy = math.cos(lat0) * math.sin(mlat) - math.sin(lat0) * math.cos(mlat) * math.cos(mlon - lon0)
        cz = math.sin(lat0) * math.sin(mlat) + math.cos(lat0) * math.cos(mlat) * math.cos(mlon - lon0)
        if cz > 0:
            ov = Image.new("RGBA", out.size, (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            px_, py_ = R + cx * R, R - cy * R
            for r_, a_ in ((34, 70), (22, 130), (10, 255)):
                od.ellipse([px_ - r_, py_ - r_, px_ + r_, py_ + r_], outline=(255, 255, 255, a_), width=3 if r_ > 10 else 0, fill=(255, 255, 255, 255) if r_ == 10 else None)
            out = Image.alpha_composite(out, ov)
    return out


def _glow(size, color, strength=90):
    g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([size * 0.2, size * 0.2, size * 0.8, size * 0.8], fill=color + (strength,))
    return g.filter(ImageFilter.GaussianBlur(size * 0.09))


def _saturn_rings(im, cx, cy, r, front):
    rl = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(rl)
    tilt = 0.30
    bands = [(1.25, 1.42, (160, 148, 120, 120)), (1.44, 1.78, (206, 190, 150, 190)), (1.80, 1.92, (150, 140, 118, 150)), (1.96, 2.25, (190, 176, 140, 130))]
    for a, b, col in bands:
        d.ellipse([cx - b * r, cy - b * r * tilt, cx + b * r, cy + b * r * tilt], outline=col, width=int((b - a) * r))
    if front:
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rectangle([0, int(cy), im.width, im.height], fill=255)
        rl.putalpha(Image.composite(rl.getchannel("A"), Image.new("L", im.size, 0), mask))
    return rl


_GEO = {}


def _geo():
    if "w" not in _GEO:
        try:
            _GEO["w"] = json.loads((BASE / "signal_map_static" / "world.geojson").read_text())["features"]
        except Exception:
            _GEO["w"] = []
        try:
            _GEO["s"] = json.loads((BASE / "signal_map_static" / "us_states.geojson").read_text())["features"]
        except Exception:
            _GEO["s"] = []
    return _GEO


def _rings_of(geom):
    t = geom.get("type")
    c = geom.get("coordinates") or []
    if t == "Polygon":
        return [r for r in c]
    if t == "MultiPolygon":
        return [r for p in c for r in p]
    return []


def _map(w, h, lon, lat, span, color=WHITE, marks=None, seed="", fx=0.5, track=None, marker=True):
    """Dark vector map crop (equirectangular, cos-lat corrected) with a pulsing marker at (lon, lat). span = degrees of latitude shown."""
    S = 2
    im = Image.new("RGB", (w * S, h * S), (7, 9, 15))
    d = ImageDraw.Draw(im)
    k = (h * S) / span
    kx = k * max(0.35, math.cos(math.radians(lat)))
    cx, cy = w * S * fx, h * S / 2
    P = lambda lo, la: (cx + (lo - lon) * kx, cy - (la - lat) * k)
    for gl in range(-180, 181, 10 if span > 20 else 5):
        x = P(gl, 0)[0]
        if 0 <= x <= w * S:
            d.line([(x, 0), (x, h * S)], fill=(14, 17, 26), width=1)
    for gl in range(-90, 91, 10 if span > 20 else 5):
        y = P(0, gl)[1]
        if 0 <= y <= h * S:
            d.line([(0, y), (w * S, y)], fill=(14, 17, 26), width=1)
    G = _geo()
    for f in G.get("w", []):
        for ring in _rings_of(f["geometry"]):
            pts = [P(a, b) for a, b in ((p[0], p[1]) for p in ring)]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if max(xs) < 0 or min(xs) > w * S or max(ys) < 0 or min(ys) > h * S:
                continue
            d.polygon(pts, fill=(33, 41, 57), outline=(88, 100, 126))
    if span <= 40:
        for f in G.get("s", []):
            for ring in _rings_of(f["geometry"]):
                pts = [P(p[0], p[1]) for p in ring]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if max(xs) < 0 or min(xs) > w * S or max(ys) < 0 or min(ys) > h * S:
                    continue
                d.line(pts + pts[:1], fill=(46, 54, 70), width=1)
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    if track and len(track) > 1:
        od.line([P(a_, b_) for a_, b_ in track], fill=color + (230,), width=5, joint="curve")
    for (mlo, mla, mc) in (([(lon, lat, color)] if marker else []) + list(marks or [])):
        mx, my = P(mlo, mla)
        for r_, a_ in ((70, 40), (46, 70), (26, 120)):
            od.ellipse([mx - r_, my - r_, mx + r_, my + r_], outline=mc + (a_,), width=3)
        od.ellipse([mx - 11, my - 11, mx + 11, my + 11], fill=mc + (255,), outline=(255, 255, 255, 255), width=3)
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    return im.resize((w, h), Image.Resampling.LANCZOS)


def _fade_edge(panel, side="left", frac=0.45):
    """Gradient mask: panel fades into BG on the given side."""
    w, h = panel.size
    m = Image.new("L", (w, h), 255)
    md = ImageDraw.Draw(m)
    span = int(w * frac)
    for x in range(span):
        a = int(255 * (x / span) ** 1.4)
        xx = x if side == "left" else w - 1 - x
        md.line([(xx, 0), (xx, h)], fill=a)
    return m


def _cover(im, w, h):
    return og._cover(im, w, h)


def _tx(d, xy, text, font, fill, tracking=0):
    return og._draw_tracked(d, xy, text, font, fill, tracking)


def _chrome(im, it, credit=True):
    d = ImageDraw.Draw(im)
    og.draw_wordmark(im, d, 64, 44, og.inter(22, bold=True), (220, 223, 230), tracking=3.2, mark=36, gap=10)
    col = it.get("color") or WHITE
    k = (it.get("kicker") or "").upper()
    if k:
        f = og.inter(15, bold=True)
        wd = og._text_w(d, k, f, 3.0)
        d.rounded_rectangle([W - 64 - wd - 28, 40, W - 64, 74], radius=17, outline=col + (255,) if len(col) == 3 else col, width=2, fill=(5, 6, 10))
        _tx(d, (W - 64 - wd - 14, 49), k, f, col, 3.0)
    cr = (it.get("credit") or "").strip()
    if credit and cr:
        f = og.inter(13)
        strip = Image.new("RGBA", (W, 44), (5, 6, 10, 200))
        im.paste(strip.convert("RGB"), (0, H - 44), strip.getchannel("A"))
        t = "Image: " + cr
        while og._text_w(d, t, f, 0.3) > W - 128 and len(t) > 20:
            t = t[:-2]
        _tx(d, (64, H - 34), t, f, (128, 134, 146), 0.3)


def _stat_row(im, stats, x0, y0, maxw, color):
    d = ImageDraw.Draw(im)
    n = max(1, len(stats))
    gap = 16
    cw = int((maxw - gap * (n - 1)) / n)
    for i, (v, lab) in enumerate(stats[:3]):
        x = x0 + i * (cw + gap)
        d.rounded_rectangle([x, y0, x + cw, y0 + 104], radius=10, fill=(12, 15, 22), outline=(46, 52, 66), width=1)
        d.rectangle([x, y0 + 14, x + 4, y0 + 90], fill=color)
        v = str(v)
        size = 40
        f = og.mont(size, 800)
        while og._text_w(d, v, f, 0) > cw - 36 and size > 20:
            size -= 2
            f = og.mont(size, 800)
        _tx(d, (x + 20, y0 + 18), v, f, WHITE, 0)
        _tx(d, (x + 20, y0 + 72), lab.upper(), og.inter(12, bold=True), MUTED, 2.0)


def _title_block(im, title, x, y, maxw, max_lines=3, base=84, fill=WHITE, minsize=40):
    d = ImageDraw.Draw(im)
    title = og._strip_emoji(title)
    size = base
    while True:
        f = og.mont(size, 800)
        lines = og._wrap(d, title, f, maxw, 0, max_lines=max_lines + 1)
        if (len(lines) <= max_lines and all(og._text_w(d, l, f, 0) <= maxw for l in lines)) or size <= minsize:
            break
        size -= 4
    lines = og._wrap(d, title, f, maxw, 0, max_lines=max_lines)
    for i, l in enumerate(lines):
        _tx(d, (x, y + i * int(size * 1.08)), l, f, fill, 0)
    return y + len(lines) * int(size * 1.08)


def _para(im, text, x, y, maxw, size=24, fill=(205, 210, 220), max_lines=3):
    d = ImageDraw.Draw(im)
    f = og.inter(size, bold=False)
    lines = og._wrap(d, text, f, maxw, 0.2, max_lines=max_lines)
    for i, l in enumerate(lines):
        _tx(d, (x, y + i * int(size * 1.4)), l, f, fill, 0.2)
    return y + len(lines) * int(size * 1.4)


def _base(seed):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for y in range(H):
        c = int(4 + 9 * y / H)
        d.line([(0, y), (W, y)], fill=(c, c + 1, c + 4))
    return im


def _paste_rgba(im, layer, xy):
    im.paste(layer.convert("RGB"), xy, layer.getchannel("A"))


# ---- layouts
def _lay_planet(it):
    art = it["art"]
    body = art[1]
    im = _base(it["id"])
    _stars(im, it["kind"] + it["id"])
    cx, cy, D = (905 if body == "saturn" else 850), 345, 500
    tex = _texture(body)
    lon0 = {"earth": -1.45, "jupiter": 0.6, "mars": 1.1, "moon": 0.0, "saturn": 0.2, "venus": 2.6, "mercury": 0.5}.get(body, 0.3)
    lat0 = 0.28 if body not in ("saturn",) else 0.18
    mark = None
    if len(art) >= 4:
        lon0, lat0 = math.radians(art[2]), math.radians(art[3]) * 0.8
        mark = (math.radians(art[2]), math.radians(art[3]))
    g = _glow(int(D * 1.9), (110, 140, 230) if body != "mars" else (200, 110, 70), 70)
    im.paste(g.convert("RGB"), (cx - g.width // 2, cy - g.height // 2), g.getchannel("A"))
    if body == "saturn":
        D = 330
        rl_back = _saturn_rings(im, cx, cy, D / 2, False)
        im.paste(rl_back.convert("RGB"), (0, 0), rl_back.getchannel("A"))
    if tex is None:
        tex = Image.new("RGB", (512, 256), {"mercury": (130, 125, 120), "venus": (205, 170, 120), "uranus": (150, 205, 215), "neptune": (70, 110, 215)}.get(body, (120, 120, 130)))
        td = ImageDraw.Draw(tex)
        for yy in range(0, 256, 8):  # soft cloud-band texture so it is not a flat disc
            sh = int(14 * math.sin(yy / 11.0))
            td.rectangle([0, yy, 512, yy + 8], fill=tuple(max(0, min(255, c + sh)) for c in tex.getpixel((1, yy))))
        tex = tex.filter(ImageFilter.GaussianBlur(2))
    sp = _sphere(tex, D, lon0, lat0, mark=mark)
    _paste_rgba(im, sp, (cx - D // 2, cy - D // 2))
    if body == "saturn":
        rl_front = _saturn_rings(im, cx, cy, D / 2, True)
        im.paste(rl_front.convert("RGB"), (0, 0), rl_front.getchannel("A"))
    # left column
    y = _title_block(im, it["title"], 64, 150, 560, 2, base=96)
    _para(im, it.get("fact") or "", 64, y + 22, 470 if body == "saturn" else 520, 26, max_lines=4)
    _stat_row(im, it["stats"], 64, 470, 560, it["color"])
    _chrome(im, it)
    return im


def _lay_photo(it):
    """Spacecraft / satellite group: real photo fills the left half, text and stats on the right."""
    im = _base(it["id"])
    _stars(im, it["id"], 90)
    ph = _img(it["art"][1])
    pw = 640
    if ph is not None:
        p = _cover(ph, pw, H)
        p = ImageEnhance.Brightness(ImageEnhance.Color(p).enhance(0.9)).enhance(0.85)
        im.paste(p, (0, 0), _fade_edge(p, "right", 0.5))
    else:
        g = _glow(700, (110, 140, 230), 80)
        im.paste(g.convert("RGB"), (-100, 0), g.getchannel("A"))
    x = 560
    y = _title_block(im, it["title"], x, 140, W - x - 64, 3, base=70)
    _para(im, it.get("fact") or "", x, y + 20, W - x - 64, 22, max_lines=3)
    _stat_row(im, it["stats"], x, 470, W - x - 64, it["color"])
    _chrome(im, it)
    return im


def _lay_launch(it):
    art = it["art"]
    im = _base(it["id"])
    _stars(im, it["id"], 70)
    # rocket photo (portrait, Public domain / CC0 only) on the right; otherwise a map of the pad with the ascent track
    rk = None
    credit = ""
    try:
        import netlaunch
        ph = netlaunch.rocket_photo(art[1])
        if ph and re.match(r"^(Public domain|CC0)", ph.get("license") or "", re.I):
            rk = _img("rockets/" + ph["url"].rsplit("/", 1)[-1])
            credit = f"{ph.get('pictured', '')}, {ph.get('author', '')} ({ph.get('license', '')})"
    except Exception:
        pass
    if rk is not None:
        p = _cover(rk, 430, H)
        p = ImageEnhance.Brightness(p).enhance(0.9)
        im.paste(p, (W - 430, 0), _fade_edge(p, "left", 0.55))
        it["credit"] = credit.strip(", ")
    elif art[2] is not None and art[3] is not None:
        marks = []
        try:
            L = _launch_row(it["id"]) or {}
            asc = [(pt[0], pt[1]) for pt in (L.get("ascent") or []) if len(pt) >= 2]
        except Exception:
            asc = []
        m = _map(520, H, art[2], art[3], 24, it["color"], fx=0.3, track=asc)
        im.paste(m, (W - 520, 0), _fade_edge(m, "left", 0.4))
    big = it.get("big") or ""
    x = 64
    d = ImageDraw.Draw(im)
    _tx(d, (x, 120), "NEXT LAUNCH" if big.startswith("T-") else "LAUNCH", og.inter(15, bold=True), it["color"], 3.2)
    f = og.mont(110 if len(big) < 11 else 80, 800)
    _tx(d, (x, 146), big, f, WHITE, 0)
    y = _title_block(im, it["title"], x, 290, 680, 2, base=52, minsize=30)
    pad = it.get("pad") or it.get("loc") or ""
    y = _para(im, pad + (", " + it["place_text"] if it.get("place_text") and it["place_text"] not in pad else ""), x, y + 6, 640, 22, fill=MUTED, max_lines=2)
    # pad map inset (only when the right side shows a photo)
    lon, lat = art[2], art[3]
    if rk is not None and lon is not None and lat is not None:
        m = _map(210, 124, lon, lat, 28, it["color"])
        im.paste(m, (W - 430 - 230 - 24 + 24, 470))
        d.rectangle([W - 430 - 230, 470, W - 430 - 230 + 209, 470 + 123], outline=(70, 78, 96), width=1)
    _stat_row(im, it["stats"], x, 470, 520, it["color"])
    _chrome(im, it)
    return im


def _lay_bars(it):
    art = it["art"]
    days = art[1] or []
    im = _base(it["id"])
    d = ImageDraw.Draw(im)
    col = it["color"]
    d.rectangle([0, 0, 14, H], fill=col)
    word = it.get("status") or "STATUS"
    _tx(d, (64, 120), word, og.inter(18, bold=True), col, 4.0)
    y = _title_block(im, it["title"], 64, 152, W - 128, 2, base=92)
    _para(im, it.get("fact") or "", 64, y + 20, 900, 24, max_lines=2)
    # 30-day strip: one bar per day, height = severity (zero days show as a thin green tick)
    x0, x1, yb, hh = 64, W - 64, 600, 120
    d.text((64, yb - hh - 34), "LAST 30 DAYS", font=og.inter(13, bold=True), fill=DIM)
    n = max(1, len(days))
    bw = (x1 - x0) / max(30, n)
    mx = max([1] + [int(v or 0) for v in days])
    for i, v in enumerate(days):
        v = int(v or 0)
        xx = x0 + i * bw
        if v == 0:
            d.rectangle([xx + 2, yb - 8, xx + bw - 3, yb], fill=(30, 94, 62))
        else:
            h_ = 14 + int((hh - 14) * min(1.0, v / mx))
            c = RED if v >= 2 else AMBER
            d.rectangle([xx + 2, yb - h_, xx + bw - 3, yb], fill=c)
    _stat_row(im, it["stats"], 64, 380, 760, col)
    _chrome(im, it)
    return im


def _lay_map(it):
    art = it["art"]
    im = _base(it["id"])
    m = _map(780, H, art[1], art[2], art[3], it["color"], fx=0.55)
    im.paste(m, (W - 780, 0), _fade_edge(m, "left", 0.3))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12, H], fill=it["color"])
    _tx(d, (64, 120), it.get("status") or "", og.inter(18, bold=True), it["color"], 4.0)
    y = _title_block(im, it["title"], 64, 152, 560, 3, base=70)
    _para(im, it.get("fact") or "", 64, y + 20, 500, 22, max_lines=3)
    _stat_row(im, it["stats"], 64, 470, 520, it["color"])
    _chrome(im, it)
    return im


def _lay_hero(it):
    art = it["art"]
    src = og._open_bg(art[1], art[2]) if len(art) >= 3 else None
    im = og._darken(src).resize((W, H)) if src is not None else _base(it["id"])
    if im.size != (W, H):
        im = im.resize((W, H))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12, H], fill=it["color"])
    y = _title_block(im, it["title"], 64, 190, W - 128, 2, base=96)
    _para(im, it.get("lines")[0] if it.get("lines") else "", 64, y + 12, 860, 28, max_lines=3, fill=(225, 229, 238))
    _stat_row(im, it["stats"], 64, 500, 360, it["color"])
    _chrome(im, it)
    return im


def _wrap_full(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if og._text_w(d, t, f, 0) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


# Readable minimum matches Bessent's photo-card size (32). Never shrink below this.
HEAD_MIN = 32

# Words a clipped headline must not end on (dangling preposition / article / conjunction).
_DANGLING = frozenset({
    "a", "an", "the", "and", "or", "but", "nor", "so",
    "at", "in", "on", "of", "to", "for", "from", "with", "by", "as",
    "into", "onto", "over", "under", "about", "after", "before",
    "against", "between", "through", "during", "without", "within",
    "upon", "via", "per", "plus", "including", "amid", "than",
})
# Opening of a prepositional / clausal phrase; cutting just before one is a natural boundary.
_PHRASE_START = _DANGLING


def _word_key(w):
    return re.sub(r"[^A-Za-z0-9]+", "", w or "").lower()


def _ends_dangling(words):
    if not words:
        return True
    last = _word_key(words[-1])
    if last in _DANGLING or not last:
        return True
    # "including 48" is not a complete phrase — the noun is missing.
    if last.isdigit() and len(words) >= 2 and _word_key(words[-2]) in _PHRASE_START:
        return True
    return False


def _trim_dangling(words):
    w = list(words)
    while w and _ends_dangling(w):
        w.pop()
    # Incomplete "as a second…" / "including 48 anti-ballistic…" — cut before the phrase
    # unless at least three words follow (as + article/modifier + noun).
    for i in range(len(w) - 1, 0, -1):
        if _word_key(w[i]) in ("as", "including") and len(w) - i - 1 < 3:
            w = w[:i]
            while w and _ends_dangling(w):
                w.pop()
            break
    return w


def _head_lines_fit(d, text, f, maxw, max_lines):
    lines = _wrap_full(d, text, f, maxw)
    if len(lines) <= max_lines and all(og._text_w(d, l, f, 0) <= maxw for l in lines):
        return lines
    return None


def _clause_prefixes(words):
    """Prefixes from longest to shortest, preferring a comma or a cut before an at/in/on phrase."""
    seen = set()
    cands = []

    def emit(chunk):
        w = _trim_dangling(chunk)
        key = tuple(w)
        if not w or key in seen:
            return
        seen.add(key)
        cands.append(w)

    for n in range(len(words), 0, -1):
        chunk = words[:n]
        emit(chunk)
        for i in range(len(chunk) - 1, -1, -1):
            if chunk[i].endswith((",", ";", ":")):
                emit(chunk[: i + 1])
                break
        for i in range(len(chunk) - 1, 0, -1):
            if _word_key(chunk[i]) in _PHRASE_START:
                emit(chunk[:i])
                break
    cands.sort(key=len, reverse=True)
    return cands


def _cut_head_lines(d, title, f, maxw, max_lines):
    """Longest first-sentence prefix that fits in the box, ending at a clause boundary, with an ellipsis."""
    words = (title or "").split()
    for prefix in _clause_prefixes(words):
        text = " ".join(prefix).rstrip(" ,;:-") + "…"
        lines = _head_lines_fit(d, text, f, maxw, max_lines)
        if lines:
            return lines
    # Last resort: first words plus ellipsis, still not dangling.
    for n in range(min(len(words), 12), 0, -1):
        prefix = _trim_dangling(words[:n])
        if not prefix:
            continue
        text = " ".join(prefix).rstrip(" ,;:-") + "…"
        lines = _head_lines_fit(d, text, f, maxw, max_lines)
        if lines:
            return lines
    lines = _wrap_full(d, title, f, maxw)[:max_lines]
    if lines:
        last = _trim_dangling(lines[-1].split())
        lines[-1] = ((" ".join(last).rstrip(" ,;:-") + "…") if last else "…")
    return lines


def _headline_would_clip(title, maxw=640, max_lines=3):
    """True when the first sentence does not fit in the 3-line box at HEAD_MIN (old typography would cut mid-phrase)."""
    if not title:
        return False
    try:
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        head = _card_headline(title) or title
        head = re.sub(r"(?:\s*[\u2026…]|\s*\.{3,})\s*$", "", head).strip()
        f = og.card_face(HEAD_MIN)
        # The tighter photo-card width (640) is the one that clips Hegseth; also check 700.
        for w in (maxw, 700, 640):
            if _head_lines_fit(d, head, f, w, max_lines) is None:
                return True
        return False
    except Exception:
        # If we cannot measure, treat a long first sentence as possibly clipped.
        return len((title or "").split()) >= 16


def card_needs_headline_refit(meta, title=""):
    """True when a stored card predates the mid-phrase typography fix (24M) and the headline would have been clipped."""
    if not meta:
        return False
    if str(meta.get("v") or "").endswith("M"):
        return False
    return _headline_would_clip(title or "")


def _story_head(d, title, maxw, max_lines=3, start=54, minsize=HEAD_MIN):
    """Headline on at most 3 lines at a readable size. Prefer the full first sentence;
    shrink down to minsize (Bessent's 32) if needed. If it still cannot fit, cut at a
    comma or before an at/in/on phrase and append an ellipsis. Never end on a dangling
    preposition or article ('at the', 'of', 'and')."""
    title = _card_headline(title or "") or og._strip_emoji(title or "")
    title = re.sub(r"(?:\s*[\u2026…]|\s*\.{3,})\s*$", "", title).strip()
    minsize = max(int(minsize or HEAD_MIN), HEAD_MIN)
    size = start
    while size >= minsize:
        f = og.card_face(size)
        lines = _head_lines_fit(d, title, f, maxw, max_lines)
        if lines:
            return f, size, lines
        size -= 2
    f = og.card_face(minsize)
    lines = _head_lines_fit(d, title, f, maxw, max_lines)
    if lines:
        return f, minsize, lines
    return f, minsize, _cut_head_lines(d, title, f, maxw, max_lines)


def _story_bg(it):
    """(background RGB image, subject RGBA or None, credit text, label text). Photo if one is stored, else a dark location map; never plain black."""
    ph = it.get("photo")
    col = it["color"]
    if ph:
        try:
            import story_photo
            p = story_photo.cached(ph["src"])
            src = Image.open(p).convert("RGB")
            sw, sh = src.size
            cred = "Image: " + " ".join((ph.get("credit") or "").split()).rstrip(". ")
            if ph.get("license"):
                cred += ". " + " ".join(str(ph.get("license")).split())
            cred += "."
            label = " ".join((ph.get("label") or "").split())
            if sh >= sw * 1.05:   # portrait: sharp subject on the right over a soft field taken from the photo's own background
                band = src.crop((0, 0, sw, max(8, int(sh * 0.36))))
                field = og._cover(band, W, H).filter(ImageFilter.GaussianBlur(36))
                field = ImageEnhance.Brightness(ImageEnhance.Color(field).enhance(0.55)).enhance(0.22)
                c = src.crop((int(sw * 0.06), int(sh * 0.04), int(sw * 0.94), int(sh * 0.80)))
                scale = H / c.size[1]
                sub = c.resize((max(1, int(c.size[0] * scale)), H), Image.Resampling.LANCZOS)
                if sub.size[0] > 540:
                    k = 540 / sub.size[0]
                    cx0 = int(c.size[0] * (1 - k) / 2)
                    c = c.crop((cx0, 0, cx0 + int(c.size[0] * k), c.size[1]))
                    sub = c.resize((max(1, int(c.size[0] * H / c.size[1])), H), Image.Resampling.LANCZOS)
                sub = ImageEnhance.Contrast(sub).enhance(1.05).convert("RGBA")
                fade = min(100, sub.size[0] // 3)
                m = Image.new("L", sub.size, 255)
                md = ImageDraw.Draw(m)
                for x in range(fade):
                    md.line([(x, 0), (x, H)], fill=int(255 * (x / fade) ** 1.15))
                sub.putalpha(m)
                field = field.convert("RGBA")
                field.paste(sub, (W - sub.size[0], 0), sub)
                return field.convert("RGB"), True, cred, label
            bgim = ImageEnhance.Brightness(og._cover(src, W, H)).enhance(0.72)   # landscape: full bleed
            return bgim, False, cred, label
        except Exception:
            pass
    # Never a map (Matt 4:47 PM ET Nov 25 2026): with no photo yet, the plain dark card; the convert worker adds a real photo.
    return _base(it["id"]), False, "", ""


def _fit_chip(d, text, maxw):
    """Chip text that fits maxw: shrink the font (13 -> 9 px) and tracking first; if it still cannot fit,
    drop whole trailing comma parts. Words are never cut mid-word."""
    text = " ".join((text or "").split())
    parts = [t.strip() for t in text.split(",") if t.strip()] or [text]
    while True:
        cand = ", ".join(parts)
        for size, trk in ((13, 2.4), (12, 2.0), (11, 1.6), (10, 1.2), (9, 0.8)):
            f = og.inter(size, bold=True)
            wd = og._text_w(d, cand, f, trk)
            if wd <= maxw:
                return f, trk, cand, wd
        if len(parts) <= 1:
            return f, trk, cand, wd
        parts = parts[:-1]

def _lay_story(it):
    """News card: photo (or dark location map) full bleed, dark gradient on the left, rank badge, whole headline, category + place chips."""
    col = it["color"]
    im, portrait, credit, label = _story_bg(it)
    ov = Image.new("L", (W, H), 0)
    od = ImageDraw.Draw(ov)
    edge = 0.58 if portrait else 0.74
    for x in range(W):
        t = min(1.0, max(0.0, x / (edge * W)))
        t = t * t * (3 - 2 * t)
        od.line([(x, 0), (x, H)], fill=int(205 * (1 - t) + (18 if portrait else 70) * t))
    im = Image.composite(Image.new("RGB", (W, H), (5, 6, 10)), im, ov)
    bot = Image.new("L", (W, 120), 0)
    bd = ImageDraw.Draw(bot)
    for y in range(120):
        bd.line([(0, y), (W, y)], fill=int(170 * (y / 120) ** 1.4))
    im.paste(Image.new("RGB", (W, 120), (5, 6, 10)), (0, H - 120), bot)
    top = Image.new("L", (W, 90), 0)
    td = ImageDraw.Draw(top)
    for y in range(90):
        td.line([(0, y), (W, y)], fill=int(110 * (1 - y / 90)))
    im.paste(Image.new("RGB", (W, 90), (5, 6, 10)), (0, 0), top)
    d = ImageDraw.Draw(im)
    wm = og.inter(20, bold=True)
    x = og.draw_wordmark(im, d, 56, 34, wm, (232, 234, 238), tracking=2.6, mark=36, gap=10) + 22
    chips = [((it.get("kicker") or "THE WIRE").upper(), col)]
    ph = it.get("photo")
    if it.get("loc") and not (ph and ph.get("kind") == "person"):   # a person's portrait is not a picture of the story's place
        chips.append((og._strip_emoji(it["loc"]).upper(), (214, 218, 226)))
    for text, c in chips:
        f, trk, text, wd = _fit_chip(d, text, W - 56 - x - 24 - 24)
        d.rounded_rectangle([x, 34, x + wd + 24, 64], radius=15, fill=(8, 10, 14), outline=c, width=2)
        _tx(d, (x + 12, 41 + (13 - getattr(f, "size", 13)) // 2), text, f, c, trk)
        x += wd + 34
    rank = it.get("rank") or 0
    rf = og.mont(26, 800)
    label_r = f"{rank} / 10"
    wd = og._text_w(d, label_r, rf, 0)
    d.rounded_rectangle([56, 196, 56 + wd + 28, 236], radius=8, fill=(8, 10, 14), outline=col, width=2)
    d.rectangle([56, 203, 60, 229], fill=col)
    _tx(d, (72, 202), label_r, rf, col, 0)
    f, size, lines = _story_head(d, it["title"], 640 if portrait else 700)
    y = 252
    for i, l in enumerate(lines):
        _tx(d, (56, y + i * int(size * 1.08)), l, f, WHITE, 0)
    y += len(lines) * int(size * 1.08)
    if label:
        for i, l in enumerate(_wrap_full(d, label, og.inter(15), 620)[:2]):
            _tx(d, (56, y + 14 + i * 20), l, og.inter(15), (186, 192, 202), 0)
    elif not ph and it.get("loc"):
        _tx(d, (56, y + 16), og._strip_emoji(it["loc"]).upper()[:40], og.inter(14, bold=True), (200, 205, 214), 2.6)
    if credit:
        cf = og.inter(12)
        t = " ".join(str(credit).split())
        while t and og._text_w(d, t, cf, 0) > W - 112 and len(t) > 24:
            t = t[:-2]
        im.paste(Image.new("RGB", (W, 38), (5, 6, 10)), (0, H - 38), Image.new("L", (W, 38), 190))
        d = ImageDraw.Draw(im)
        _tx(d, (56, H - 28), t, cf, (156, 162, 172), 0)
    return im


def _lay_type(it):
    """No picture available for this item: category-colored typographic card with unique concentric-ring art seeded by the item."""
    im = _base(it["id"])
    d = ImageDraw.Draw(im)
    col = it["color"]
    h = int(hashlib.md5((it["kind"] + str(it["id"])).encode()).hexdigest()[:8], 16)
    cx, cy = 820 + (h % 160), 250 + ((h >> 8) % 220)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    n = 5 + (h >> 16) % 4
    for k in range(1, n + 1):
        r = 46 * k + ((h >> (k + 3)) % 14)
        od.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col + (max(24, 150 - 17 * k),), width=2 + (k == 1) * 2)
    od.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=col + (255,))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12, H], fill=col)
    y = _title_block(im, it["title"], 64, 150, 640, 3, base=84, minsize=42)
    _para(im, it.get("fact") or "", 64, y + 22, 600, 24, max_lines=4)
    if it.get("stats"):
        _stat_row(im, it["stats"], 64, 470, 560, col)
    _chrome(im, it)
    return im


def render(it):
    a = it.get("art") or ("hero", "media", "hero-d.jpg")
    t = a[0]
    if t == "planet":
        return _lay_planet(it)
    if t == "photo":
        return _lay_photo(it)
    if t == "rocket":
        return _lay_launch(it)
    if t == "bars":
        return _lay_bars(it)
    if t == "map":
        return _lay_map(it)
    if t == "story":
        return _lay_story(it)
    if t == "type":
        return _lay_type(it)
    return _lay_hero(it)


def _key(it):
    raw = json.dumps([VERSION, it["kind"], it["id"], it.get("title"), it.get("kicker"), it.get("stats"), it.get("status"), it.get("big"), it.get("rank"), it.get("fact"), it.get("art")], default=str)
    return hashlib.sha1(raw.encode()).hexdigest()


def png_for(kind, ident):
    it = resolve(kind, ident)
    if not it:
        return None
    key = "x" + _key(it)
    return og._cached(key, lambda: og.png_bytes(render(it)))


# ------------------------------------------------------------------ routes
def card_url(it):
    return f"{SITE}/og/x/{it['kind']}/{quote(str(it['id']), safe='~:.-_')}.png?v={_key(it)[:10]}"


_SC = {}   # cid -> (built_at, png, refreshing)


_NEED = set()   # stories whose card was built before their photo was stored (rebuilt once the photo is in)


def invalidate_card_layers(cid):
    """Drop every in-process and leftover-DB cache of this card so a newly persisted PNG is what we serve.
    Layers: in-memory _SC, og._MEM / on-disk og cache keys we can find, and any #221 story_cards row in story_writer.db."""
    if not cid:
        return
    _SC.pop(cid, None)
    try:
        import og
        # Keys are hashes, not cids; drop mem entries and cache files that contain the cid hex in the name or were
        # built for this story by scanning is impractical. Clearing the small in-process PNG mem is enough
        # together with a VERSION bump; also evict any file whose name contains the cid.
        if hasattr(og, "drop_mem"):
            og.drop_mem()
        else:
            try:
                og._MEM.clear()
            except Exception:
                pass
        try:
            d = og.cache_dir()
            if d and d.is_dir():
                needle = str(cid).lower()
                for fp in d.glob("*.png"):
                    if needle in fp.name.lower():
                        try:
                            fp.unlink()
                        except Exception:
                            pass
        except Exception:
            pass
    except Exception:
        pass
    # #221 stored cards in story_writer.db. Serving no longer reads them, but a leftover row must not outlive a downgrade.
    try:
        import os, sqlite3
        import story_writer as SW
        path = (SW.cfg() or {}).get("db") or ""
        if path and os.path.exists(path):
            k = sqlite3.connect(path, timeout=5)
            try:
                names = {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                if "story_cards" in names:
                    k.execute("DELETE FROM story_cards WHERE cid=?", (cid,))
                    k.commit()
            finally:
                k.close()
    except Exception:
        pass


def _register_card_hooks():
    try:
        import story_photo
        if invalidate_card_layers not in getattr(story_photo, "ON_CARD_WRITE", []):
            story_photo.ON_CARD_WRITE.append(invalidate_card_layers)
    except Exception:
        pass


_register_card_hooks()


_GENERIC_BG = None
_GENERIC_BG_READY = False


def _ensure_generic_bg():
    """Build (once) a generic designed world-map background. Safe to call from a daemon thread."""
    global _GENERIC_BG, _GENERIC_BG_READY
    if _GENERIC_BG_READY and _GENERIC_BG is not None:
        return _GENERIC_BG
    try:
        im = _map(W, H, 10.0, 22.0, 150, (214, 218, 226), fx=0.5, marker=False)
        _GENERIC_BG = im
        _GENERIC_BG_READY = True
        return im
    except Exception:
        return None


def _kick_generic_bg():
    try:
        if _GENERIC_BG_READY:
            return
        threading.Thread(target=_ensure_generic_bg, name="card-generic-bg", daemon=True).start()
    except Exception:
        pass


_kick_generic_bg()


def story_map_hit(title="", location="", brief="", cid="", lat=None, lon=None):
    """{place, lat, lon, cc, precision}: the place the Wire map uses for this story (empty place when none).

    A leftover location field is ignored unless the headline names that place. Stored coordinates (lat/lon)
    are only a hint for the Wikidata QID check; the label always comes from the story text."""
    title = title or ""
    loc = (location or "").strip()
    empty = {"place": "", "lat": None, "lon": None, "cc": None, "precision": None}
    try:
        import signal_place as SP
        if loc:
            in_title = loc.lower() in title.lower()
            if not in_title:
                words = [w for w in re.split(r"[^\w]+", loc) if len(w) > 2]
                in_title = any(re.search(r"\b" + re.escape(w) + r"\b", title, re.I) for w in words)
            if not in_title:
                title_ccs = set(SP.named_countries(title) or [])
                loc_ccs = set(SP.named_countries(loc) or [])
                if not (title_ccs and loc_ccs and (title_ccs & loc_ccs)):
                    loc = ""
        story = SP.story_text(title, loc, brief or "")
        title_ccs = list(SP.named_countries(title) or [])
        # "Congo" in outbreak/aid headlines is the DR Congo unless Brazzaville / "Republic of the Congo" is named.
        if "CG" in title_ccs and re.search(r"\bCongo\b", title) and not re.search(r"Republic of (?:the )?Congo|Brazzaville|Congo[- ]Brazzaville", title + " " + (brief or "")):
            title_ccs = ["CD" if c == "CG" else c for c in title_ccs]
            if "CD" in title_ccs:
                cap = SP.capital_of("CD")
                if cap:
                    return {"place": "Democratic Republic of the Congo", "lat": cap.get("lat"), "lon": cap.get("lon"), "cc": "CD", "precision": "country"}
        prefer = title_ccs[0] if len(title_ccs) == 1 else None
        hit = SP.infer(story, prefer_cc=prefer)
        if hit and (hit.get("place") or "").strip():
            hit_cc = (hit.get("cc") or "").upper()
            if title_ccs and hit_cc and hit_cc not in {c.upper() for c in title_ccs}:
                cap = SP.capital_of(title_ccs[0])
                if cap and cap.get("place"):
                    hit = cap
        elif title_ccs:
            hit = SP.capital_of(title_ccs[0])
        else:
            hit = SP.infer(title)
        if not hit or not (hit.get("place") or "").strip():
            return empty
        place = (hit.get("place") or "").strip()
        prec = hit.get("precision")
        if (prec == "country" or hit.get("approximate")) and "," in place:
            place = place.split(",")[-1].strip()
        hlat, hlon = hit.get("lat"), hit.get("lon")
        # The story's own stored coordinate (feed/EONET/USGS) wins when the text-inferred city/region is a
        # same-named place on another continent ("Highland, Virginia" -> Virginia, South Africa).
        cc_out = hit.get("cc")
        if lat is not None and lon is not None and prec != "country" and hlat is not None:
            try:
                import card_photo as _cp
                if _cp._km(float(lat), float(lon), float(hlat), float(hlon)) > 1500:
                    hlat, hlon, cc_out, prec = float(lat), float(lon), None, "region"
            except Exception:
                pass
        return {"place": place, "lat": hlat, "lon": hlon, "cc": cc_out, "precision": prec}
    except Exception:
        pass
    if loc and loc.lower() in title.lower():
        return {"place": loc, "lat": None, "lon": None, "cc": None, "precision": None}
    return empty

def story_map_place(title="", location="", brief="", cid="", lat=None, lon=None):
    """(place label, lat, lon) for the card badge and map; see story_map_hit."""
    h = story_map_hit(title, location, brief, cid, lat, lon)
    return h["place"], h["lat"], h["lon"]


_BAKED = set()
_BAKING = set()
_BAKE_LOCK = threading.Lock()
_BAKE_Q = None  # lazy queue.Queue; a single worker bakes cards one at a time (never one thread per story)


def card_baked(cid):
    """True once a PNG card for this story is stored in cards.db (cached per process). Never raises, no network."""
    if not cid:
        return True
    if cid in _BAKED:
        return True
    try:
        import story_photo
        if story_photo.get_card(cid):
            _BAKED.add(cid)
            return True
    except Exception:
        return True   # fail open: a cards.db problem must not hide the Wire
    return False


def _bake_one(cid):
    """Render and store one designed card (~0.3 s, no network). The photo upgrade is a later, paced worker job."""
    try:
        import story_photo
        if not story_photo.get_card(cid):
            b = generic_story_card(cid)
            if b and b.startswith(b"\x89PNG"):
                title = ""
                try:
                    import story
                    r, _al = story.load(cid)
                    title = (r or {}).get("title") or ""
                except Exception:
                    pass
                story_photo.put_card(cid, b, "", title_hash=story_photo.card_title_key(_card_headline(title) or ""))
        _BAKED.add(cid)
        # Do not submit(fetch=True) here: a flood of Commons downloads is what OOM-killed the 2Gi box
        # after #242 (10:40:19 AM ET). The existing paced photo backfill upgrades the map later.
    except Exception as e:
        print(f"share_card: bake {cid} err={type(e).__name__}", flush=True)
    finally:
        with _BAKE_LOCK:
            _BAKING.discard(cid)


def _bake_worker():
    while True:
        cid = _BAKE_Q.get()
        try:
            if cid:
                _bake_one(cid)
        finally:
            _BAKE_Q.task_done()


def bake_card(cid):
    """Queue a designed card on the single bake worker. Deduped; returns at once. Never starts a new thread per story."""
    global _BAKE_Q
    if not cid or cid in _BAKED:
        return
    with _BAKE_LOCK:
        if cid in _BAKING:
            return
        _BAKING.add(cid)
        if _BAKE_Q is None:
            import queue
            _BAKE_Q = queue.Queue()
            threading.Thread(target=_bake_worker, name="card-bake", daemon=True).start()
        _BAKE_Q.put(cid)


def generic_story_card(cid):
    """A designed 1200x675 card (generic world map + this story's cleaned title). No geocoding, no board rebuild, no network.
    Used on a true cache miss so the Twitterbot path stays under 1s; a unique locator/photo rebuilds in the background."""
    title, rank, loc, cat = "The Wire", 0, "", "THE WIRE"
    try:
        import og as _og
        spec = _og._db_spec(cid) if hasattr(_og, "_db_spec") else None
        if spec:
            title = _card_headline(spec.get("title") or "") or title
            try:
                rank = int(spec.get("rank") or 0)
            except Exception:
                rank = 0
    except Exception:
        pass
    try:
        import story
        r, _al = story.load(cid)
        if r:
            title = _card_headline(r.get("title") or "") or title
            place, _, _ = story_map_place(r.get("title") or "", r.get("location") or "", r.get("brief") or "", cid)
            loc = (place or "")[:40]
            cat = ((r.get("category") or "") or cat).upper()[:36]
            try:
                rank = int(r.get("rank") or rank or 0)
            except Exception:
                pass
    except Exception:
        pass
    col = RED if rank >= 7 else AMBER if rank >= 4 else GREEN
    bg = _ensure_generic_bg()
    if bg is None:
        bg = _base(cid or "generic")
    else:
        bg = bg.copy()
    it = dict(kind="story", id=cid or "generic", title=title, kicker=cat, color=col, rank=rank,
              loc=loc, art=("story", None, None, None), photo=None, fact="", credit="")
    # Paint typography on the cached world map without calling _map again.
    try:
        # Temporarily use the prepared bg via a tiny shim: _lay_story calls _story_bg, which would
        # re-draw a generic _map. Seed the copy into a one-shot monkeypatch-free path.
        im, portrait, credit, label = bg, False, "", ""
        # Reuse _lay_story by stuffing a photo-less item and short-circuiting _story_bg via art without coords —
        # _story_bg already draws the generic map in that case; if _GENERIC_BG is ready, swap after.
        out = _lay_story(it)
        return og.png_bytes(out)
    except Exception:
        try:
            return og.png_bytes(bg if hasattr(bg, "size") else _base(cid or "generic"))
        except Exception:
            return None


def card_photo_on():
    """Licensed person/place/topic photo cards (Matt 10:27 AM ET). BN_CARD_PHOTO=0 turns them off."""
    try:
        import card_photo as CP
        return CP.enabled()
    except Exception:
        return False


_US_WORDS = re.compile(r"\b(u\.?s\.?a?|united states|(?<!central )(?<!south )(?<!latin )america\\b|americans\\b|washington|pentagon|white house|congress|federal|fbi|cdc|noaa|fema|usgs|nasa|wall street)\b", re.I)


def apply_card_photo(cid, title="", loc="", brief="", lat=None, lon=None, category=""):
    """Network: choose a v3 licensed photo, store it, return the photo dict (or None). No-op when the flag is off."""
    if not cid or not card_photo_on():
        return None
    try:
        import card_photo as CP, story_photo as SP
        hit = story_map_hit(title or "", loc or "", brief or "", cid, lat, lon)
        # signal_place falls back to Washington / "United States" when it finds no place; do not show the National Mall
        # on a Nicaragua volcano. A country-level US hit needs a US word in the story, else use the topic photo.
        if hit and hit.get("cc") == "US" and hit.get("precision") == "country" and not _US_WORDS.search((title or "") + " " + (brief or "")):
            hit = None
        im = CP.choose(cid, title or "", hit, brief or "", category or "")
        if not im:
            return None
        jpg = None
        try:
            path = im.get("path")
            if path:
                sz = Path(path).stat().st_size
                # v3 source thumbs are well under this; never hold a huge file in RAM
                if 4000 <= sz <= 6 * 1024 * 1024:
                    jpg = Path(path).read_bytes()
        except Exception:
            jpg = None
        try:
            SP.db_put(cid, im, jpg=jpg)
        finally:
            jpg = None
        return im
    except Exception as e:
        print(f"share_card: apply_card_photo {cid} err={type(e).__name__}", flush=True)
        return None


def _network_prefetch(cid):
    """Commons / HTTP lookup only (no card render). Used by the photo worker so a 10s
    network timeout cannot fire after a successful photo=1 while typography is still being laid out."""
    import story_photo
    it = _story_item(cid)
    if it and it[0]:
        r = it[0]
        title = r.get("title") or ""
        loc = r.get("location") or ""
        brief = r.get("brief") or ""
        if card_photo_on():
            apply_card_photo(cid, title, loc, brief, r.get("lat"), r.get("lon"), r.get("category") or "")
        # Always run the existing Commons prefetch too: it is how a PEOPLE-list
        # portrait lands when the v3 chooser misses, and tests mock _commons_portrait.
        story_photo.prefetch(cid, title, loc, brief)


def _story_build(cid, fetch=False):
    """fetch=True (background warm, refresh, write-up gate) may download the story's photo; the crawler path (fetch=False) never touches the network."""
    try:
        try:
            # Rehydrate a stored JPEG onto disk so a VERSION rebuild can reuse it (no network).
            import story_photo
            c = story_photo.db_choice(cid)
            if c and not c.get("none") and c.get("src"):
                story_photo.cached(c["src"])
        except Exception:
            pass
        if fetch:
            try:
                _network_prefetch(cid)
            except Exception:
                pass
            _NEED.discard(cid)
        b = png_for("story", cid)
        if b:
            try:
                import story_photo
                it = None
                try:
                    it = resolve("story", cid)
                except Exception:
                    it = None
                src = ""
                if it and it.get("photo"):
                    src = (it["photo"] or {}).get("src") or ""
                if not src:
                    try:
                        if story_photo.has_photo(cid):
                            # A stored JPEG must be on the card; do not persist a map over it.
                            src = (story_photo.db_choice(cid) or {}).get("src") or ""
                    except Exception:
                        pass
                pending = bool(it and it.get("photo_pending"))
                th = ""
                try:
                    th = story_photo.card_title_key((it or {}).get("title") or "")
                except Exception:
                    th = ""
                # put_card itself refuses to replace a correctly matched photo with a map,
                # and allows the one exception: a wrong-subject / non-matching photo may be
                # downgraded to the designed map. fetch=False typography must also persist.
                if not pending:
                    story_photo.put_card(cid, b, src, title_hash=th)
                if not fetch and not src.startswith("https://"):
                    if _r_story_pending(cid):
                        _NEED.add(cid)
            except Exception:
                pass
            _SC[cid] = (time.time(), b, False)
        return b
    finally:
        time.sleep(0.2)  # yield the only CPU so new TLS/HTTP connections can be accepted


def _r_story_pending(cid):
    try:
        it = resolve("story", cid)
        return bool(it and it.get("photo_pending"))
    except Exception:
        return False


def story_png(cid):
    """Unique 1200x675 card for a Wire story (used by og.png_for_story, so /wire/<id> shares get it). None if the story is unknown.
    Resolving a story reads the live board (api_state), which can take tens of seconds when its cache is stale, so a built card is
    served from memory at once and refreshed in the background after 10 minutes. warm() builds it ahead of the first crawl."""
    hit = _SC.get(cid)
    if hit:
        if time.time() - hit[0] > 600 and not hit[2]:
            _SC[cid] = (hit[0], hit[1], True)
            import threading
            threading.Thread(target=lambda: _story_refresh(cid), name="story-card", daemon=True).start()
        return hit[1]
    try:
        import story_photo
        b = story_photo.get_card(cid)
        if b:
            _SC[cid] = (time.time(), b, False)
            if not story_photo.resolved(cid):
                import threading
                threading.Thread(target=lambda: _story_refresh(cid), name="story-card", daemon=True).start()
            return b
    except Exception:
        pass
    return _story_build(cid, fetch=True)


def _story_refresh(cid):
    try:
        _story_build(cid, fetch=True)
    except Exception:
        h = _SC.get(cid)
        if h:
            _SC[cid] = (time.time() - 300, h[1], False)


_POOL = None
_INFLIGHT = {}
_FINFLIGHT = {}
_FLOCK = threading.Lock()
_FHIGH = []          # urgent cids, index 0 is next (newest first: insert at 0)
_FLOW = []           # backfill cids, FIFO
_FWAIT = {}          # cid -> Future
_FSKIP_NET = set()   # typography-only jobs: skip Commons prefetch (local JPEG + current title)
_FWAKE = threading.Event()
_FWORKER = None
_FSEQ = 0


def _pool():
    global _POOL
    if _POOL is None:
        from concurrent.futures import ThreadPoolExecutor
        _POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="story-card")
    return _POOL


def _entity_story(cid, title=None):
    """True when the headline names a person or a quoted/aliased landmark. Cheap (DB/title only, no network)."""
    if not title:
        try:
            got = _story_item(cid)
            title = ((got[0] if got else {}) or {}).get("title") or ""
        except Exception:
            title = ""
    try:
        import story_photo
        if story_photo._named_people(cid, title, ""):
            return True
        if story_photo.landmark_in(title):
            return True
    except Exception:
        pass
    return False


LOOKUP_TIMEOUT = 10  # network-only; typography render is not inside this window
_LAST_PREFETCH = ""
_FRUNNING = None
_WORKER_LOGGED = False


_FWORKER_PID = None


def photo_status():
    """Heartbeat for /healthz: queue depth, last prefetch time, whether the worker thread is alive.
    Starts (or restarts) the worker in this process so a request/healthz path never depends on a pre-fork start."""
    try:
        _ensure_fworker()
    except Exception:
        pass
    with _FLOCK:
        depth = len(_FHIGH) + len(_FLOW)
        running = _FRUNNING
        last = _LAST_PREFETCH
        alive = bool(_FWORKER and _FWORKER.is_alive() and _FWORKER_PID == os.getpid())
    photos = cards = photo_cards = 0
    try:
        import story_photo
        got = story_photo.store_counts()
        if got:
            photos, cards, photo_cards = got
    except Exception:
        pass
    audit = {}
    try:
        import story_photo
        audit = dict(story_photo.AUDIT)
    except Exception:
        audit = {}
    rebuild = {}
    try:
        import story_photo
        rebuild = dict(story_photo.REBUILD)
    except Exception:
        rebuild = {}
    debug = []
    try:
        import story_photo
        debug = story_photo.photo_row_debug()
    except Exception:
        debug = []
    deleted_cids = list(audit.get("deleted_cids") or [])
    return {"depth": depth + (1 if running else 0), "last": last, "worker": alive, "inflight": running or "",
            "pid": os.getpid(), "photos": photos, "cards": cards, "photo_cards": photo_cards,
            "audit_checked": int(audit.get("checked") or 0),
            "audit_deleted": int(audit.get("deleted") or 0),
            "audit_deleted_cids": deleted_cids,
            "audit_downgraded": int(audit.get("deleted") or audit.get("downgraded") or 0),
            "audit_typography": int(audit.get("typography") or 0),
            "audit_done": bool(audit.get("done")),
            "rebuild_done": bool(rebuild.get("done")),
            "rebuild_ids": int(rebuild.get("ids") or 0),
            "photo_debug": debug}


def _mark_prefetch(cid, note=""):
    global _LAST_PREFETCH
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _LAST_PREFETCH = f"{ts} {cid}" + (f" {note}" if note else "")


def _ensure_fworker():
    """Start (or restart) the photo worker in *this* process.

    Must be lazy and PID-checked: a thread started in a parent process does not
    survive fork, and render_app.py's web-only Thread.start guard silently
    refuses targets whose name contains "loop" (the #228/#229 `_floop` bug:
    "worker started" logged after start() but the target never ran).
    """
    global _FWORKER, _FWORKER_PID, _WORKER_LOGGED
    pid = os.getpid()
    if _FWORKER is not None and _FWORKER.is_alive() and _FWORKER_PID == pid:
        return True
    # Target name must not contain "loop"/"harvest"/"indexer" (render_app thread guard).
    _FWORKER = threading.Thread(target=_photo_jobs, name="story-photo", daemon=True)
    _FWORKER.start()
    _FWORKER_PID = pid
    if _FWORKER.is_alive():
        if not _WORKER_LOGGED:
            print(f"story_photo: worker started pid={pid}", flush=True)
            _WORKER_LOGGED = True
        try:
            _ensure_convert()
        except Exception:
            pass
        return True
    print(f"story_photo: worker failed to start pid={pid} (thread guard?)", flush=True)
    return False


def _run_lookup(cid, fut):
    """Run one fetch=True build; always record a last-prefetch heartbeat."""
    try:
        print(f"story_photo: lookup start {cid}", flush=True)
        b = _story_build(cid, True)
        _mark_prefetch(cid, "ok")
        if not fut.done():
            fut.set_result(b)
    except Exception as e:
        _mark_prefetch(cid, type(e).__name__)
        print(f"story_photo: lookup {cid} err={type(e).__name__}", flush=True)
        if not fut.done():
            try:
                fut.set_exception(e)
            except Exception:
                pass


def _photo_jobs():
    global _FRUNNING
    print(f"story_photo: worker running pid={os.getpid()}", flush=True)
    while True:
        cid = fut = None
        with _FLOCK:
            if _FHIGH:
                cid = _FHIGH.pop(0)
            elif _FLOW:
                cid = _FLOW.pop(0)
            if cid:
                fut = _FWAIT.pop(cid, None)
        if not cid or fut is None:
            _FWAKE.wait(timeout=0.4)
            _FWAKE.clear()
            continue
        _FINFLIGHT[cid] = fut
        _FRUNNING = cid
        try:
            # Timeout covers only the network prefetch. Card render is local (stored JPEG)
            # and must not be inside the join: a photo=1 at ~10s was logging timeout at 15s
            # while typography was still running.
            # Typography-only jobs (stale title hash / VERSION) skip the network and re-render
            # from the stored JPEG with the current cleaned title. The old _pool() path could hang
            # behind other typography work (max_workers=1) and never replace Zelensky's dashed PNG.
            skip_net = False
            with _FLOCK:
                skip_net = cid in _FSKIP_NET
                _FSKIP_NET.discard(cid)
            box = {"done": True, "err": None}
            th = None
            if not skip_net:
                box = {"done": False, "err": None}
                def _prefetch_job(c=cid, b=box):
                    try:
                        _network_prefetch(c)
                    except Exception as e:
                        b["err"] = e
                    finally:
                        b["done"] = True
                th = threading.Thread(target=_prefetch_job, daemon=True, name=f"photo-{cid[:8]}")
                th.start()
                th.join(LOOKUP_TIMEOUT)
                if th.is_alive() and not box["done"]:
                    _mark_prefetch(cid, "timeout")
                    print(f"story_photo: prefetch {cid} photo=0 err=timeout {LOOKUP_TIMEOUT}s", flush=True)
            # Render from whatever is stored now (reuse a JPEG if prefetch finished).
            try:
                b = _story_build(cid, False)
            except Exception as e:
                b = None
                if not fut.done():
                    try:
                        fut.set_exception(e)
                    except Exception:
                        pass
            else:
                _mark_prefetch(cid, "ok" if box["done"] else "timeout")
                if not fut.done():
                    fut.set_result(b)
            # If prefetch is still running, let it finish and rebuild typography from the JPEG.
            if th is not None and th.is_alive():
                def _after_prefetch(c=cid, thread=th):
                    thread.join(30)
                    try:
                        _story_build(c, False)
                    except Exception:
                        pass
                threading.Thread(target=_after_prefetch, daemon=True, name=f"photo-late-{cid[:8]}").start()
        finally:
            _FINFLIGHT.pop(cid, None)
            _FRUNNING = None


def submit(cid, fetch=False, urgent=False):
    """Start (or join) the build of a story's card. Both typography (fetch=False) and photo
    lookups (fetch=True) use the photo worker — typography used to go through a 1-thread
    _pool() that could hang and never rewrite a stale title. urgent=True (hit-triggered,
    new publish) jumps the backfill and is newest-first. Backfill must pass urgent=False
    and is never auto-promoted onto the request queue."""
    from concurrent.futures import Future
    _ensure_fworker()
    with _FLOCK:
        if fetch:
            _FSKIP_NET.discard(cid)
        else:
            # A later fetch=True for the same cid clears this so a portrait lookup still runs.
            if cid not in _FINFLIGHT and cid not in _FWAIT:
                _FSKIP_NET.add(cid)
        run = _FINFLIGHT.get(cid)
        if run is not None and not run.done():
            return run
        wait = _FWAIT.get(cid)
        if wait is not None and not wait.done():
            if urgent:
                if cid in _FLOW:
                    _FLOW.remove(cid)
                if cid in _FHIGH:
                    _FHIGH.remove(cid)
                _FHIGH.insert(0, cid)
            return wait
        fut = Future()
        _FWAIT[cid] = fut
        if urgent:
            _FHIGH.insert(0, cid)
        else:
            _FLOW.append(cid)
        _FWAKE.set()
        return fut



def _queue_card_work(cid):
    """Queue background work for this story: typography rebuild from a stored JPEG, and/or a photo lookup.
    Requested ids are urgent (newest first) so they jump the backfill. Never blocks."""
    try:
        _ensure_fworker()
        import story_photo
        has_jpg = bool(story_photo.has_photo(cid))
        has_pcard = bool(story_photo.card_has_photo(cid))
        meta = story_photo.card_meta(cid)
        current_key = ""
        try:
            import story
            r, _al = story.load(cid)
            if r:
                current_key = story_photo.card_title_key(_card_headline(r.get("title") or "") or "")
        except Exception:
            current_key = ""
        stale = bool(meta and story_photo.card_stale(meta))
        if meta and story_photo.card_title_stale(meta, current_key):
            stale = True
        if meta and current_key:
            try:
                raw_title = ""
                import story as _st
                r, _al = _st.load(cid)
                if r:
                    raw_title = r.get("title") or ""
                head = _card_headline(raw_title) or raw_title
                if story_photo.card_font_stale(meta, head) or card_needs_headline_refit(meta, head):
                    stale = True
            except Exception:
                pass
        if not meta:
            stale = False
        if stale or (has_jpg and not has_pcard):
            # Re-render from the stored JPEG with the current cleaned title (photo worker, no network).
            submit(cid, fetch=False, urgent=True)
        if not has_pcard and not has_jpg:
            submit(cid, fetch=True, urgent=True)
    except Exception:
        pass


def ensure_current_card(cid):
    """Return the best stored card immediately. Always re-reads cards.db so an audit/downgrade
    is not hidden by a stale in-memory _SC (or a leftover #221 writer-db row we no longer serve).
    Typography/VERSION or photo rebuilds are queued in the background. Never blocks the request path.
    When photo cards are on and a licensed JPEG is already stored, a leftover map is re-rendered
    into the v3 photo card now (no network) instead of being served."""
    stored = None
    meta = None
    try:
        import story_photo
        meta = story_photo.card_meta(cid)
        if meta and meta.get("png"):
            stored = meta["png"]
            _SC[cid] = (time.time(), stored, False)
    except Exception:
        stored = None
        meta = None
    if stored is None:
        hit = _SC.get(cid)
        if hit and hit[1]:
            stored = hit[1]
    try:
        import story_photo
        is_map = not (meta and (meta.get("src") or "").startswith("https://"))
        if stored and is_map and card_photo_on() and story_photo.has_photo(cid):
            b = render_story_fresh(cid)
            if b and b.startswith(b"\x89PNG") and len(b) > 2000:
                src = ((story_photo.db_choice(cid) or {}).get("src") or "")
                if src.startswith("https://"):
                    th = ""
                    try:
                        it = resolve("story", cid)
                        th = story_photo.card_title_key((it or {}).get("title") or "")
                    except Exception:
                        th = ""
                    story_photo.put_card(cid, b, src, title_hash=th)
                    invalidate_card_layers(cid)
                    _SC[cid] = (time.time(), b, False)
                    stored = b
    except Exception:
        pass
    try:
        _queue_card_work(cid)
    except Exception:
        pass
    return stored


def story_png_fast(cid, budget=1.0):
    """Serve the best stored card immediately (never block the Twitterbot path over 2s).
    Typography/VERSION and photo rebuilds run in the background and replace the stored card when done.
    On a true cold miss, serve a generic designed 1200x675 card in under 1s and rebuild the unique
    locator/photo in the background. Never the 1200x630 earth fallback."""
    try:
        cur = ensure_current_card(cid)
        if cur:
            return cur
    except Exception:
        pass
    try:
        b = generic_story_card(cid)
        if b and b.startswith(b"\x89PNG") and len(b) > 2000:
            _SC[cid] = (time.time(), b, False)
            try:
                submit(cid, fetch=True, urgent=True)
            except Exception:
                pass
            return b
    except Exception:
        pass
    # Last resort still under the budget: do not call the slow unique _map render on this path.
    try:
        submit(cid, fetch=True, urgent=True)
    except Exception:
        pass
    return None



def story_png_map_now(cid):
    """Return a stored card at once, or build a designed 1200x675 map synchronously (no network) on a cold miss
    so the 1200x630 earth fallback is never served for a known story. Rebuilds and photo lookups are background."""
    try:
        cur = ensure_current_card(cid)
        if cur:
            return cur
    except Exception:
        pass
    try:
        b = generic_story_card(cid)
        if b and b.startswith(b"\x89PNG") and len(b) > 2000:
            _SC[cid] = (time.time(), b, False)
    except Exception:
        b = None
    try:
        submit(cid, fetch=True, urgent=True)
    except Exception:
        pass
    return b



def story_png_publish(cid, wait=12):
    """High-priority photo lookup for a new story, waited so the photo card can exist before the write-up publishes.
    If the lookup does not finish in `wait` seconds, return the designed map card (never the earth fallback)."""
    try:
        import story_photo
        if story_photo.card_has_photo(cid):
            b = story_photo.get_card(cid)
            if b:
                _SC[cid] = (time.time(), b, False)
                return b
    except Exception:
        pass
    try:
        fut = submit(cid, fetch=True, urgent=True)
        try:
            fut.result(timeout=max(1.0, float(wait)))
        except Exception:
            pass
    except Exception:
        pass
    hit = _SC.get(cid)
    if hit and hit[1]:
        return hit[1]
    try:
        import story_photo
        b = story_photo.get_card(cid)
        if b:
            _SC[cid] = (time.time(), b, False)
            return b
    except Exception:
        pass
    return story_png_map_now(cid)


def boot_warm_cards(cids, timeout=40):
    """Synchronously build designed (map) cards for cids, then run photo lookups until timeout.
    Called from render_app._boot_warm before healthz reports og=true."""
    t0 = time.time()
    n = 0
    seen = []
    for cid in cids or []:
        if not cid or cid in seen:
            continue
        seen.append(cid)
        if time.time() - t0 > max(8, timeout - 12):
            break
        try:
            if story_png_map_now(cid):
                n += 1
        except Exception:
            pass
    # Photo pass: fetch=True on the photo pool; wait out the remaining budget so people/landmark
    # stories can land a photo card before the instance takes public traffic.
    futs = []
    for cid in seen:
        if time.time() - t0 > timeout:
            break
        try:
            futs.append(submit(cid, fetch=True, urgent=True))
        except Exception:
            pass
    remain = timeout - (time.time() - t0)
    for f in futs:
        left = timeout - (time.time() - t0)
        if left <= 0:
            break
        try:
            f.result(timeout=min(left, 12))
        except Exception:
            pass
    return n



_AUDIT_FIRST = ("cbdfb48145e55048", "9f5bc9d66d783d25", "4c292ccdd9df73f8")


def audit_stored_photo_cards():
    """Walk every stored photo (story_photos and photo cards). Re-check the Commons file title
    against the headline under photo_rule_allows. DELETE non-matching rows outright (not a
    map downgrade) so the card rebuilds as a map and the photo worker cannot put the JPEG back.
    Log every cid deleted. Typography-rebuild a matching photo when the title hash is stale.
    """
    import story_photo as SP
    SP.AUDIT.update(checked=0, deleted=0, downgraded=0, typography=0, done=False, error="", deleted_cids=[])
    cids = list(dict.fromkeys(list(SP.stored_photo_cids()) + list(SP.photo_cids())))
    first = [c for c in _AUDIT_FIRST if c in cids]
    rest = [c for c in cids if c not in first]
    # Gaza meningitis (live miss) first among the rest if present.
    extra = [c for c in SP.WATCH_CIDS if c in rest]
    rest = extra + [c for c in rest if c not in extra]
    print(f"story_photo: audit starting {len(cids)} stored photo rows", flush=True)

    def _audit_one(cid, force=False):
        invalidate_card_layers(cid)
        title, text = "", ""
        try:
            title, text, _loc = _force_title(cid)
        except Exception:
            title, text = "", ""
        if title:
            SP.SUBJECT_HINTS.setdefault(cid, (title, text or ""))
        c = SP.db_choice(cid) or {}
        meta = SP.card_meta(cid) or {}
        src = (meta.get("src") or c.get("src") or "")
        ft = SP.commons_file_title(src=src, link=c.get("link") or "", title=c.get("title") or "")
        match = SP.stored_photo_matches(cid) if (title or src) else False
        if not title and not force:
            # Still try to delete if we have a photo src that is not a ShakeMap — cannot confirm a person match.
            if src.startswith("https://") and not SP.official_event_src(cid, src):
                match = False
            else:
                return "retry"
        if match is not True:
            ok = SP.delete_stored_photo(cid)
            invalidate_card_layers(cid)
            SP.AUDIT["deleted"] += 1
            SP.AUDIT["deleted_cids"].append(cid)
            print(f"story_photo: deleted {cid} commons_title={ft!r} src={src} reason=no_match ok={ok}", flush=True)
            return "deleted"
        # Matching photo: typography-rebuild when the stored title hash is stale or missing.
        current_key = ""
        try:
            current_key = SP.card_title_key(_card_headline(title or "") or "")
        except Exception:
            current_key = ""
        if meta and (SP.card_title_stale(meta, current_key) or SP.card_stale(meta) or force):
            _story_build(cid, False)
            invalidate_card_layers(cid)
            SP.AUDIT["typography"] += 1
            print(f"story_photo: typography {cid} hash={current_key}", flush=True)
            return "typography"
        return "ok"

    retry = []
    for cid in first + rest:
        try:
            SP.AUDIT["checked"] += 1
            got = _audit_one(cid, force=False)
            if got == "retry":
                retry.append(cid)
        except Exception as e:
            SP.AUDIT["error"] = type(e).__name__
            print(f"story_photo: audit {cid} err={type(e).__name__}", flush=True)
            retry.append(cid)
    for cid in list(dict.fromkeys(list(first) + retry)):
        try:
            _audit_one(cid, force=True)
        except Exception as e:
            SP.AUDIT["error"] = type(e).__name__
            print(f"story_photo: audit retry {cid} err={type(e).__name__}", flush=True)
    SP.AUDIT["done"] = True
    print(f"story_photo: audit deleted {SP.AUDIT['deleted']} of {SP.AUDIT['checked']} photo rows (typography {SP.AUDIT['typography']}): {','.join(SP.AUDIT['deleted_cids'])}", flush=True)
    return SP.AUDIT["deleted"]



# Last-known headlines for the one-shot listed-id rebuild if story.load is not ready at boot.
_FORCE_TITLES = {
    "cbdfb48145e55048": ("Trump wanted Jensen Huang back as the CEO of Nvidia", "", "Pennsylvania"),
    "9f5bc9d66d783d25": ("Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine", "", "Ukraine"),
    "4c292ccdd9df73f8": ("Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel", "", "Libya"),
    "b06344259ebf4d01": ("Gaza's Health Ministry has declared an epidemic alert across the territory over a rapid rise in meningitis", "", "Gaza"),
}


def _force_title(cid):
    """Title, body, location for a listed-id rebuild. SUBJECT_HINTS, then story.load, then the baked-in headline."""
    try:
        import story_photo as SP
        if cid and cid in SP.SUBJECT_HINTS:
            t, x = SP.SUBJECT_HINTS[cid]
            loc = (_FORCE_TITLES.get(cid) or ("", "", ""))[2]
            return t or "", x or "", loc
    except Exception:
        pass
    try:
        import story
        r, _al = story.load(cid)
        if r:
            body = (r.get("brief") or "") + " " + (r.get("writeup") or r.get("body") or "")
            return r.get("title") or "", body, r.get("location") or ""
    except Exception:
        pass
    return _FORCE_TITLES.get(cid) or ("", "", "")


def render_story_fresh(cid):
    """Render this story's card now, bypassing the og mem/disk cache so typography is current."""
    it = resolve("story", cid)
    if not it:
        return None
    try:
        return og.png_bytes(render(it))
    except Exception:
        return None

def rebuild_card_places(budget=25):
    """Re-render stored map cards so the badge and map use the Wire-map location, not leftover loc."""
    import story_photo as SP
    t0 = time.time()
    n = 0
    cids = list(dict.fromkeys(list(SP.WATCH_CIDS) + list(SP.card_cids(400))))
    watch = set(SP.WATCH_CIDS)
    for cid in cids:
        if time.time() - t0 > float(budget) and cid not in watch and n >= 4:
            break
        try:
            # Keep a matching portrait; everything else is a map that may have a stale badge.
            if SP.card_has_photo(cid) and SP.stored_photo_matches(cid) is True:
                continue
            invalidate_card_layers(cid)
            title, _text, _loc = _force_title(cid)
            th = SP.card_title_key(_card_headline(title or "") or "")
            b = generic_story_card(cid) or render_story_fresh(cid)
            if b and b.startswith(b"\x89PNG"):
                SP.put_card(cid, b, "", title_hash=th, allow_downgrade=True)
                invalidate_card_layers(cid)
                n += 1
        except Exception as e:
            print(f"story_photo: place-rebuild {cid} err={type(e).__name__}", flush=True)
    print(f"story_photo: place-rebuild {n} map cards in {time.time()-t0:.1f}s", flush=True)
    return n


PHOTO_REBUILD = {"done": False, "ids": 0, "error": "", "queued": 0}
_REBUILD_LOCK = threading.Lock()
# Encoded v3 photo cards are 0.6–1.2 MB. Anything larger is not stored or kept in RAM.
_REBUILD_PNG_CAP = 2 * 1024 * 1024

# Persistent one-at-a-time convert of leftover map cards + Latin-ext typography.
# Survives a boot pass that finished before blackout.db / cards.db arrived.
# Target name must not contain "loop" (render_app thread guard).
CONVERT = {"done": False, "ids": 0, "error": "", "queued": 0, "left": 0}
_CONVERT = None
_CONVERT_PID = None
_CONVERT_SLEEP = 0.2


def _ensure_convert():
    """Start (or restart) the stale-map convert worker in this process."""
    global _CONVERT, _CONVERT_PID
    pid = os.getpid()
    if _CONVERT is not None and _CONVERT.is_alive() and _CONVERT_PID == pid:
        return True
    _CONVERT = threading.Thread(target=_stale_map_jobs, name="card-convert", daemon=True)
    _CONVERT.start()
    _CONVERT_PID = pid
    if _CONVERT.is_alive():
        print(f"share_card: convert worker started pid={pid}", flush=True)
        return True
    print(f"share_card: convert worker failed to start pid={pid} (thread guard?)", flush=True)
    return False


_CONVERT_TRIED = {}      # cid -> time of the last attempt; a card that found no photo is retried after _RETRY_S
_RETRY_S = 1800


def _pending_convert_cids(limit=3000):
    """Leftover maps and previous-VERSION cards first; then non-ASCII / clipped headlines still on old typography.
    Uses card_heads() so a scan never loads PNG bytes into RAM. A card tried within _RETRY_S is skipped, so one
    story with no photo can never block the rest of the queue."""
    import story_photo as SP
    now = time.time()
    seen, order, rest = set(), [], []
    try:
        rows = SP.card_heads(limit) or []
    except Exception:
        rows = []
    for row in rows:
        cid = row.get("cid") or ""
        if not cid or cid in seen:
            continue
        seen.add(cid)
        if now - _CONVERT_TRIED.get(cid, 0) < _RETRY_S:
            continue
        if SP.card_stale(row):
            order.append(cid)
        else:
            rest.append(row)
    if order:
        return order
    for row in rest[:400]:   # newest first; the font/headline pass only runs when no map is waiting
        cid = row.get("cid") or ""
        title = ""
        try:
            title, _text, _loc = _force_title(cid)
            title = _card_headline(title or "") or title
        except Exception:
            title = ""
        if SP.card_font_stale(row, title) or card_needs_headline_refit(row, title):
            order.append(cid)
    return order


def _convert_one_stale(cid):
    """Re-render one stale card. Uses a stored JPEG when present (no network)."""
    import gc
    import story_photo as SP
    b = None
    try:
        title, text, loc = _force_title(cid)
        lat = lon = None
        cat = ""
        try:
            import story
            r, _al = story.load(cid)
            if r:
                title = r.get("title") or title
                loc = r.get("location") or loc
                text = r.get("brief") or text
                lat, lon = r.get("lat"), r.get("lon")
                cat = r.get("category") or ""
        except Exception:
            pass
        has_jpg = False
        try:
            has_jpg = bool(SP.has_photo(cid))
        except Exception:
            has_jpg = False
        # Relief / satellite place photos, and place photos on hazard/outbreak stories, must be dropped and re-chosen.
        try:
            ch = SP.db_choice(cid) or {}
            drop = bool(ch and SP.is_non_photo_candidate(ch))
            if not drop and ch and (ch.get("kind") or "") == "place":
                try:
                    import card_photo as CP
                    drop = CP.skip_place_photo(title, text, cat)
                except Exception:
                    drop = False
            if drop:
                SP.delete_stored_photo(cid)
                has_jpg = False
        except Exception:
            pass
        if not has_jpg and card_photo_on():
            apply_card_photo(cid, title or "", loc or "", text or "", lat, lon, cat)
        invalidate_card_layers(cid)
        th = SP.card_title_key(_card_headline(title or "") or "")
        b = render_story_fresh(cid) or generic_story_card(cid)
        src = ""
        try:
            if SP.has_photo(cid):
                src = (SP.db_choice(cid) or {}).get("src") or ""
        except Exception:
            src = ""
        if not src.startswith("https://"):
            try:
                c = SP.pick(cid, title or "", loc or "", text or "")
                if c and (c.get("src") or "").startswith("https://"):
                    src = c.get("src") or ""
            except Exception:
                pass
        if b and len(b) > _REBUILD_PNG_CAP:
            print(f"share_card: convert {cid} skip oversized png {len(b)}", flush=True)
            b = None
        if b and b.startswith(b"\x89PNG"):
            SP.put_card(cid, b, src, title_hash=th, allow_downgrade=True)
            return True
        return False
    except Exception as e:
        CONVERT["error"] = type(e).__name__
        print(f"share_card: convert {cid} err={type(e).__name__}", flush=True)
        return False
    finally:
        b = None
        _SC.pop(cid, None)
        try:
            invalidate_card_layers(cid)
        except Exception:
            pass
        gc.collect()


def _stale_map_jobs():
    """Drain leftover map cards and Latin-ext typography, one at a time, after data arrives."""
    print(f"share_card: convert worker running pid={os.getpid()}", flush=True)
    idle = 0
    while True:
        try:
            cids = _pending_convert_cids()
            CONVERT["queued"] = len(cids)
            CONVERT["left"] = len(cids)
            if not cids:
                CONVERT["done"] = True
                idle += 1
                # Data often arrives after handoff gives up; keep scanning, then back off.
                time.sleep(15 if idle < 8 else 45)
                continue
            CONVERT["done"] = False
            idle = 0
            _CONVERT_TRIED[cids[0]] = time.time()
            ok = _convert_one_stale(cids[0])
            if ok:
                CONVERT["ids"] += 1
            CONVERT["left"] = max(0, len(cids) - 1)
            time.sleep(float(_CONVERT_SLEEP))
        except Exception as e:
            CONVERT["error"] = type(e).__name__
            print(f"share_card: convert worker err={type(e).__name__}", flush=True)
            time.sleep(2.0)


def rebuild_card_photos(cids=None, pause=0.4, budget=0):
    """Single paced background worker, newest first: licensed v3 photo cards.

    One story at a time on this thread — never one thread per story. After each
    card the PNG bytes (0.6–1.2 MB) are written to cards.db and then dropped,
    and the in-process `_SC` entry is evicted, so a 400–800 card run cannot
    accumulate enough RAM to OOM the 2 Gi instance. Does not block healthz.
    pause spaces lookups so the 1-CPU box stays responsive. budget=0 means
    no time cap (the boot thread runs this after og=true). A second caller
    is a no-op while a rebuild is already running.
    """
    import gc
    import story_photo as SP
    if not _REBUILD_LOCK.acquire(blocking=False):
        return PHOTO_REBUILD
    try:
        PHOTO_REBUILD.update(done=False, ids=0, error="", queued=0)
        if not card_photo_on():
            PHOTO_REBUILD["done"] = True
            return PHOTO_REBUILD
        seen, order = set(), []
        for cid in cids or []:
            if cid and cid not in seen:
                seen.add(cid); order.append(cid)
        t0 = time.time()
        PHOTO_REBUILD["queued"] = len(order)
        for cid in order:
            if budget and time.time() - t0 > float(budget):
                break
            b = None
            try:
                title, text, loc = _force_title(cid)
                lat = lon = None
                cat = ""
                try:
                    import story
                    r, _al = story.load(cid)
                    if r:
                        title = r.get("title") or title
                        loc = r.get("location") or loc
                        text = r.get("brief") or text
                        lat, lon = r.get("lat"), r.get("lon")
                        cat = r.get("category") or ""
                except Exception:
                    pass
                has_jpg = False
                try:
                    has_jpg = bool(SP.has_photo(cid))
                except Exception:
                    has_jpg = False
                if not has_jpg:
                    apply_card_photo(cid, title or "", loc or "", text or "", lat, lon, cat)
                invalidate_card_layers(cid)
                th = SP.card_title_key(_card_headline(title or "") or "")
                b = render_story_fresh(cid) or generic_story_card(cid)
                src = ""
                try:
                    c = SP.pick(cid, title or "", loc or "", text or "")
                    if c and (c.get("src") or "").startswith("https://"):
                        src = c.get("src") or ""
                except Exception:
                    src = ""
                if not src.startswith("https://"):
                    try:
                        d = SP.db_choice(cid) or {}
                        if (d.get("src") or "").startswith("https://") and not d.get("none"):
                            src = d.get("src") or ""
                    except Exception:
                        pass
                if b and len(b) > _REBUILD_PNG_CAP:
                    print(f"share_card: photo-rebuild {cid} skip oversized png {len(b)}", flush=True)
                    b = None
                if b and b.startswith(b"\x89PNG"):
                    SP.put_card(cid, b, src, title_hash=th, allow_downgrade=True)
                    PHOTO_REBUILD["ids"] += 1
            except Exception as e:
                PHOTO_REBUILD["error"] = type(e).__name__
                print(f"share_card: photo-rebuild {cid} err={type(e).__name__}", flush=True)
            finally:
                b = None
                # Evict the in-process PNG cache for this cid so a long run
                # cannot hold hundreds of 0.6–1.2 MB cards in RAM.
                _SC.pop(cid, None)
                try:
                    invalidate_card_layers(cid)
                except Exception:
                    pass
            if PHOTO_REBUILD["ids"] and PHOTO_REBUILD["ids"] % 8 == 0:
                gc.collect()
            if pause:
                time.sleep(float(pause))
        PHOTO_REBUILD["done"] = True
        gc.collect()
        print(f"share_card: photo-rebuild {PHOTO_REBUILD['ids']}/{PHOTO_REBUILD['queued']} in {time.time()-t0:.1f}s", flush=True)
        return PHOTO_REBUILD
    finally:
        _REBUILD_LOCK.release()


# NZ quake + Iceland: stored place photos were NASA relief / ESA satellite country views.
MAPLIKE_PLACE_CARDS = ("d9c1418515395db1", "dcd0416e4a66964e")
MAPLIKE_REBUILD = {"done": False, "ids": 0, "error": ""}

# Hazard stories that previously stored a generic place/culture photo (NZ haka, Iceland city, Telica).
# Do not bump og.VERSION; only these cards are rebuilt at boot.
HAZARD_PLACE_CARDS = ("d9c1418515395db1", "dcd0416e4a66964e", "a03826e8db39746e")
HAZARD_PLACE_REBUILD = {"done": False, "ids": 0, "error": ""}


def rebuild_maplike_place_cards(force=False):
    """One-shot: drop relief/satellite place photos for the two listed cards and re-choose a ground-level or category photo.
    Does not bump og.VERSION; other cards are left alone."""
    import story_photo as SP
    if MAPLIKE_REBUILD.get("done") and not force:
        return MAPLIKE_REBUILD
    MAPLIKE_REBUILD.update(done=False, ids=0, error="")
    for cid in MAPLIKE_PLACE_CARDS:
        try:
            try:
                SP.delete_stored_photo(cid)
            except Exception:
                pass
            invalidate_card_layers(cid)
            title, text, loc = _force_title(cid)
            lat = lon = None
            cat = ""
            try:
                import story
                r, _al = story.load(cid)
                if r:
                    title = r.get("title") or title
                    loc = r.get("location") or loc
                    text = r.get("brief") or text
                    lat, lon = r.get("lat"), r.get("lon")
                    cat = r.get("category") or ""
            except Exception:
                pass
            if card_photo_on():
                apply_card_photo(cid, title or "", loc or "", text or "", lat, lon, cat)
            invalidate_card_layers(cid)
            th = SP.card_title_key(_card_headline(title or "") or "")
            b = render_story_fresh(cid)
            src = ""
            try:
                ch = SP.db_choice(cid) or {}
                if ch and (ch.get("src") or "").startswith("https://") and not SP.is_non_photo_candidate(ch):
                    src = ch.get("src") or ""
            except Exception:
                src = ""
            if b and b.startswith(b"\x89PNG"):
                SP.put_card(cid, b, src, title_hash=th, allow_downgrade=True)
            invalidate_card_layers(cid)
            MAPLIKE_REBUILD["ids"] += 1
            print(f"share_card: maplike-rebuild {cid} src={bool(src)}", flush=True)
        except Exception as e:
            MAPLIKE_REBUILD["error"] = type(e).__name__
            print(f"share_card: maplike-rebuild {cid} err={type(e).__name__}", flush=True)
    MAPLIKE_REBUILD["done"] = True
    print(f"share_card: maplike-rebuild done {MAPLIKE_REBUILD['ids']} ids", flush=True)
    return MAPLIKE_REBUILD


def rebuild_hazard_place_cards(force=False):
    """One-shot: drop stored place photos on listed hazard cards and re-choose the category hazard photo.
    Does not bump og.VERSION; other cards (including Hegseth) are left alone."""
    import story_photo as SP
    if HAZARD_PLACE_REBUILD.get("done") and not force:
        return HAZARD_PLACE_REBUILD
    HAZARD_PLACE_REBUILD.update(done=False, ids=0, error="")
    for cid in HAZARD_PLACE_CARDS:
        try:
            try:
                SP.delete_stored_photo(cid)
            except Exception:
                pass
            invalidate_card_layers(cid)
            title, text, loc = _force_title(cid)
            lat = lon = None
            cat = ""
            try:
                import story
                r, _al = story.load(cid)
                if r:
                    title = r.get("title") or title
                    loc = r.get("location") or loc
                    text = r.get("brief") or text
                    lat, lon = r.get("lat"), r.get("lon")
                    cat = r.get("category") or ""
            except Exception:
                pass
            if card_photo_on():
                apply_card_photo(cid, title or "", loc or "", text or "", lat, lon, cat)
            invalidate_card_layers(cid)
            th = SP.card_title_key(_card_headline(title or "") or "")
            b = render_story_fresh(cid)
            src = ""
            try:
                ch = SP.db_choice(cid) or {}
                if ch and (ch.get("src") or "").startswith("https://") and not SP.is_non_photo_candidate(ch) and (ch.get("kind") or "") != "place":
                    src = ch.get("src") or ""
            except Exception:
                src = ""
            if b and b.startswith(b"\x89PNG"):
                SP.put_card(cid, b, src, title_hash=th, allow_downgrade=True)
            invalidate_card_layers(cid)
            HAZARD_PLACE_REBUILD["ids"] += 1
            print(f"share_card: hazard-place-rebuild {cid} src={bool(src)}", flush=True)
        except Exception as e:
            HAZARD_PLACE_REBUILD["error"] = type(e).__name__
            print(f"share_card: hazard-place-rebuild {cid} err={type(e).__name__}", flush=True)
    HAZARD_PLACE_REBUILD["done"] = True
    print(f"share_card: hazard-place-rebuild done {HAZARD_PLACE_REBUILD['ids']} ids", flush=True)
    return HAZARD_PLACE_REBUILD



def force_rebuild_listed_cards(force=False):
    """One-shot, admin-free boot task: rewrite Huang, Zelensky and Libya under the current rules.

    Does not trust stored match metadata, a current title_hash, or has_photo to skip a row.
    Libya: rematch Commons caption/categories against the headline subject; a memorial/topic
    photo is downgraded to the designed map. Zelensky: typography is always rebuilt from the
    stored JPEG with the cleaned title (og cache bypassed). Huang: Commons portrait lookup
    runs even if the stored card is already a map.
    """
    import story_photo as SP
    if SP.REBUILD.get("done") and not force:
        return SP.REBUILD
    SP.REBUILD.update(done=False, ids=0, error="")
    for cid in _AUDIT_FIRST:
        try:
            _force_rebuild_one(cid)
            SP.REBUILD["ids"] += 1
            print(f"story_photo: force-rebuild {cid}", flush=True)
        except Exception as e:
            SP.REBUILD["error"] = type(e).__name__
            print(f"story_photo: force-rebuild {cid} err={type(e).__name__}", flush=True)
    SP.REBUILD["done"] = True
    print(f"story_photo: force-rebuild done {SP.REBUILD['ids']} ids", flush=True)
    return SP.REBUILD


def _force_rebuild_one(cid):
    """Rewrite one listed card under current strict-match and typography rules."""
    import story_photo as SP
    invalidate_card_layers(cid)
    title, text, loc = _force_title(cid)
    if title:
        SP.SUBJECT_HINTS.setdefault(cid, (title, text or ""))
    match = SP.stored_photo_matches(cid) if title else None
    # A PEOPLE-list person without a strictly matching stored photo may get a Commons lookup.
    # Do not invent mid-headline names (Jensen Huang) or org titles (Health Ministry).
    people = []
    try:
        import x_share
        people = list(x_share.people_from_entities(title, "") or []) if title else []
    except Exception:
        people = []
    need_fetch = bool(people) and not (match is True and SP.has_photo(cid) and SP.card_has_photo(cid))
    if need_fetch:
        try:
            _network_prefetch(cid)
        except Exception:
            pass
        invalidate_card_layers(cid)
        match = SP.stored_photo_matches(cid) if title else None
    th = SP.card_title_key(_card_headline(title) or "")
    src = ""
    try:
        c = SP.pick(cid, title, loc, text)
        if c and (c.get("src") or "").startswith("https://"):
            src = c.get("src") or ""
    except Exception:
        src = ""
    if src and not SP.cached(src):
        src = ""
    b = None
    if src:
        b = render_story_fresh(cid)
    if not b or not src:
        # Designed map (mismatch, or person lookup found nothing).
        src = ""
        b = generic_story_card(cid) or render_story_fresh(cid)
    if b and b.startswith(b"\x89PNG"):
        SP.put_card(cid, b, src, title_hash=th, allow_downgrade=True)
    invalidate_card_layers(cid)


def backfill_photos(cids, pause=0.6):
    """One-time after boot (after og=true): licensed photo lookups for the top Wire items.
    Deduped on the single card/photo worker and paused between submits so it does not starve the CPU."""
    seen = set()
    n = 0
    for cid in cids or []:
        if not cid or cid in seen:
            continue
        seen.add(cid)
        try:
            import story_photo
            if story_photo.card_has_photo(cid):
                continue
            submit(cid, fetch=True, urgent=False)
            n += 1
        except Exception:
            pass
        time.sleep(max(0.3, float(pause or 0.6)))
    print(f"story_photo: backfill queued {n} photo lookups", flush=True)
    return n


_WARM_CAP = 20   # at most this many card builds queued or running (timeline pre-warm must not flood Render)


def warm(cid):
    """Build a story's card ahead of the first crawl (bounded pool, deduped, cap of 20 in flight/queued).
    After a deploy the in-memory cache is empty: hydrate the stored PNG, and only skip a photo lookup when one already ran."""
    try:
        import story_photo
        if cid not in _SC:
            b = story_photo.get_card(cid)
            if b:
                _SC[cid] = (time.time(), b, False)
        if cid in _SC and cid not in _NEED and story_photo.card_has_photo(cid):
            return
    except Exception:
        if cid in _SC and cid not in _NEED:
            return
    live = sum(1 for f in list(_INFLIGHT.values()) + list(_FINFLIGHT.values()) if f is not None and not f.done())
    live += sum(1 for f in list(_FWAIT.values()) if f is not None and not f.done())
    if live >= _WARM_CAP:
        return
    try:
        submit(cid, fetch=True, urgent=True)
    except Exception:
        pass


def handle_get(path, qs=None, headers=None):
    """addons.py routes /og/share/* here (ahead of /og)."""
    p = (path or "").split("?")[0].rstrip("/")
    if p.startswith("/og/share/"):
        return og_share(p, qs)
    return 404, {"error": "not found"}


# ------------------------------------------------------------------ adaptor for /og/share/<kind>/<id>.png (the client-supplied n/d/l fields)
def _q(qs, k, n=120):
    v = (qs or {}).get(k)
    v = v[0] if isinstance(v, list) and v else (v or "")
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f<>]", " ", str(v))).strip()[:n]


_KIND_COLOR = {"weather": WX_C, "solar": SPACE_C, "power": NET_C, "dc": NET_C, "cable": NET_C, "outage": RED, "network": NET_C, "cloud": NET_C, "page": WHITE}


def item_for_share(kind, ident, qs=None):
    """Map a share-card request from the on-page Post on X buttons to an item. Server data wins over anything in the URL."""
    kind = (kind or "").lower()
    ident = ident or ""
    it = None
    if kind in ("planet", "moon", "sun"):
        it = resolve("planet", ident.lower() if ident.lower() in PLANETS else ("moon" if kind == "moon" else ident.lower()))
    elif kind in ("craft", "roadster"):
        it = resolve("craft", "roadster" if kind == "roadster" else ident.lower())
    elif kind == "sat":
        it = resolve("sat", ident.lower())
    elif kind == "site":
        S_ = _json_file("planets/sites.json")
        for body in ("moon", "mars"):
            if any(r.get("id") == ident for r in S_.get(body) or []):
                it = resolve("site", f"{body}~{ident}")
        if not it:
            for f in S_.get("features") or []:
                if f.get("id") == ident:
                    it = resolve("site", f"{f.get('body')}~{ident}")
    elif kind == "launch":
        it = resolve("launch", ident)
    elif kind in ("network", "outage", "cloud"):
        it = resolve("net", ident.lower()) if _net_row(ident.lower()) else None
        if not it:
            for r in _cloud_rows():
                if f"{r.get('p')}-" + re.sub(r"[^A-Za-z0-9_.:-]", "", r.get("name") or "") == ident:
                    it = resolve("cloud", f"{r['p']}~{_slug(r['name'])}")
                    break
        if not it and ident.startswith("ioda-"):
            nm = ident[5:]
            for c in (_netdata().get("outages") or {}).get("countries") or []:
                if re.sub(r"[^A-Za-z0-9_.:-]", "", c.get("name") or "") == nm:
                    word, col = ("OUTAGE", RED) if c.get("cur") else ("RECENT OUTAGE", AMBER)
                    it = dict(kind="outage", id=ident, title=f"{c['name']} internet", kicker="INTERNET OUTAGE · COUNTRY", color=col, status=word,
                              stats=[(("MAJOR" if c.get("major") else "SIGNAL"), "severity")] + ([(c["cc"], "country code")] if c.get("cc") else []),
                              fact=_q(qs, "d") or f"Internet outage signal in {c['name']}, measured by IODA (Georgia Tech).", lines=[], tags=[], loc=c["name"],
                              deep="/grid", art=("map", c["lon"], c["lat"], 40), credit="Data: IODA, Georgia Tech", desc="")
                    break
    if it:
        return it
    # unknown id: typographic card from the client-supplied name / detail (sanitised, capped); never a 5xx
    name = _q(qs, "n", 90)
    if not name:
        return None
    return dict(kind=kind, id=ident, title=name, kicker=(_q(qs, "k", 30) or kind).upper()[:30] if False else {"weather": "WEATHER", "solar": "SPACE WEATHER", "power": "POWER OUTAGE", "dc": "DATA CENTER", "cable": "UNDERSEA CABLE", "outage": "OUTAGE", "network": "NETWORK", "cloud": "CLOUD"}.get(kind, "BLACKOUT.NETWORK"),
                color=_KIND_COLOR.get(kind, WHITE), stats=[], fact=_q(qs, "d", 160), lines=[], tags=[], loc=_q(qs, "l", 80), deep="/", art=("type",), credit="", desc="")


def og_share(path, qs=None):
    """handle_get for /og/share/<kind>/<id>.png (addons.py routes it here ahead of /og). Falls back to share_cards' card when we cannot resolve."""
    p = (path or "").split("?")[0].rstrip("/")
    p = p[:-4] if p.endswith(".png") else p
    m = re.fullmatch(r"/og/share/([a-z]{2,12})/([A-Za-z0-9_.:~-]{1,90})", p)
    if m:
        try:
            it = item_for_share(m.group(1), m.group(2), qs)
            if it:
                key = "x" + _key(it)
                return 200, og._cached(key, lambda: og.png_bytes(render(it))), "image/png"
        except Exception:
            import traceback
            traceback.print_exc()
        try:
            import share_cards
            return 200, share_cards.card_png(m.group(1), m.group(2), qs), "image/png"
        except Exception:
            pass
    return 404, {"error": "not found"}
