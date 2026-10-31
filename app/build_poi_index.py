#!/usr/bin/env python3
"""Build resources_pois.db (statewide emergency/essential POIs) from the Geofabrik Florida OSM extract.
Run with /workspace/.mapenv/bin/python. Offline, $0. Data © OpenStreetMap contributors (ODbL)."""
import json, os, sqlite3, sys, time
import osmium
PBF = sys.argv[1] if len(sys.argv) > 1 else "/workspace/osm/florida-latest.osm.pbf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources_pois.db")
KEEP = {"amenity": {"police", "fire_station", "ambulance_station", "hospital", "clinic", "pharmacy", "fuel", "townhall", "courthouse", "shelter", "drinking_water", "water_point", "veterinary", "doctors"},
        "emergency": {"ambulance_station", "assembly_point"}, "healthcare": {"hospital", "clinic", "urgent_care", "pharmacy"},
        "office": {"government"}, "social_facility": {"shelter"}, "natural": {"spring"}, "shop": {"supermarket", "grocery", "hardware", "doityourself"}}
TAGS = ("name", "official_name", "brand", "operator", "addr:housenumber", "addr:street", "addr:city", "addr:state", "addr:postcode", "addr:full", "phone", "contact:phone",
        "opening_hours", "website", "contact:website", "shelter_type", "government", "emergency", "healthcare", "amenity", "office", "social_facility", "natural", "shop", "healthcare:speciality")
def want(t): return any(t.get(k) in v for k, v in KEEP.items())
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.rows = []
    def add(s, typ, i, lat, lon, tags):
        t = {k: tags.get(k) for k in TAGS if tags.get(k)}
        s.rows.append((f"{typ}/{i}", lat, lon, json.dumps(t)))
    def node(s, n):
        if n.tags and want(n.tags): s.add("node", n.id, n.location.lat, n.location.lon, n.tags)
    def way(s, w):
        if w.tags and want(w.tags):
            try:
                pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
                if pts: s.add("way", w.id, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), w.tags)
            except Exception: pass
t0 = time.time(); h = H(); h.apply_file(PBF, locations=True, idx="flex_mem")
tmp = OUT + ".tmp"
if os.path.exists(tmp): os.remove(tmp)
c = sqlite3.connect(tmp); c.execute("CREATE TABLE pois(id TEXT PRIMARY KEY, lat REAL, lon REAL, tags TEXT)"); c.executemany("INSERT OR IGNORE INTO pois VALUES(?,?,?,?)", h.rows)
c.execute("CREATE INDEX ix_ll ON pois(lat, lon)"); c.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
c.execute("INSERT INTO meta VALUES('source', ?)", (os.path.basename(os.path.realpath(PBF)) + " (Geofabrik extract, mtime " + time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(PBF))) + ")",))
c.execute("INSERT INTO meta VALUES('built', ?)", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),)); c.commit(); c.close(); os.replace(tmp, OUT)
print(len(h.rows), "pois in", round(time.time() - t0), "s")
