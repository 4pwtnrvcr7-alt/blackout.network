"""Sky view Launches chip (Nov 24 2026, pt1824u): LL2 parsing, modeled paths, landing outcome, failure marker, caching rules."""
import os, sys, json, re, shutil, tempfile, unittest, copy
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"
FIX = os.path.join(APP, "tests", "fixtures", "ll2_launch_window.json")

class Launches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); os.environ["BN_STATE_DIR"] = self.tmp
        os.makedirs(os.path.join(self.tmp, "bn_launch")); shutil.copy(FIX, os.path.join(self.tmp, "bn_launch", "ll2_window.json"))
        import netlaunch; self.N = netlaunch; netlaunch._MEM.clear()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def by(self, d, key): return next(l for l in d["launches"] if key in l["name"])

    def test_parse_and_model(self):
        d = self.N.launches()
        self.assertEqual(d["count"], 3); self.assertIsNone(d["error"])
        self.assertIn("not telemetry", d["modeled"])
        a = self.by(d, "USSF-266")   # polar from Vandenberg, droneship OCISLY 574 km downrange, landed
        self.assertAlmostEqual(a["azimuth"], 180.0, delta=1)
        self.assertEqual(a["landing"]["where"], "OCISLY"); self.assertIs(a["landing"]["success"], True)
        self.assertEqual(a["timeline_source"], "LL2 mission timeline")
        lon, lat = a["booster"][-1][:2]; self.assertAlmostEqual(lat, 34.632 - 574 / 111.2, delta=0.3); self.assertEqual(a["booster"][-1][2], 0)
        self.assertEqual(a["ascent"][0][:3], [-120.611, 34.632, 0])
        alts = [p[2] for p in a["ascent"]]; self.assertTrue(all(b >= x for x, b in zip(alts, alts[1:])))
        self.assertTrue(60000 <= next(p[2] for p in a["ascent"] if p[3] >= 149) <= 80000)   # staging ~65-80 km
        ks = [b["k"] for b in a["labels"]]
        for k in ("liftoff", "maxq", "sep", "seco", "land", "orbit"): self.assertIn(k, ks)
        sep = next(b for b in a["labels"] if b["k"] == "sep"); self.assertIn("T+2:29", sep["text"])
        r = self.by(d, "NROL-136")   # return to launch site LZ-4: booster ends at the LL2 coordinates
        self.assertEqual(r["landing"]["type"], "RTLS")
        self.assertAlmostEqual(r["booster"][-1][0], -120.615193, places=3); self.assertAlmostEqual(r["booster"][-1][1], 34.632994, places=3)
        s = self.by(d, "Shenzhou 24")
        self.assertEqual(s["booster"], []); self.assertIsNone(s["landing"]); self.assertAlmostEqual(s["inclination"], 41.47)

    def test_failure_and_landing_failure(self):
        j = json.load(open(FIX)); r = copy.deepcopy(j["results"][0])
        r["status"] = {"abbrev": "Failure", "name": "Launch Failure"}; r["failreason"] = ""
        r["rocket"]["launcher_stage"][0]["landing"]["success"] = False
        m = self.N.model(r)
        ks = [b["k"] for b in m["labels"]]; self.assertIn("fail", ks); self.assertIn("landfail", ks)
        self.assertIn("not published", next(b for b in m["labels"] if b["k"] == "fail")["text"])

    def test_durations(self):
        self.assertEqual(self.N._dur("PT2M26S"), 146); self.assertEqual(self.N._dur("-PT3S"), -3); self.assertEqual(self.N._dur("P0D"), 0)
        self.assertEqual(self.N._dur("PT1H6M"), 3960)

    def test_route_and_no_network_when_fresh(self):
        import netmap, urllib.request
        real = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched while cache fresh"))
        try:
            code, body, ct = netmap.handle_get("/api/netmap/launches")
        finally:
            urllib.request.urlopen = real
        self.assertEqual((code, ct), (200, "application/json")); self.assertEqual(json.loads(body)["count"], 3)
        self.assertEqual(netmap.handle_get("/api/netmap/launches.js")[0], 200)
        self.assertGreaterEqual(self.N.MAX_AGE, 600)   # LL2 free tier ~15 calls/h

    def test_js_rules(self):
        js = open(os.path.join(APP, "netmap_static", "launches.js"), encoding="utf-8").read()
        net = open(os.path.join(APP, "netmap_static", "net.js"), encoding="utf-8").read()
        mine = set(re.findall(r"function (\w+)\s*\(", js)); theirs = set(re.findall(r"function (\w+)\s*\(", net))
        self.assertEqual(mine & theirs, set())
        self.assertIn("not telemetry", js)
        low = re.sub(r"/\*.*?\*/", "", js.lower(), flags=re.S)
        self.assertNotIn("yellow", low)
        for c in ("#f5d547", "#f5a524", "#ffcc00", "#facc15"): self.assertNotIn(c, low)
        self.assertEqual(low.count("<img"), 1)   # one image slot: the per-rocket Commons photo, with its credit
        self.assertIn("d.rocket_photo", js); self.assertNotIn("d.image.url", js)   # LL2 images are not used
        self.assertIn("lcFeatured", js); self.assertIn("lim = z < base + 0.9 ? 5", js)   # next 5 + live when zoomed out
        import netpages
        self.assertIn("/api/netmap/launches.js", netpages.handle_get("/grid", {})[1])
        self.assertIn('aria-pressed", LC.on ? "true" : "false"', js)
        self.assertIn("window.__nxLaunchLayerIn = lcLayerIn", js)
        self.assertIn("LC.reveal", js)

    def test_details_and_image_licences(self):
        import netmap
        d = self.N.launches(); lid = self.by(d, "USSF-266")["id"]
        code, body = netmap.handle_get("/api/netmap/launches/" + lid)[:2]
        self.assertEqual(code, 200)
        self.assertEqual(body["boosters"][0]["serial"], "B1081"); self.assertEqual(body["rocket"]["launch_cost_usd"], 52000000)
        self.assertIsNone(body["image"])   # SpaceX images in LL2 are CC BY-NC 2.0 / Unknown: never shown
        self.assertEqual(netmap.handle_get("/api/netmap/launches/00000000-0000-0000-0000-000000000000")[0], 404)
        ok = lambda n: self.N.image_ok({"image_url": "https://x/y.jpg", "license": {"name": n}})
        for n in ("CC BY-NC 2.0", "Unknown", "ESA Standard Licence", "Roscosmos Image Use Policy", "CC BY-ND 4.0", ""): self.assertIsNone(ok(n), n)
        for n in ("Public Domain", "CC BY 2.0", "CC BY-SA 4.0", "CC0 1.0", "NASA Image and Media Guidelines"): self.assertIsNotNone(ok(n), n)

    def test_geo_ring_removed_and_track_js(self):
        net = open(os.path.join(APP, "netmap_static", "net.js"), encoding="utf-8").read()
        self.assertNotIn("layer.ring.length / 3", net)   # pt1834u: no always-on GEO ring
        self.assertIn("window.__nxSky = SKY", net)
        tr = open(os.path.join(APP, "netmap_static", "skytrack.js"), encoding="utf-8").read()
        theirs = set(re.findall(r"function (\w+)\s*\(", net))
        self.assertEqual(set(re.findall(r"function (\w+)\s*\(", tr)) & theirs, set())
        import netpages
        self.assertIn("/api/netmap/skytrack.js", netpages.handle_get("/grid", {})[1])

    def test_rocket_photos(self):
        import netmap, base64
        man = json.load(open(os.path.join(APP, "netmap_static", "rockets", "rockets.json"), encoding="utf-8"))
        self.assertGreaterEqual(len(man), 15)
        for k, m in man.items():
            self.assertRegex(k, r"^[a-z0-9]+$")
            self.assertIsNotNone(self.N._OK_LIC.match(m["license"]), k)   # PD / CC0 / CC BY / CC BY-SA only
            self.assertNotRegex(m["license"].lower(), r"\bnc\b|nd\b|non-?commercial")
            self.assertTrue(m["source_url"].startswith("https://commons.wikimedia.org/wiki/File:"), k)
            self.assertTrue(m["author"] and m["pictured"], k)
            code, body, ct = netmap.handle_get("/api/netmap/rockets/" + m["file"])
            self.assertEqual((code, ct), (200, "image/jpeg")); self.assertEqual(body[:2], b"\xff\xd8")
        self.assertEqual(netmap.handle_get("/api/netmap/rockets/../netmap.py")[0], 404)
        self.assertEqual(self.N.rocket_photo("Falcon 9 Block 5")["key"], "falcon9")
        self.assertEqual(self.N.rocket_photo("Falcon Heavy")["key"], "falconheavy")
        self.assertEqual(self.N.rocket_photo("Long March 2F", "Long March 2")["key"], "longmarch")
        self.assertIsNone(self.N.rocket_photo("Ariane 62"))   # no usable photo -> none shown
        d = self.N.launches(); lid = self.by(d, "USSF-266")["id"]
        self.assertEqual(netmap.handle_get("/api/netmap/launches/" + lid)[1]["rocket_photo"]["key"], "falcon9")

    def test_chip_frame_then_hide(self):
        tr = open(os.path.join(APP, "netmap_static", "skytrack.js"), encoding="utf-8").read()
        js = open(os.path.join(APP, "netmap_static", "launches.js"), encoding="utf-8").read()
        self.assertIn("Tap again to hide", tr); self.assertIn("}, true);", tr)   # capture listener runs before net.js toggles
        self.assertIn('T.framed() !== "launches"', js)
        self.assertIn("selecting a launch turns the Launches chip back on", js)

if __name__ == "__main__":
    unittest.main()
