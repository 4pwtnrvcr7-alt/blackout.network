"""Network Status map (/grid, Nov 23 2026, pt1755u): route, page skeleton, no yellow, no OSM tiles, bars math, old hub kept."""
import os, sys, re, unittest
from datetime import datetime, timezone, timedelta
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"

class NetMap(unittest.TestCase):
    def test_routes(self):
        import addons, netmap, netpages
        self.assertEqual(addons.ROUTES["/api/netmap"], "netmap")
        self.assertEqual(addons.ROUTES["/grid"], "netpages")
        code, body, ct = netpages.handle_get("/grid", {})
        self.assertEqual((code, ct), (200, "text/html"))
        for s in ('id="nx_map"', 'id="nx_ld"', 'id="gx_more"', 'id="nx_more"', 'id="nx_f"', "/api/netmap/net.js", "/api/signal/maplibre-gl.js"):
            self.assertIn(s, body)
        self.assertEqual(netmap.handle_get("/api/netmap/nope")[0], 404)
        self.assertEqual(netmap.handle_get("/api/netmap/net.js")[0], 200)

    def test_static_rules(self):
        for f in ("net.css", "net.js"):
            t = open(os.path.join(APP, "netmap_static", f), encoding="utf-8").read().lower()
            # Nov 24 2026 (Matt): the one allowed yellow is the 230 kV+ line status colour (LCOL.strain #F5D547) and its legend words
            t = t.replace("yellow strained or warning", "").replace('strain: "#f5d547"', "").replace('1: "#f5d547"', "")   # + the undersea cable status yellow (CCOL[1], pt1812u)
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            self.assertNotIn("f5d547", t)
            self.assertNotIn("tile.openstreetmap.org", t)
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#ff9900"): self.assertNotIn(c, t)
            self.assertIn("prefers-reduced-motion", t) if f == "net.js" else None
        self.assertIn("25000", open(os.path.join(APP, "netmap_static", "net.js")).read())

    def test_power_line_status_colours(self):
        """Regression (pt1816u, Nov 24 2026): U.S. 230 kV+ lines must stay green / yellow / red by operator status, never one colour."""
        js = open(os.path.join(APP, "netmap_static", "net.js"), encoding="utf-8").read()
        self.assertIn('var LCOL = { ok: "#2FD67B", strain: "#F5D547", out: "#FF3B3B", na: "#7C8190" }', js)
        self.assertRegex(js, r'OPS\.forEach\(function \(o\) \{ e\.push\(\["within", o\.g\], LCOL\[opSt\(o\.id\)\]')
        for lid in ("gl-lo", "gl-hi"):   # both line layers paint with the status expression, not the old single-hue kV ramp
            m = re.search(r'id: "' + lid + r'".*?"line-color": (\w+)\(\)', js, re.S)
            self.assertEqual(m.group(1), "lineCol", lid)
        self.assertIn('document.addEventListener("gx:status", gridColor)', js)
        self.assertIn('then(function (j) { OPS = j.ops || []; gridColor(); })', js)
        gl = open(os.path.join(APP, "netmap_static", "gridlayer.js"), encoding="utf-8").read()
        self.assertIn('window.__gxRegionStatus = rs', gl)
        self.assertIn('new CustomEvent("gx:status")', gl)
        # every operator outline has a live status id, so lines can take more than one colour
        ops = __import__("json").load(open(os.path.join(APP, "netmap_static", "gridops.json")))["ops"]
        self.assertGreaterEqual(len(ops), 8)
        for o in ops: self.assertIn(o["g"]["type"], ("Polygon", "MultiPolygon"))
        # the normal internet tint must not wash the lines green while Power grid is on
        self.assertIn('map.setPaintProperty("inet-fill", "fill-opacity", ON.grid ? ["case", ["==", ["get", "l"], 0], 0.06, ["get", "o"]] : ["get", "o"])', js)
        self.assertIn("l: l, o: l >= 3", js)

    def test_boot_loader(self):
        """Nov 24 2026 (pt1795u): the loader is the old /grid "Energizing the grid" animation (boot.js kept in the repo, no longer loaded).
        Progress ids net.js drives are present, reduced motion is honored, no yellow or red neon."""
        import colorsys, netmap, netpages
        self.assertEqual(netmap.handle_get("/api/netmap/boot.js")[0], 200)
        body = netpages.handle_get("/grid", {})[1]
        self.assertNotIn("/api/netmap/boot.js", body)
        self.assertLess(body.index('class="gx-ld" id="nx_ld"'), body.index("/api/netmap/net.js"))
        for s in ('id="nx_ldn"', 'id="nx_ldmsg"', "Energizing the grid", 'class="gx-ldsvg"', 'data-s="map"', 'data-s="nets"', 'data-s="out"', 'data-s="rep"'): self.assertIn(s, body)
        css = open(os.path.join(APP, "netmap_static", "gridlayer.css"), encoding="utf-8").read()
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("body.nx-ready .gx-ld{opacity:0", css)
        for f in ("gridlayer.css",):
            t = open(os.path.join(APP, "netmap_static", f), encoding="utf-8").read()
            t = t[t.index(".gx-ld"):t.index(".gx-ld") + 4000]
            for h in set(re.findall(r"#([0-9A-Fa-f]{6})\b", t)):
                r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
                hue, l, sat = colorsys.rgb_to_hls(r, g, b)
                if sat > 0.4 and l > 0.25: self.assertFalse(hue < 0.06 or 0.97 < hue or 0.08 < hue < 0.2, f + " #" + h)

    def test_bars_union_and_bounds(self):
        import netmap
        n = datetime.now(timezone.utc)
        days, up = netmap._bars([(n - timedelta(hours=5), n - timedelta(hours=3), 2), (n - timedelta(hours=4), n - timedelta(hours=2), 3), (n - timedelta(days=90), None, 1)])
        self.assertEqual(len(days), netmap.DAYS)
        self.assertTrue(0 <= up <= 100)
        self.assertAlmostEqual(100 - up, 100 * 3 * 3600 / ((n - (n.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=netmap.DAYS - 1))).total_seconds()), places=1)
        self.assertEqual(max(days), 3)

    def test_asn_status(self):
        import netmap, time
        t = int(time.time())
        ev = [{"location": "asn/1", "datasource": "bgp", "start": t - 1800, "duration": 600, "location_name": "AS1"},
              {"location": "asn/1", "datasource": "merit-nt", "start": t - 600, "duration": 60, "location_name": "AS1"},
              {"location": "asn/2", "datasource": "bgp", "start": t - 86400 * 5, "duration": 86400 * 10, "location_name": "AS2"}]
        self.assertEqual(netmap.asn_one([1], ev)["level"], 2)
        self.assertEqual(netmap.asn_one([2], ev)["level"], 0)   # baseline shift longer than 3 days is ignored

    def test_every_network_has_links(self):
        import netmap
        ids = set()
        for n in netmap.NETS:
            self.assertNotIn(n[0], ids); ids.add(n[0])
            self.assertTrue((n[5] is None and n[3] == "watch" or n[5].startswith("https://")) and n[6].startswith("https://"), n[0])   # feedless banks have no status page
            self.assertIn(n[2], {g for g, _ in netmap.GROUPS})

if __name__ == "__main__":
    unittest.main()

CSV = ("OBJECT_NAME,OBJECT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,RA_OF_ASC_NODE,ARG_OF_PERICENTER,MEAN_ANOMALY,EPHEMERIS_TYPE,CLASSIFICATION_TYPE,NORAD_CAT_ID,ELEMENT_SET_NO,REV_AT_EPOCH,BSTAR,MEAN_MOTION_DOT,MEAN_MOTION_DDOT\n"
       + "".join(f"SAT {i},2020-001A,2026-11-22T12:00:00.123456,15.06,0.0001,53.0,10.0,90.0,270.0,0,U,{40000+i},999,100,0.0001,0,0\n" for i in range(9)))

class NetSky(unittest.TestCase):
    def setUp(self):
        import tempfile, netsky
        self.d = tempfile.mkdtemp(); os.environ["BN_STARLINK_CACHE_DIR"] = self.d; netsky._MEM.clear()
        p = os.path.join(self.d, "g.csv"); open(p, "w").write(CSV); self.p = p

    def test_sky_payload_lite_and_missing(self):
        import netsky, json, time
        from unittest import mock
        def fake(gid, grp): return (self.p, time.time(), None) if gid in ("starlink", "gps") else (None, None, "HTTPError")
        with mock.patch.object(netsky, "_file", fake):
            full = json.loads(netsky.sky(False)); lite = json.loads(netsky.sky(True))
        g = {x["id"]: x for x in full["groups"]}
        self.assertEqual(len(full["groups"]), 8)
        self.assertEqual((g["starlink"]["total"], g["gps"]["shown"]), (9, 9))
        self.assertEqual(g["goes"]["shown"], 0); self.assertTrue(g["goes"]["error"])
        self.assertEqual(len(full["sats"]), 18); self.assertEqual(len(lite["sats"]), 3 + 9)
        self.assertEqual(len(full["sats"][0]), len(full["fields"]))
        self.assertAlmostEqual(full["sats"][0][2] % 1, 0.123, places=2)

    def test_routes_and_space_fallback(self):
        import netmap, netsky
        from unittest import mock
        with mock.patch.object(netsky, "sky_cached", lambda lite: b'{"lite":%d}' % lite):
            self.assertEqual(netmap.handle_get("/api/netmap/sky", {"lite": ["1"]})[1], b'{"lite":1}')
            self.assertEqual(netmap.handle_get("/api/netmap/sky", {})[1], b'{"lite":0}')
        def boom(u): raise OSError("down")
        with mock.patch.object(netsky, "_j", boom):
            code, body = netmap.handle_get("/api/netmap/space", {})[:2]
        self.assertEqual(code, 200); self.assertFalse(body["ok"])

    def test_space_levels(self):
        import netsky
        from unittest import mock
        def fake(u):
            if "scales" in u: return {"0": {"DateStamp": "2026-11-23", "TimeStamp": "06:00:00", "R": {"Scale": "0"}, "S": {"Scale": "0"}, "G": {"Scale": "3"}}}
            return [{"time_tag": "2026-11-23T03:00:00", "Kp": 7.0}]
        with mock.patch.object(netsky, "_j", fake): w = netsky.space()
        self.assertTrue(w["ok"]); self.assertEqual(w["scales"]["G"], 3); self.assertEqual(w["gnss"], "Watch")
        self.assertIn("gpsjam.org", w["jamming"]["url"])

    def test_page_has_sky(self):
        import netpages
        b = netpages.handle_get("/grid", {})[1]
        for s in ('id="nx_mode"', 'data-m="sky"', 'id="nx_sf"', 'id="nx_sw"', "BN_SATJS", "sha384-"): self.assertIn(s, b)

    def test_sky_spin_layer_path_and_mobile_chip(self):
        # pt1813u: globe auto-rotate, constellations layer in small-to-Starlink, two-orbit path, compact mobile chip
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "netmap_static"
        js = (root / "net.js").read_text()
        css = (root / "net.css").read_text()
        self.assertIn("function skySpinStart", js)
        self.assertIn("function layerIn", js)
        self.assertIn('if (a.id === "starlink") return 1', js)
        self.assertIn("k <= 120", js)
        self.assertIn("two orbits", js)
        self.assertIn("nx-sky-focus", js)
        self.assertIn("function clearSat", js)
        self.assertIn("nx-sat-alt", js)
        self.assertIn("nx-sky-focus", css)
        self.assertIn("nx-sat-more", css)
        added = css.split("pt1813u")[-1]
        self.assertNotIn("#FFC21A", added)
        self.assertNotIn("yellow", added.lower())

class NetSkyStarlinkFallback(unittest.TestCase):
    def test_supgp_when_group_refused(self):
        import netsky, netstarlink, tempfile
        from unittest import mock
        os.environ["BN_STARLINK_CACHE_DIR"] = tempfile.mkdtemp(); netsky._BO.clear()
        seen = []
        def fetch(gid, url): seen.append((gid, url)); return ("/x", 1.0, None)
        with mock.patch.object(netstarlink, "celestrak_file", lambda *a: (None, None, "HTTP 403")), mock.patch.object(netsky, "_fetch", fetch):
            self.assertEqual(netsky._file("starlink", "starlink"), ("/x", 1.0, None))
        self.assertEqual(seen[0][0], "starlink_sup"); self.assertIn("sup-gp.php?FILE=starlink", seen[0][1])

class NetRails(unittest.TestCase):
    def test_rails_group_and_component_filter(self):
        import netmap
        from unittest import mock
        self.assertIn("rails", [g for g, _ in netmap.GROUPS])
        ids = {n[0]: n for n in netmap.NETS if n[2] == "rails"}
        for k in ("fedres", "column"): self.assertIn(k, ids)
        grp = {n[0]: n[2] for n in netmap.NETS}   # pt1758u board groups: Login.gov under Government, Bandwidth voice under Apps
        self.assertEqual((grp["logingov"], grp["ssa"], grp["cloudgov"], grp["bandwidth"]), ("gov", "gov", "gov", "apps"))
        self.assertEqual(ids["fedres"][3], "link")   # Fed's status app disallows robots: link only, never fetched
        summ = {"status": {"indicator": "major"}, "components": [{"name": "FedWire", "status": "operational"}, {"name": "Production", "status": "major_outage"}],
                "incidents": [{"name": "API down", "status": "investigating", "components": [{"name": "Production"}]}]}
        def jg(u, **k): return summ if u.endswith("summary.json") else {"incidents": []}
        with mock.patch.object(netmap, "jget", jg):
            netmap._C.clear() if hasattr(netmap, "_C") else None
            r = netmap.spc_one(("https://x.example", r"^(FedWire|FedACH)$"))
        self.assertEqual(r["level"], 0); self.assertEqual(r["incidents"], [])
        self.assertEqual(netmap.link_one("see page")["level"], -1)
