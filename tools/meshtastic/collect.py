#!/usr/bin/env python3
"""Meshtastic public-node collector for BLACKOUT.NETWORK (box only, read-only on the mesh).

One polite GET of https://meshmap.net/nodes.json per run (the public snapshot MeshMap.net builds from the official
Meshtastic public MQTT server; it refreshes about once a minute and is served with Cache-Control max-age=60). We send a
descriptive User-Agent and If-None-Match / If-Modified-Since, never more often than every 10 minutes (MIN_GAP_S).
Nothing is ever sent to the mesh, the MQTT broker or MeshMap beyond that GET.

Output: one compact JSON file (default data/mesh_nodes.json) that tools/meshtastic/push.py pushes to Render with the
same signed one-file method as tools/story_reports/push.py. Never a database, never a full render_sync.

Privacy: we keep only a coarse position (2 decimals, about 1 km; the public broker already blurs default-channel
positions to 364 m-23 km), the role, the hardware model, the minutes since last heard and a sanitized short name
(ASCII, <= 4 chars). No node IDs, long names, telemetry, or message content are written to the output file.
The box-side state file keeps a hashed node key (sha1 of the MeshMap node number, truncated) plus a 24 h activity
bitmask, so drop-offs can be measured without storing raw IDs.

Drop-off signal (single source, unconfirmed, never high severity):
  * every 10 min sample, a node is "active" when MeshMap heard it in the last ACTIVE_MIN minutes;
  * a node is "regular" in a region when it was active in >= REGULAR_FRAC of the samples in the prior 24 h
    (needs >= MIN_SAMPLES samples first);
  * silent_pct = regular nodes not active now / regular nodes;
  * a region is flagged "watch" when regulars >= MIN_REGULARS, silent >= MIN_SILENT, silent_pct >= WATCH_PCT, for
    PERSIST consecutive samples. Rank 4 (5 when >= 75% and >= 25 regulars). Capped at 5: never red, never 7+;
  * feed guard: if the worldwide silent_pct >= FEED_GUARD_PCT, or the fetch failed / data is older than 20 min,
    the drop is treated as a data-source problem and no regional signal is raised.
Regions: U.S. grid-operator sections (app/gridstatus_static/sections.geojson), countries (app/signal_map_static/world.geojson)
and named metro watch areas (circles, below; Central Florida first).

usage: collect.py [--out PATH] [--state PATH] [--src-file nodes.json (offline test)] [--now EPOCH]
Never touches scanner.py, scoring, push.py, jets.py, config.json, aviation_watch.py or blackout.db."""
import argparse, gzip, hashlib, json, math, os, re, sys, time, urllib.request, urllib.error

URL = "https://meshmap.net/nodes.json"
UA = "BLACKOUT.NETWORK mesh status (+https://blackout.network/mesh; hello@blackout.network)"
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get("BN_MESH_APP") or next((p for p in (os.path.normpath(os.path.join(HERE, "..", "..", "app")), os.path.join(HERE, "geo"))
            if os.path.isfile(os.path.join(p, "gridstatus_static", "sections.geojson"))), os.path.join(HERE, "geo"))   # repo app/ or a copied geo/ dir
D = "/workspace/launch/meshtastic"
MIN_GAP_S = 600
ACTIVE_MIN = 60
SAMPLES_24H = 144
MIN_SAMPLES = 36          # 6 h of 10-min samples before any baseline is trusted
REGULAR_FRAC = 0.5
MIN_REGULARS = 10
MIN_SILENT = 6
WATCH_PCT = 0.5
HIGH_PCT = 0.75
PERSIST = 2
FEED_GUARD_PCT = 0.30
STALE_S = 1200
RANK_CAP = 5

# Named watch areas: (id, name, lat, lon, radius km)
AREAS = [
    ("cfl", "Central Florida (Sanford / Lake Mary / Orlando)", 28.70, -81.33, 70),
    ("tampa", "Tampa Bay", 27.95, -82.46, 60), ("sfl", "South Florida", 26.10, -80.20, 70), ("jax", "Jacksonville", 30.33, -81.66, 50),
    ("atl", "Atlanta", 33.75, -84.39, 60), ("hou", "Houston", 29.76, -95.37, 70), ("dfw", "Dallas-Fort Worth", 32.80, -97.00, 70),
    ("aus", "Austin / San Antonio", 29.90, -97.90, 90), ("phx", "Phoenix", 33.45, -112.07, 60), ("la", "Los Angeles", 34.05, -118.25, 70),
    ("sfbay", "San Francisco Bay Area", 37.65, -122.15, 70), ("sea", "Seattle / Puget Sound", 47.55, -122.30, 70),
    ("den", "Denver / Front Range", 39.85, -104.95, 80), ("chi", "Chicago", 41.88, -87.70, 60), ("nyc", "New York City", 40.73, -73.95, 60),
    ("dc", "Washington, D.C.", 38.90, -77.04, 60), ("bos", "Boston", 42.36, -71.06, 60), ("phl", "Philadelphia", 39.95, -75.16, 50),
    ("lon", "London", 51.51, -0.13, 60), ("ber", "Berlin", 52.52, 13.40, 60), ("tpe", "Taipei", 25.03, 121.56, 50),
]
ROLE = {"CLIENT": "C", "CLIENT_MUTE": "M", "CLIENT_HIDDEN": "M", "CLIENT_BASE": "B", "ROUTER": "R", "ROUTER_CLIENT": "R", "ROUTER_LATE": "R",
        "REPEATER": "P", "TRACKER": "T", "TAK": "T", "TAK_TRACKER": "T", "SENSOR": "S", "LOST_AND_FOUND": "T"}

def log(m): print(time.strftime("[%Y-%m-%d %H:%M:%S %Z] ") + m, flush=True)

# ---------------------------------------------------------------- geometry
def _pip(x, y, ring):
    inside = False; n = len(ring); j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]; xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi: inside = not inside
        j = i
    return inside
class Polys:
    def __init__(self, path, key):
        self.items = []
        try: g = json.load(open(path))
        except Exception: return
        for f in g.get("features", []):
            p = f.get("properties") or {}; geom = f.get("geometry") or {}
            polys = geom.get("coordinates") or []
            if geom.get("type") == "Polygon": polys = [polys]
            elif geom.get("type") != "MultiPolygon": continue
            xs = [pt[0] for poly in polys for pt in poly[0]]; ys = [pt[1] for poly in polys for pt in poly[0]]
            if not xs: continue
            self.items.append((p.get(key) or p.get("name"), p.get("name") or p.get(key), (min(xs), min(ys), max(xs), max(ys)), polys))
    def find(self, lon, lat):
        for k, name, (x0, y0, x1, y1), polys in self.items:
            if x0 <= lon <= x1 and y0 <= lat <= y1:
                for poly in polys:
                    if _pip(lon, lat, poly[0]) and not any(_pip(lon, lat, h) for h in poly[1:]): return k, name
        return None, None
def km(a, b, c, d):
    p = math.pi / 180; h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))

# ---------------------------------------------------------------- fetch
def fetch(cache_meta):
    h = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"}
    if cache_meta.get("etag"): h["If-None-Match"] = cache_meta["etag"]
    if cache_meta.get("lm"): h["If-Modified-Since"] = cache_meta["lm"]
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, headers=h), timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 304: return None, cache_meta, "not-modified"
        return None, cache_meta, f"HTTP {e.code}"
    except Exception as e:
        return None, cache_meta, f"error {type(e).__name__}"
    b = r.read(40_000_000)
    if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
    meta = {"etag": r.headers.get("ETag"), "lm": r.headers.get("Last-Modified")}
    return json.loads(b), meta, "ok"

ASCII = re.compile(r"[^A-Za-z0-9 _.\-]")
def short(s):
    s = ASCII.sub("", (s or "")).strip()[:4]
    return s or ""
def nkey(nid): return hashlib.sha1(("bn-mesh:" + str(nid)).encode()).hexdigest()[:12]

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(D, "data", "mesh_nodes.json"))
    ap.add_argument("--state", default=os.path.join(D, "state.json"))
    ap.add_argument("--src-file", help="offline test: read a saved nodes.json instead of fetching")
    ap.add_argument("--now", type=float, help="offline test: pretend the time is this epoch")
    ap.add_argument("--force", action="store_true", help="ignore MIN_GAP_S (tests only)")
    a = ap.parse_args()
    now = a.now or time.time()
    try: st = json.load(open(a.state))
    except Exception: st = {"nodes": {}, "samples": 0, "flags": {}, "meta": {}}
    if not a.force and not a.src_file and now - st.get("last_fetch", 0) < MIN_GAP_S:
        log(f"skip: last fetch {int(now - st['last_fetch'])} s ago (min gap {MIN_GAP_S} s)"); return 0
    if a.src_file: raw, meta, status = json.load(open(a.src_file)), st.get("meta", {}), "ok (file)"
    else: raw, meta, status = fetch(st.get("meta", {}))
    st["last_fetch"] = now; st["meta"] = meta or {}
    if raw is None:
        log(f"fetch: {status}")
        prev = None
        try: prev = json.load(open(a.out))
        except Exception: pass
        if prev:   # keep the last good snapshot but mark it stale; never raise signals on stale data
            prev["feed"] = dict(prev.get("feed") or {}, ok=status == "not-modified" and now - prev.get("feed", {}).get("source_t", 0) < STALE_S, last_status=status)
            if not prev["feed"]["ok"]: prev["signals"] = []
            _write(a.out, prev)
        _write(a.state, st); return 0 if status == "not-modified" else 1

    secs = Polys(os.path.join(APP, "gridstatus_static", "sections.geojson"), "id")
    world = Polys(os.path.join(APP, "signal_map_static", "world.geojson"), "name")
    nodes_out, hw, hwi = [], [], {}
    reg = {}      # region id -> {"name", "kind", "regular", "silent", "active", "total"}
    def R(rid, name, kind):
        r = reg.get(rid)
        if r is None: r = reg[rid] = {"id": rid, "name": name, "kind": kind, "total": 0, "active": 0, "regular": 0, "silent": 0}
        return r
    newest = 0
    old = st.get("nodes", {}); new = {}
    samples = min(st.get("samples", 0) + 1, 10**9)
    for nid, v in raw.items():
        try: lat = v["latitude"] / 1e7; lon = v["longitude"] / 1e7
        except Exception: continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): continue
        seen = max((v.get("seenBy") or {}).values() or [0])
        newest = max(newest, seen)
        age_min = max(0, int((now - seen) / 60)) if seen else 9999
        active = age_min <= ACTIVE_MIN
        k = nkey(nid); prev = old.get(k) or {}
        mask = ((int(prev.get("m", 0)) << 1) | (1 if active else 0)) & ((1 << SAMPLES_24H) - 1)
        prior = int(prev.get("m", 0)) & ((1 << SAMPLES_24H) - 1)     # the 24 h BEFORE this sample
        nprior = min(int(prev.get("n", 0)), SAMPLES_24H)
        regular = nprior >= MIN_SAMPLES and bin(prior).count("1") >= REGULAR_FRAC * nprior
        sec, _ = secs.find(lon, lat)
        cty, cname = world.find(lon, lat)
        keys = []
        if sec: keys.append(("grid:" + sec, None, "grid"))
        if cty: keys.append(("country:" + cty, cname, "country"))
        for aid, aname, alat, alon, rad in AREAS:
            if abs(lat - alat) < 2 and abs(lon - alon) < 2.5 and km(lat, lon, alat, alon) <= rad: keys.append(("area:" + aid, aname, "area"))
        for rid, name, kind in keys + [("world", "Worldwide", "world")]:
            r = R(rid, name or rid.split(":", 1)[1], kind); r["total"] += 1; r["active"] += active
            if regular: r["regular"] += 1; r["silent"] += (not active)
        new[k] = {"m": mask, "n": nprior + 1}
        m = v.get("hwModel") or "UNKNOWN"
        if m not in hwi: hwi[m] = len(hw); hw.append(m)
        nodes_out.append([round(lat, 2), round(lon, 2), ROLE.get(v.get("role") or "", "C"), hwi[m], min(age_min, 9999), short(v.get("shortName"))])
    # nodes MeshMap dropped (no position update for 8 h) still count as silent regulars in their last region? We do not know their
    # region any more, so they are kept in state (mask shifts with zeros) but only counted while MeshMap still lists them. Expire after 24 h.
    for k, pv in old.items():
        if k not in new:
            m = (int(pv.get("m", 0)) << 1) & ((1 << SAMPLES_24H) - 1)
            if m: new[k] = {"m": m, "n": min(int(pv.get("n", 0)) + 1, SAMPLES_24H)}
    st["nodes"] = new; st["samples"] = samples
    feed_age = now - newest if newest else 1e9
    sec_names = {k: n for k, n, *_ in secs.items}
    for r in reg.values():
        if r["kind"] == "grid": r["name"] = sec_names.get(r["id"].split(":", 1)[1], r["name"])
        r["silent_pct"] = round(r["silent"] / r["regular"], 3) if r["regular"] else None
        r["baseline_ready"] = r["regular"] > 0
    w = reg.get("world") or {"silent_pct": 0}
    feed_ok = feed_age < STALE_S and (w.get("silent_pct") or 0) < FEED_GUARD_PCT
    flags = st.get("flags", {}); signals = []
    for r in reg.values():
        hit = (feed_ok and r["kind"] != "world" and r["regular"] >= MIN_REGULARS and r["silent"] >= MIN_SILENT and (r["silent_pct"] or 0) >= WATCH_PCT)
        flags[r["id"]] = (flags.get(r["id"], 0) + 1) if hit else 0
        r["status"] = "watch" if flags[r["id"]] >= PERSIST else ("forming" if hit else ("normal" if r["regular"] >= MIN_REGULARS else "too-few"))
        if r["status"] == "watch":
            rank = 5 if (r["silent_pct"] >= HIGH_PCT and r["regular"] >= 25) else 4
            signals.append({"region": r["id"], "name": r["name"], "kind": r["kind"], "rank": min(rank, RANK_CAP), "list": "watchlist",
                            "single_source": True, "confirmed": False, "silent": r["silent"], "regular": r["regular"], "silent_pct": r["silent_pct"],
                            "title": f"Meshtastic nodes gone quiet: {r['name']} ({r['silent']} of {r['regular']} regular nodes, {round(100 * r['silent_pct'])}%)",
                            "note": "Single source (MeshMap.net / Meshtastic public MQTT). Unconfirmed. A drop can mean a power or internet outage at gateway nodes, or just an MQTT or gateway problem.",
                            "since_samples": flags[r["id"]]})
    st["flags"] = flags
    signals.sort(key=lambda s: (-s["rank"], -s["silent_pct"]))
    regions = sorted(reg.values(), key=lambda r: (r["kind"] != "area", r["kind"] != "grid", -r["total"]))
    out = {"v": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
           "feed": {"ok": feed_ok, "source": "MeshMap.net nodes.json (Meshtastic public MQTT)", "source_url": "https://meshmap.net/",
                    "source_t": newest, "age_s": int(feed_age) if newest else None, "last_status": status, "samples": samples,
                    "baseline_ready": samples >= MIN_SAMPLES, "world_silent_pct": w.get("silent_pct")},
           "params": {"active_min": ACTIVE_MIN, "regular_frac": REGULAR_FRAC, "min_regulars": MIN_REGULARS, "min_silent": MIN_SILENT,
                      "watch_pct": WATCH_PCT, "persist_samples": PERSIST, "rank_cap": RANK_CAP, "feed_guard_pct": FEED_GUARD_PCT},
           "counts": {"total": len(nodes_out), "active": sum(1 for n in nodes_out if n[4] <= ACTIVE_MIN)},
           "focus": "area:cfl", "areas": [{"id": "area:" + a[0], "name": a[1], "lat": a[2], "lon": a[3], "r_km": a[4]} for a in AREAS],
           "hw": hw, "nodes": nodes_out, "regions": regions, "signals": signals}
    _write(a.out, out); _write(a.state, st)
    log(f"ok: {len(nodes_out)} nodes, {out['counts']['active']} active, {len(signals)} signals, samples {samples}, feed_ok {feed_ok}")
    return 0

def _write(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path + ".tmp", "w") as f: json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(path + ".tmp", path)

if __name__ == "__main__":
    raise SystemExit(main())
