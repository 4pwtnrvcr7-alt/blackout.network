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

    def test_legend_is_a_collapsed_key(self):
        """pt1822u: the map key is a collapsed Key pill at the bottom, not a box at the top of the map."""
        import netpages
        from pathlib import Path
        b = netpages.handle_get("/grid", {})[1]
        self.assertIn('id="nx_leg_btn"', b)
        self.assertIn(">Key</button>", b)
        self.assertIn('aria-expanded="false"', b)
        self.assertIn('id="nx_leg_body" hidden', b)
        self.assertIn('data-leg="internet"', b)
        self.assertIn('data-leg="grid"', b)
        self.assertIn('data-leg="hydro"', b)
        self.assertIn('data-leg="dc"', b)
        self.assertIn("Live: U.S., Europe, GB, Nordic", b)
        self.assertNotIn("Live line status:", b)
        root = Path(__file__).resolve().parents[1] / "netmap_static"
        css, js = (root / "net.css").read_text(), (root / "net.js").read_text()
        self.assertIn("function leg(", js)
        self.assertIn("function key(", js)
        self.assertIn('lv.textContent = "Live: U.S., "', js)
        self.assertNotIn("Live line status:", js)
        self.assertIn(".nx-leg-btn", css)
        self.assertIn("bottom:calc(66px + env(safe-area-inset-bottom))", css)  # phone: above All networks / Grid details
        self.assertIn(".nx-leg [hidden]{display:none!important}", css)
        # later rules must not park the legend at the top of the map
        self.assertNotIn(".nx-leg{top:calc(146px + env(safe-area-inset-top));bottom:auto;left:50%", css.replace(" ", ""))
        self.assertNotIn(".nx-leg{bottom:auto;top:calc(104px + env(safe-area-inset-top));left:50%", css.replace(" ", ""))

    def test_attrib_is_collapsed(self):
        """pt1831u: map credits stay a collapsed info button with an X; they never auto-expand or sit mid-map."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "netmap_static"
        css, js = (root / "net.css").read_text(), (root / "net.js").read_text()
        credits = (
            "OpenFreeMap", "OpenMapTiles", "OpenStreetMap contributors",
            "IODA", "PeeringDB", "NOAA OCM", "FCC ASR", "ODbL",
        )
        for s in credits:
            self.assertIn(s, js)
        self.assertIn("function bindAttrib(", js)
        self.assertIn("nx-attrib-x", js)
        self.assertIn("nx-attrib-open", js)
        self.assertIn("setOpen(!on)", js)
        self.assertIn('el.removeAttribute("open")', js)
        self.assertIn("MutationObserver", js)
        self.assertNotIn('classList.remove("maplibregl-compact-show"); }, 1500)', js)
        self.assertIn(".nx-attrib-x", css)
        self.assertIn(".nx-attrib-open", css)
        self.assertIn("maplibregl-compact:not(.nx-attrib-open) .maplibregl-ctrl-attrib-inner{display:none!important}", css)
        self.assertNotIn("body.nx-sky .maplibregl-ctrl-bottom-right{bottom:196px}", css)
        self.assertIn("body.nx-sky .maplibregl-ctrl-bottom-right{bottom:0;right:0}", css)

    def test_asset_version_is_content_hash(self):
        """Asset ?v= is a short content hash, not mtime, so Cloudflare never reuses a stale immutable URL."""
        import hashlib, netmap, netpages
        from pathlib import Path
        root = Path(APP) / "netmap_static"
        css, js = (root / "net.css").read_bytes(), (root / "net.js").read_bytes()
        want_css = hashlib.md5(css).hexdigest()[:12]
        want_js = hashlib.md5(js).hexdigest()[:12]
        self.assertRegex(want_css, r"^[0-9a-f]{12}$")
        self.assertNotEqual(want_css, want_js)
        self.assertEqual(netmap._v("net.css"), want_css)
        self.assertEqual(netmap._v("net.js"), want_js)
        self.assertEqual(netmap._v("does-not-exist.css"), "0")
        html = netpages.handle_get("/grid", {})[1]
        self.assertIn(f"net.css?v={want_css}", html)
        self.assertIn(f"net.js?v={want_js}", html)
        self.assertNotRegex(html, r"net\.css\?v=\d{9,}")

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
        self.assertEqual(len(full["groups"]), 9)
        self.assertEqual(g["iss"]["shown"], 0)
        self.assertIn("iss", g)
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
        for s in ('id="nx_mode"', 'data-m="sky"', 'id="nx_sf"', 'id="nx_sw"', 'id="nx_ss"', 'data-g="iss"', 'data-g="debris"', "BN_SATJS", "sha384-"): self.assertIn(s, b)
        self.assertIn('data-g="debris" aria-pressed="false"', b)
        self.assertIn('data-g="ss"', b)
        self.assertIn('data-g="sw"', b)
        self.assertIn('id="nx_sky_labs"', b)
        # pt1832u: restore #128 — constellation chips on; debris / solar system / space weather stay off
        self.assertIn('data-g="iss" aria-pressed="true"', b)
        self.assertIn('data-g="starlink" aria-pressed="true"', b)
        self.assertIn('data-g="ss" aria-pressed="false"', b)
        self.assertIn('data-g="sw" aria-pressed="false"', b)
        self.assertNotIn('data-g="iss" aria-pressed="false"', b)

    def test_sky_spin_layer_path_and_mobile_chip(self):
        # pt1813u: globe auto-rotate, constellations layer in small-to-Starlink, two-orbit path, compact mobile chip
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "netmap_static"
        js = (root / "net.js").read_text()
        css = (root / "net.css").read_text()
        self.assertIn("function skySpinStart", js)
        self.assertIn("function layerIn", js)
        self.assertIn('if (a.id === "starlink") return 1', js)
        self.assertIn("function launchLayerIn", js)
        self.assertIn("__nxLaunchLayerIn", js)
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


    def test_sky_true_scale_and_learn_panel(self):
        # pt1814u: true-altitude 3D layer, GEO zoom, learn panel with licensed images, no Sky chip status dot
        from pathlib import Path
        import netmap, json
        root = Path(__file__).resolve().parents[1] / "netmap_static"
        js = (root / "net.js").read_text()
        css = (root / "net.css").read_text()
        learn = json.loads((root / "learn.json").read_text())
        self.assertIn("function globePos", js)
        self.assertIn("sats3d", js)
        self.assertIn("35786", js)
        self.assertIn("function skyPick", js)
        self.assertIn("nx-learn-panel", js)
        self.assertIn("setMinZoom(-2)", js)
        self.assertIn('className = "nx-chip"', js)
        self.assertIn("/api/netmap/learn.json", js)
        self.assertIn("nx-learn-panel", css)
        self.assertIn("body.nx-sky .nx-chip i", css)
        added = css.split("pt1814u")[-1]
        self.assertNotIn("#FFC21A", added)
        self.assertNotIn("yellow", added.lower())
        for gid in ("starlink", "gps", "glonass", "galileo", "beidou", "iridium", "oneweb", "goes"):
            self.assertIn(gid, learn)
            self.assertTrue(learn[gid]["sources"])
            for s in learn[gid]["sources"]:
                self.assertTrue(s["url"].startswith("http"))
        gal = learn["galileo"]
        self.assertIn("CC BY-SA 3.0 IGO", gal["credit"])
        self.assertIn("Resized from the original", gal["credit"])
        self.assertIn("creativecommons.org/licenses/by-sa/3.0/igo", gal["license_url"])
        for rec in learn.values():
            if rec.get("image"):
                name = rec["image"].split("?")[0].split("/")[-1]
                self.assertTrue((root / "learn" / name).is_file() or (root / "learn" / (name + ".b64")).is_file(), name)
        code, body, *rest = netmap.handle_get("/api/netmap/learn.json")
        self.assertEqual(code, 200)
        self.assertIn(b"starlink", body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode())
        code, img, ctype = netmap.handle_get("/api/netmap/learn/gps.jpg")
        self.assertEqual(code, 200)
        self.assertIn("image", ctype)
        self.assertEqual(img[:2], b"\xff\xd8")
        self.assertEqual(netmap.handle_get("/api/netmap/learn/../net.js")[0], 404)
        self.assertEqual(netmap.handle_get("/api/netmap/learn/nope.jpg")[0], 404)


    def test_sky_3d_retries_without_idle(self):
        # 3D layer must retry if style is not ready; waiting only on map "idle" never installed sats3d (startPulse keeps idle from firing)
        from pathlib import Path
        js = (Path(__file__).resolve().parents[1] / "netmap_static" / "net.js").read_text()
        self.assertIn("function sky3dRetry", js)
        self.assertIn("function sky3dEnsure", js)
        self.assertIn("startPulse() can keep idle from firing", js)
        self.assertIn("if (!SKY.alt3d && !SKY._3dFail) sky3dEnsure()", js)
        self.assertNotIn('map.once("idle", function () { if (SKY.on) sky3dEnsure(); })', js)

    def test_iss_only_from_stations_and_learn_card(self):
        import netsky, json, time, netmap
        from unittest import mock
        from pathlib import Path
        stations = CSV + "ISS (ZARYA),1998-067A,2026-11-22T12:00:00.123456,15.49,0.0007,51.6,10.0,90.0,270.0,0,U,25544,999,100,0.0001,0,0\n" + \
                   "CSS (TIANHE),2021-035A,2026-11-22T12:00:00.123456,15.59,0.001,41.4,10.0,90.0,270.0,0,U,48274,999,100,0.0001,0,0\n"
        sp = os.path.join(self.d, "stations.csv"); open(sp, "w").write(stations)
        def fake(gid, grp):
            if gid == "iss": return (sp, time.time(), None)
            if gid in ("starlink", "gps"): return (self.p, time.time(), None)
            return (None, None, "HTTPError")
        with mock.patch.object(netsky, "_file", fake):
            payload = json.loads(netsky.sky(False))
        g = {x["id"]: x for x in payload["groups"]}
        self.assertEqual(g["iss"]["total"], 1)
        self.assertEqual(g["iss"]["shown"], 1)
        iss = [s for s in payload["sats"] if s[1] == 25544]
        self.assertEqual(len(iss), 1)
        self.assertTrue(any("ISS" in (s[10] or "") for s in iss))
        self.assertFalse(any(s[1] == 48274 for s in payload["sats"]))
        learn = json.loads((Path(APP) / "netmap_static" / "learn.json").read_text())
        self.assertIn("iss", learn)
        self.assertTrue(learn["iss"]["image"].endswith("iss.jpg"))
        self.assertTrue(learn["iss"]["sources"])
        code, img, ctype = netmap.handle_get("/api/netmap/learn/iss.jpg")
        self.assertEqual(code, 200)
        self.assertIn("image", ctype)
        self.assertEqual(img[:2], b"\xff\xd8")

    def test_debris_is_decimated_and_routed(self):
        import netsky, json, time, netmap
        from unittest import mock
        many = CSV.split("\n")[0] + "\n" + "".join(
            f"DEB {i},2020-001A,2026-11-22T12:00:00.000000,15.06,0.0001,53.0,10.0,90.0,270.0,0,U,{50000+i},999,100,0.0001,0,0\n" for i in range(60))
        dp = os.path.join(self.d, "debris.csv"); open(dp, "w").write(many)
        def fake(gid, url):
            return (dp, time.time(), None) if "fengyun-1c-debris" in url or gid == "fengyun-1c-debris" else (None, None, "HTTPError")
        with mock.patch.object(netsky, "_fetch", fake):
            full = json.loads(netsky.debris(False)); lite = json.loads(netsky.debris(True))
        self.assertEqual(full["step"], 2); self.assertEqual(lite["step"], 6)
        fy = {g["id"]: g for g in full["groups"]}["fengyun-1c-debris"]
        self.assertEqual(fy["total"], 60)
        self.assertEqual(fy["shown"], 30)
        self.assertEqual({g["id"]: g for g in lite["groups"]}["fengyun-1c-debris"]["shown"], 10)
        with mock.patch.object(netsky, "debris_cached", lambda lite: b'{"lite":%d}' % lite):
            self.assertEqual(netmap.handle_get("/api/netmap/debris", {"lite": ["1"]})[1], b'{"lite":1}')
            self.assertEqual(netmap.handle_get("/api/netmap/debris", {})[1], b'{"lite":0}')

    def test_solar_system_and_cad_payloads(self):
        import netsky, netmap, json
        from unittest import mock
        from datetime import datetime, timezone
        when = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
        def hz(command, center, when):
            tables = {
                ("-31", "500@399"): {"delta_au": 173.2, "deldot_km_s": 23.1, "light_min": 1440.5, "time": "2026-Nov-24 18:00"},
                ("-31", "500@10"): {"delta_au": 172.4, "deldot_km_s": 16.9, "light_min": 1434.0, "time": "2026-Nov-24 18:00"},
                ("-32", "500@399"): {"delta_au": 145.0, "deldot_km_s": 32.7, "light_min": 1206.3, "time": "2026-Nov-24 18:00"},
                ("-32", "500@10"): {"delta_au": 144.5, "deldot_km_s": 15.0, "light_min": 1202.1, "time": "2026-Nov-24 18:00"},
                ("-143205", "500@399"): {"delta_au": 0.856, "deldot_km_s": 8.2, "light_min": 7.12, "time": "2026-Nov-24 18:00"},
                ("-143205", "500@10"): {"delta_au": 1.369, "deldot_km_s": -6.36, "light_min": 11.38, "time": "2026-Nov-24 18:00"},
            }
            return tables[(command, center)]
        with mock.patch.object(netsky, "_horizons_observer", hz), mock.patch.object(netsky, "datetime") as dt:
            # keep datetime class methods used at import; only now() needs a stub if we don't patch it.
            pass
        with mock.patch.object(netsky, "_horizons_observer", hz):
            ss = netsky.solar_system()
        self.assertTrue(ss["ok"])
        by = {o["id"]: o for o in ss["objects"]}
        self.assertEqual(set(by), {"roadster", "voyager1", "voyager2"})
        self.assertAlmostEqual(by["voyager1"]["earth"]["au"], 173.2, places=3)
        self.assertEqual(by["voyager1"]["launch"], "1977-09-05")
        self.assertIn("interstellar", by["voyager1"]["status"].lower())
        self.assertIn("nasa.gov", by["voyager1"]["source_url"])
        self.assertTrue(by["roadster"]["ok"])
        self.assertIn("horizons", by["roadster"]["source_url"])
        self.assertGreater(by["voyager1"]["earth"]["km"], 20_000_000_000)
        cad_fixture = {"fields": ["des", "cd", "dist", "h", "diameter", "fullname"],
                       "data": [["2026 VQ5", "2026-Nov-25 21:21", "0.013432313511248", "23.915", None, "(2026 VQ5)"],
                                ["P/2026 A1", "2026-Dec-10 04:00", "0.04", "18.0", 1.2, "Comet P/2026 A1"]]}
        with mock.patch.object(netsky, "_j", lambda url: cad_fixture):
            netsky._MEM.pop("cad", None)
            cad = netsky.cad()
        self.assertTrue(cad["ok"]); self.assertEqual(cad["count"], 2)
        a, c = cad["objects"]
        self.assertAlmostEqual(a["dist_ld"], a["dist_km"] / netsky.LD_KM, places=3)
        self.assertIsNone(a["diameter_km"]); self.assertTrue(a["size_est_km"]); self.assertIn("albedo", a["size_note"])
        self.assertEqual(c["diameter_km"], 1.2); self.assertIsNone(c["size_est_km"])
        self.assertTrue(a["source_url"].startswith("https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html"))
        with mock.patch.object(netsky, "solar_system", lambda: {"ok": True, "objects": []}):
            code, body = netmap.handle_get("/api/netmap/ss")[:2]
        self.assertEqual(code, 200); self.assertTrue(body["ok"])
        with mock.patch.object(netsky, "cad", lambda: {"ok": True, "objects": []}):
            self.assertEqual(netmap.handle_get("/api/netmap/cad")[0], 200)
        self.assertAlmostEqual(netsky.size_from_h(24.7), 1329.0 * (10 ** (-24.7 / 5.0)) / (0.14 ** 0.5), places=6)

    def test_sky_objects_client_hooks(self):
        from pathlib import Path
        root = Path(APP) / "netmap_static"
        js = (root / "net.js").read_text()
        css = (root / "net.css").read_text()
        for s in ("function debrisLoad", "function ssLoad", "function skyLabs", "function skyChipLabels",
                  'SKYC = { iss: "#FFFFFF"', 'g === "debris"', "/api/netmap/ss", "/api/netmap/cad", "/api/netmap/debris"):
            self.assertIn(s, js)
        self.assertIn("nx-ss-pin", css)
        self.assertIn("Tap a chip to show a layer", js)
        self.assertIn('SKY.show[g.id] = g.id !== "debris"', js)
        self.assertNotIn('SKY.groups.forEach(function (g) { SKY.show[g.id] = false; })', js)
        self.assertNotIn("function prog(", js.split("function glProg")[-1] if "function glProg" in js else "")
        self.assertIn("function glProg", js)
        self.assertEqual(js.count("function debrisLoad"), 1)
        self.assertIn("nx-ss", css)
        self.assertIn("nx-cad", css)
        added = css.split("solar-system inset")[-1]
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


_BN_UNITS_PROBE = """
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
const cut = src.indexOf("\\n(function () {");
if (cut < 0) { console.error("no main iife"); process.exit(1); }
const store = {};
const w = {
  localStorage: { getItem: (k) => store[k] || null, setItem: (k, v) => { store[k] = String(v); } },
  dispatchEvent: () => {}, addEventListener: () => {},
  CustomEvent: function (n, i) { this.type = n; this.detail = i && i.detail; },
  document: { getElementById: () => null, readyState: "complete", addEventListener: () => {} }
};
w.window = w;
const ctx = { window: w, document: w.document, console };
vm.createContext(ctx);
vm.runInContext(src.slice(0, cut), ctx);
const U = ctx.window.BNUnits;
function eq(a, b, m) { if (a !== b) { console.error("FAIL", m, JSON.stringify(a), "want", JSON.stringify(b)); process.exit(2); } }
eq(U.system(), "imperial", "default");
eq(U.isImperial(), true, "isImperial");
eq(U.fmtSpeed(7.66, "s"), "4.76 mi/s", "speed");
eq(U.fmtAlt(400), "249 mi", "iss alt");
eq(U.fmtDist(20200), "12,552 mi", "gps");
eq(U.fmtDist(35786), "22,236 mi", "geo");
eq(U.fmtLenM(100), "328 ft", "tower");
eq(U.fmtFt(1065), "1,065 ft", "lake");
eq(U.fmtSizeKm(0.5), "1,640 ft", "size m");
U.set("metric");
eq(U.system(), "metric", "metric");
eq(U.fmtSpeed(7.66, "s"), "7.66 km/s", "speed km");
eq(U.fmtAlt(400), "400 km", "alt km");
eq(U.fmtDist(20200), "20,200 km", "gps km");
eq(U.fmtLenM(100), "100 m", "tower m");
eq(U.fmtFt(1065), "325 m", "lake m");
eq(store["bn-units"], "metric", "persist");
console.log("UNITS_OK");
"""

class GridUnits(unittest.TestCase):
    def test_units_toggle(self):
        """pt1827u: Metric/Imperial pill defaults to imperial, persists, and formats speeds/distances/altitudes."""
        import netpages, subprocess, tempfile
        from pathlib import Path
        b = netpages.handle_get("/grid", {})[1]
        if isinstance(b, bytes):
            b = b.decode("utf-8")
        self.assertIn('id="nx_units"', b)
        self.assertIn('aria-label="Units"', b)
        self.assertIn('data-u="imperial" aria-pressed="true"', b)
        self.assertIn('data-u="metric" aria-pressed="false"', b)
        self.assertIn(">mi</button>", b)
        self.assertIn(">km</button>", b)
        root = Path(APP) / "netmap_static"
        js, css = (root / "net.js").read_text(), (root / "net.css").read_text()
        self.assertIn("window.BNUnits", js)
        self.assertIn("fmtSpeed", js)
        self.assertIn("fmtDist", js)
        self.assertIn("fmtAlt", js)
        self.assertIn('new CustomEvent("bn-units"', js)
        self.assertIn('localStorage.setItem(KEY, imperial ? "imperial" : "metric")', js)
        self.assertIn("window.BNUnits.fmtAlt(o.p[2])", js)
        self.assertIn('window.BNUnits.fmtSpeed(o.p[3], "s")', js)
        self.assertIn("window.BNUnits.fmtDist(km)", js)
        self.assertIn("window.BNUnits.fmtFt(lv.ft)", js)
        self.assertIn("window.BNUnits.fmtLenM(r[3])", js)
        self.assertIn('document.addEventListener("bn-units"', js)
        self.assertIn(".nx-units", css)
        added = css.split("pt1827u")[-1]
        self.assertNotIn("#FFC21A", added)
        self.assertNotIn("yellow", added.lower())
        script = Path(tempfile.gettempdir()) / "bn_units_probe.js"
        script.write_text(_BN_UNITS_PROBE)
        r = subprocess.run(["node", str(script), str(root / "net.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + "\n" + r.stderr)
        self.assertIn("UNITS_OK", r.stdout)


class NoDuplicateFunctions(unittest.TestCase):
    def test_net_js_declares_each_function_once(self):
        """Regression (Nov 24 2026): a second `function prog(...)` (sky shaders) replaced the loader's prog() and broke map setup."""
        import collections
        js = open(os.path.join(APP, "netmap_static", "net.js"), encoding="utf-8").read()
        c = collections.Counter(re.findall(r"^  function (\w+)\(", js, re.M))
        self.assertEqual([k for k, n in c.items() if n > 1], [])

