"""Shared visitor location (geo picker) add-on. The public site has NO default location: visitors pick a country/state or
click "Use my location" (browser geolocation; coordinates are rounded and only sent with the lookup request, never logged
or stored server-side; the choice is kept in the visitor's own localStorage).
The owner's private preset (private_location.json) exists only on the box, is never packaged/synced (render_rules private_*),
and is returned only after the admin passcode."""
import builtins, hmac, json, math, os, time
BASE = os.path.dirname(os.path.abspath(__file__)); STATIC = os.path.join(BASE, "geo_static")
FILES = {"geo.js": "application/javascript", "geo.css": "text/css"}
PRIV = os.path.join(BASE, "private_location.json")
G = getattr(builtins, "_bn_visitor_geo", None)
if G is None: G = builtins._bn_visitor_geo = {"data": None, "mt": 0, "fails": {}}

def data():
    p = os.path.join(BASE, "radio_geo.json"); mt = os.path.getmtime(p)
    if G["data"] is None or G["mt"] != mt:
        d = json.load(open(p)); G["data"], G["mt"] = d, mt
        d["_states"] = {s["code"]: s for s in d["states"]}; d["_cc"] = {c["cc"]: c["name"] for c in d["countries"]}
    return G["data"]

def km(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

def private_available(): return os.path.isfile(PRIV) and not os.environ.get("BN_WEB_ONLY")

def where(lat, lon):
    d = data(); ap = min(d["airports"], key=lambda a: km(lat, lon, a["lat"], a["lon"]))
    cc = ap["cc"]; st = ap["rg"].split("-", 1)[1] if cc == "US" and "-" in ap["rg"] else ""
    stname = d["_states"].get(st, {}).get("name", "") if st else ""
    return {"cc": cc, "country": d["_cc"].get(cc, cc), "st": st, "stname": stname, "city": ap["city"],
            "label": ", ".join(x for x in [ap["city"], stname or d["_cc"].get(cc, cc)] if x), "lat": round(lat, 2), "lon": round(lon, 2)}

def center(cc, st):
    d = data()
    if st:
        pts = [(n["lat"], n["lon"]) for n in d["nwr"] if n["st"] == st] or [(a["lat"], a["lon"]) for a in d["airports"] if a["rg"] == f"US-{st}"]
    else:
        c = next((c for c in d["countries"] if c["cc"] == cc), None)
        pts = [(c["lat"], c["lon"])] if c else []
    if not pts: return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

def handle_get(path, qs):
    n = path[len("/api/geo/"):] if path.startswith("/api/geo/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/geo/meta":
        d = data()
        return 200, {"countries": [{"cc": c["cc"], "name": c["name"]} for c in d["countries"]], "states": [{"code": s["code"], "name": s["name"]} for s in d["states"]],
                     "private_available": private_available()}
    if path == "/api/geo/where":
        try: lat, lon = float((qs.get("lat") or [""])[0]), float((qs.get("lon") or [""])[0])
        except ValueError: return 400, {"error": "lat and lon required"}
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): return 400, {"error": "out of range"}
        return 200, where(lat, lon)
    return 404, {"error": "not found"}

def handle_post(path, d, ip=None):
    if path != "/api/geo/private": return 404, {"error": "not found"}
    if not private_available(): return 404, {"error": "not available"}
    t = time.time(); f = [x for x in G["fails"].get(ip, []) if t - x < 600]; G["fails"][ip] = f
    if len(f) >= 5: return 429, {"error": "too many attempts, wait 10 min"}
    try: pw = open(os.path.join(BASE, "ADMIN_PASSCODE.txt")).read().strip()
    except Exception: return 503, {"error": "admin not configured"}
    given = str((d or {}).get("passcode") or "")
    if not given or not hmac.compare_digest(given.encode(), pw.encode()): f.append(t); return 403, {"error": "admin passcode required"}
    p = json.load(open(PRIV)); p.pop("note", None); p["private"] = True
    return 200, p
