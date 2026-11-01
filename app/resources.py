#!/usr/bin/env python3
"""Local Resources add-on: address/ZIP search -> nearby emergency & essential resources from OpenStreetMap.
- Geocoding: Nominatim (proper User-Agent, <=1 request/sec, cached 30 days).
- POIs: Overpass API with mirror fallback, timeout, cached 24 h.
- Open shelters: FEMA National Shelter System public "Open Shelters" layer (free, no key), cached 30 min.
No paid APIs or keys. Data can be incomplete: call 911 in an emergency. Never touches threat scoring."""
import json, math, os, re, sqlite3, threading, time, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "resources_cache.db")
UA = "BlackoutNetwork/1.1 (+https://blackout.network; hello@blackout.network) local-resources lookup"
RADIUS_M = 12000
CAP = 15
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
OVP_RADIUS_M = 8000      # live Overpass fallback only: smaller circle keeps big-city queries light (offline index still uses RADIUS_M)
OVP_BUDGET_S = 20        # total wall time across mirrors, one mirror at a time (t480 follow-up)
OVP_FAIL_TTL = 300       # remember a failed cell for 5 min so retries don't hammer the mirrors
_ovp_lock = threading.Lock(); _ovp_mirror = [0]
FEMA = "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/MapServer/0/query"
DEFAULT_Q = ""   # no default place: the visitor types one or uses the shared location picker

CATS = [  # id, label, emoji, overpass filters, matcher(tags)
 ("police", "Police", "🚓", ['["amenity"="police"]'], lambda t: t.get("amenity") == "police"),
 ("fire", "Fire stations", "🚒", ['["amenity"="fire_station"]'], lambda t: t.get("amenity") == "fire_station"),
 ("ems", "EMS / ambulance", "🚑", ['["emergency"="ambulance_station"]', '["amenity"="ambulance_station"]'], lambda t: t.get("emergency") == "ambulance_station" or t.get("amenity") == "ambulance_station"),
 ("hospital", "Hospitals", "🏥", ['["amenity"="hospital"]', '["healthcare"="hospital"]'], lambda t: t.get("amenity") == "hospital" or t.get("healthcare") == "hospital"),
 ("clinic", "Urgent care / clinics", "🩺", ['["amenity"="clinic"]', '["healthcare"="clinic"]', '["healthcare"="urgent_care"]'], lambda t: t.get("amenity") == "clinic" or t.get("healthcare") in ("clinic", "urgent_care")),
 ("pharmacy", "Pharmacies", "💊", ['["amenity"="pharmacy"]', '["healthcare"="pharmacy"]'], lambda t: t.get("amenity") == "pharmacy" or t.get("healthcare") == "pharmacy"),
 ("fuel", "Gas stations", "⛽", ['["amenity"="fuel"]'], lambda t: t.get("amenity") == "fuel"),
 ("gov", "Local government (town hall, county offices, courthouse)", "🏛", ['["amenity"="townhall"]', '["amenity"="courthouse"]', '["office"="government"]'],
  lambda t: t.get("amenity") in ("townhall", "courthouse") or (t.get("office") == "government" and not re.search(r"emergency", t.get("name", "") + t.get("government", ""), re.I))),
 ("em", "Emergency management", "🚨", ['["office"="government"]["government"~"emergency"]', '["office"="government"]["name"~"Emergency",i]', '["emergency"="emergency_ward_entrance"]["name"~"Emergency Management",i]'],
  lambda t: t.get("office") == "government" and re.search(r"emergency", t.get("name", "") + " " + t.get("government", ""), re.I)),
 ("shelter", "Emergency shelters (OSM)", "🏠", ['["social_facility"="shelter"]', '["emergency"="assembly_point"]', '["amenity"="shelter"]["shelter_type"!~"public_transport|picnic_shelter|lean_to|field_shelter|weather_shelter"]'],
  lambda t: t.get("social_facility") == "shelter" or t.get("emergency") == "assembly_point" or (t.get("amenity") == "shelter" and t.get("shelter_type") not in ("public_transport", "picnic_shelter", "lean_to", "field_shelter", "weather_shelter") and re.search(r"shelter|emergency|refuge|evacuat", t.get("name", ""), re.I))),
 ("water", "Water (drinking water, water points, springs)", "🚰", ['["amenity"="drinking_water"]', '["amenity"="water_point"]', '["natural"="spring"]'],
  lambda t: t.get("amenity") in ("drinking_water", "water_point") or t.get("natural") == "spring"),
 ("grocery", "Grocery / supermarkets", "🛒", ['["shop"="supermarket"]', '["shop"="grocery"]'], lambda t: t.get("shop") in ("supermarket", "grocery")),
 ("hardware", "Hardware stores", "🔨", ['["shop"="hardware"]', '["shop"="doityourself"]'], lambda t: t.get("shop") in ("hardware", "doityourself")),
 ("vet", "Veterinary", "🐾", ['["amenity"="veterinary"]'], lambda t: t.get("amenity") == "veterinary"),
]

_lock = threading.Lock(); _last_nom = [0.0]
def cdb():
    c = sqlite3.connect(CACHE, timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY, t REAL, v TEXT)"); return c
def cget(k, ttl):
    c = cdb()
    try: r = c.execute("SELECT t, v FROM cache WHERE k=?", (k,)).fetchone()
    finally: c.close()
    return json.loads(r[1]) if r and time.time() - r[0] < ttl else None
def cput(k, v):
    c = cdb()
    try: c.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (k, time.time(), json.dumps(v))); c.commit()
    finally: c.close()

def http(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read(20_000_000))

def geocode(q):
    k = "geo:" + q.lower().strip()
    v = cget(k, 30 * 86400)
    if v: return v, True
    with _lock:   # Nominatim usage policy: max 1 request per second
        wait = 1.05 - (time.time() - _last_nom[0])
        if wait > 0: time.sleep(wait)
        try: res = http("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 1}), timeout=15)
        finally: _last_nom[0] = time.time()
    if not res: return None, False
    v = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"]), "display": res[0].get("display_name", q)}
    cput(k, v); return v, False

def cell(lat, lon):
    """~2 km grid cell (0.02 deg), used as the 24 h cache key so nearby searches share one Overpass answer."""
    return f"{round(lat / 0.02) * 0.02:.2f},{round(lon / 0.02) * 0.02:.2f}"

def overpass(lat, lon):
    ck = cell(lat, lon); k = f"ovp2:{ck},{OVP_RADIUS_M}"
    v = cget(k, 86400)
    if v is not None: return v, True, "cache"
    f = cget("ovpfail:" + ck, OVP_FAIL_TTL)
    if f: raise RuntimeError("OpenStreetMap lookup service is busy (tried a minute ago: " + f + "). Please retry in a few minutes.")
    clat, clon = map(float, ck.split(","))
    parts = "".join(f"nwr{flt}(around:{OVP_RADIUS_M},{clat},{clon});" for c in CATS for flt in c[3])
    q = f"[out:json][timeout:25][maxsize:67108864];({parts});out center tags qt;"
    err = []; t0 = time.time()
    with _ovp_lock:   # one Overpass request at a time from this server (usage policy)
        n = len(OVERPASS)
        for i in range(n):
            left = OVP_BUDGET_S - (time.time() - t0)
            if left < 3: err.append("time budget used"); break
            m = OVERPASS[(_ovp_mirror[0] + i) % n]
            try:
                r = http(m, data=urllib.parse.urlencode({"data": q}).encode(), timeout=min(25, left))
                if r.get("remark") and "runtime error" in r["remark"]: raise RuntimeError(r["remark"][:80])
                els = r.get("elements", [])
                _ovp_mirror[0] = (_ovp_mirror[0] + i) % n   # stick with the mirror that answered
                cput(k, els); return els, False, m
            except Exception as ex: err.append(f"{m.split('/')[2]}: {type(ex).__name__}")
        _ovp_mirror[0] = (_ovp_mirror[0] + 1) % n
    msg = "; ".join(err); cput("ovpfail:" + ck, msg)
    raise RuntimeError("OpenStreetMap lookup service did not answer in time (" + msg + "). Please retry in a few minutes.")

POI_DB = os.path.join(BASE, "resources_pois.db")
def local_pois(lat, lon):
    """Offline index built from the Geofabrik Florida OSM extract (build_poi_index.py)."""
    if not os.path.exists(POI_DB): return None, None
    c = sqlite3.connect(f"file:{POI_DB}?mode=ro", uri=True)
    try:
        bb = globals().get("_POI_BBOX") or globals().setdefault("_POI_BBOX", c.execute("SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM pois").fetchone())
        if not (bb[0] <= lat <= bb[1] and bb[2] <= lon <= bb[3]): return None, None   # outside the offline index -> live Overpass lookup
        dl = RADIUS_M / 111000 + 0.01; dn = dl / max(0.2, math.cos(math.radians(lat)))
        rows = c.execute("SELECT id, lat, lon, tags FROM pois WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?", (lat - dl, lat + dl, lon - dn, lon + dn)).fetchall()
        src = dict(c.execute("SELECT k, v FROM meta").fetchall())
    finally: c.close()
    els = []
    for i, la, lo, t in rows:
        if miles(lat, lon, la, lo) * 1609.34 > RADIUS_M: continue
        typ, oid = i.split("/"); els.append({"type": typ, "id": int(oid), "lat": la, "lon": lo, "tags": json.loads(t)})
    return els, src

def fema_shelters(lat, lon):
    k = f"fema:{lat:.2f},{lon:.2f}"
    v = cget(k, 1800)
    if v is not None: return v, None
    d = 0.35
    try:
        r = http(FEMA + "?" + urllib.parse.urlencode({"where": "1=1", "outFields": "shelter_name,address,city,state,zip,shelter_status,org_name,evacuation_capacity",
                 "geometry": f"{lon-d},{lat-d},{lon+d},{lat+d}", "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
                 "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "true", "f": "json"}), timeout=25)
        out = []
        for f in r.get("features", []):
            a = f.get("attributes", {}); g = f.get("geometry") or {}
            if "y" not in g: continue
            out.append({"name": a.get("shelter_name"), "address": ", ".join(x for x in [a.get("address"), a.get("city"), a.get("state"), a.get("zip")] if x),
                        "lat": g["y"], "lon": g["x"], "status": a.get("shelter_status"), "org": a.get("org_name"), "capacity": a.get("evacuation_capacity")})
        cput(k, out); return out, None
    except Exception as ex: return [], f"{type(ex).__name__}: {ex}"

def miles(a, b, c, d):
    R = 3958.8; p1, p2 = math.radians(a), math.radians(c); dp = p2 - p1; dl = math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def norm_phone(p):
    if not p: return None
    p = p.split(";")[0].strip(); d = re.sub(r"\D", "", p)
    if len(d) == 11 and d[0] == "1": d = d[1:]
    if len(d) == 10: return {"display": f"({d[:3]}) {d[3:6]}-{d[6:]}", "tel": "+1" + d}
    return {"display": p, "tel": "+" + d if d else None} if d else None

def addr(t):
    s = " ".join(x for x in [t.get("addr:housenumber"), t.get("addr:street")] if x)
    tail = ", ".join(x for x in [t.get("addr:city"), " ".join(y for y in [t.get("addr:state"), t.get("addr:postcode")] if y)] if x)
    if t.get("addr:full"): return t["addr:full"]
    if not s and not t.get("addr:city"): return None            # a bare state/ZIP is not an address
    return ", ".join(x for x in [s or "street not listed", tail] if x)

def places_key_present():
    names = [k for k in os.environ if re.search(r"GOOGLE.*(PLACES|MAPS)|PLACES_API", k, re.I)]
    return bool(names)

def search(q):
    q = (q or DEFAULT_Q).strip()[:120]
    if not q: return 200, {"need_location": True, "q": "", "categories": [], "note": "Enter an address, city or postcode, or pick your location."}
    if len(q) < 3: return 400, {"error": "enter an address, city or ZIP"}
    g, gc = geocode(q)
    if not g: return 404, {"error": f"could not find “{q}”"}
    els, meta = local_pois(g["lat"], g["lon"])
    if els is not None: oc, mirror = True, None
    else: els, oc, mirror = overpass(g["lat"], g["lon"])
    cats = {c[0]: {"id": c[0], "label": c[1], "emoji": c[2], "items": [], "total": 0} for c in CATS}
    seen = set()
    for e in els:
        t = e.get("tags") or {}
        la = e.get("lat") or (e.get("center") or {}).get("lat"); lo = e.get("lon") or (e.get("center") or {}).get("lon")
        if la is None: continue
        for c in CATS:
            if not c[4](t): continue
            key = (c[0], e["type"], e["id"])
            if key in seen: continue
            seen.add(key)
            name = t.get("name") or t.get("official_name") or t.get("brand") or t.get("operator")
            if not name and c[0] not in ("water", "shelter"): name = c[1].split(" (")[0].rstrip("s") + " (unnamed)"
            cats[c[0]]["items"].append({"name": name or "(unnamed)", "address": addr(t), "phone": norm_phone(t.get("phone") or t.get("contact:phone")),
                "hours": t.get("opening_hours"), "website": t.get("website") or t.get("contact:website"), "lat": la, "lon": lo,
                "miles": round(miles(g["lat"], g["lon"], la, lo), 2), "emergency": t.get("emergency"), "er": c[0] == "hospital" and t.get("emergency") == "yes",
                "osm": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
                "map": f"https://www.openstreetmap.org/?mlat={la:.6f}&mlon={lo:.6f}#map=18/{la:.6f}/{lo:.6f}"})
    for c in cats.values():
        c["items"].sort(key=lambda x: x["miles"]); c["total"] = len(c["items"]); c["items"] = c["items"][:CAP]
    for c in cats.values():
        if c["id"] == "em" and not c["items"]:
            c["note"] = "No emergency management office is mapped in OpenStreetMap here. Check your local or national emergency management agency."
            if ", Florida," in g.get("display", ""): c["link"] = "https://www.floridadisaster.org/counties/"   # state directory, offered only for places in that state
        if c["id"] == "shelter":
            c["note"] = "OSM rarely lists hurricane shelters (they are usually schools opened only during an event). Check the FEMA open-shelters list above and your county emergency management announcements."
        if c["id"] == "ems" and not c["items"]:
            c["note"] = "No separate EMS/ambulance stations mapped here; in many areas EMS runs from fire stations. Call your local emergency number."
    fema, ferr = fema_shelters(g["lat"], g["lon"])
    for s in fema:
        s["miles"] = round(miles(g["lat"], g["lon"], s["lat"], s["lon"]), 2)
        s["map"] = f"https://www.openstreetmap.org/?mlat={s['lat']:.6f}&mlon={s['lon']:.6f}#map=18/{s['lat']:.6f}/{s['lon']:.6f}"
    fema.sort(key=lambda x: x["miles"])
    rad = RADIUS_M if meta else OVP_RADIUS_M
    return 200, {"query": q, "geocode": g, "radius_km": rad / 1000, "radius_miles": round(rad / 1609.34, 1),
                 "categories": list(cats.values()), "fema_open_shelters": fema[:CAP], "fema_error": ferr,
                 "sources": {"geocoder": "Nominatim (OpenStreetMap)" + (" · cached" if gc else ""), "pois": (f"OpenStreetMap offline index from {meta.get('source')}, built {meta.get('built','')[:10]}" if meta else "OpenStreetMap via Overpass API" + (" · cached ≤24h" if oc else f" · {mirror.split('/')[2]}")),
                             "shelters": "FEMA National Shelter System — Open Shelters (public layer; only shelters currently open)"},
                 "google_places_key_found": places_key_present(),
                 "note": "OpenStreetMap data can be incomplete or out of date. In an emergency call 911.",
                 "attribution": "© OpenStreetMap contributors (ODbL)"}

def handle_get(path, qs):
    if path == "/api/resources":
        try: return search((qs.get("q") or [""])[0])
        except Exception as ex: return 503, {"error": f"lookup failed: {ex}", "retry": True}
    return 404, {"error": "not found"}
