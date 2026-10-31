"""Maps add-on: list of downloadable printable PDF maps (static/maps), statewide emergency POIs for the
interactive map, FDEM evacuation routes, and address search (reuses the Local Resources Nominatim proxy + cache).
No paid services or keys. Never touches threat scoring."""
import json, os, sqlite3, time
BASE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(BASE, "static", "maps")
CATS = ("hospital", "clinic", "fire", "ems", "police", "em", "shelter", "water")
_cache = {"pois": None, "t": 0}
def _pois():
    if _cache["pois"] and time.time() - _cache["t"] < 3600: return _cache["pois"]
    import resources
    out = []
    c = sqlite3.connect(f"file:{BASE}/resources_pois.db?mode=ro", uri=True)
    try:
        for pid, lat, lon, tags in c.execute("SELECT id, lat, lon, tags FROM pois"):
            t = json.loads(tags)
            for cid, label, emo, _, m in resources.CATS:
                if cid in CATS:
                    try: hit = m(t)
                    except Exception: hit = False
                    if hit:
                        a = t.get("addr:full") or " ".join(x for x in [t.get("addr:housenumber"), t.get("addr:street")] if x)
                        if t.get("addr:city"): a = (a + ", " if a else "") + t["addr:city"]
                        out.append([cid, round(lat, 6), round(lon, 6), t.get("name") or t.get("brand") or t.get("operator") or "", a, t.get("phone") or t.get("contact:phone") or "", pid]); break
    finally: c.close()
    _cache.update(pois=out, t=time.time()); return out
def _list():
    try: meta = json.load(open(os.path.join(MAPS, "maps_index.json")))
    except Exception: meta = {"maps": []}
    # Owner's private home-area maps (street atlas, POI list, USGS quads) live in a box-only index; never on the public node.
    if not os.environ.get("BN_WEB_ONLY"):
        try: meta["maps"] = meta["maps"] + [dict(m, private=True) for m in json.load(open(os.path.join(MAPS, "private_maps_index.json")))["maps"]]
        except Exception: pass
    for m in meta["maps"]:
        f = os.path.join(MAPS, m["file"]); m["available"] = os.path.isfile(f); m["bytes"] = os.path.getsize(f) if m["available"] else 0
    return meta
def handle_get(path, qs):
    if path == "/api/maps/list": return 200, _list()
    if path == "/api/maps/pois":
        import resources
        return 200, {"cats": {c[0]: {"label": c[1], "emoji": c[2]} for c in resources.CATS if c[0] in CATS}, "pois": _pois(),
                     "note": "OpenStreetMap (ODbL). Offline layer coverage so far: Florida, US (other regions: use search; more regions can be indexed); may be incomplete."}
    if path == "/api/maps/geocode":
        import resources
        q = (qs.get("q") or [""])[0].strip()[:120]
        if len(q) < 3: return 400, {"error": "enter an address, city or ZIP"}
        g, cached = resources.geocode(q)
        return (200, {**g, "cached": cached}) if g else (404, {"error": f"could not find “{q}”"})
    return 404, {"error": "not found"}
