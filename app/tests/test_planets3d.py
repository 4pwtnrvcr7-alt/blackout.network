"""Solar explorer planet textures + Moon/Mars landing sites (pt1837u, Nov 24 2026)."""
import os, sys, json, re, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"
STATIC = os.path.join(APP, "netmap_static")
import netmap, netpages

BANNED = ("verified", "before the news")
YELLOW = ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#ff9900", "#ffc21a")

class Planets3d(unittest.TestCase):
    def test_routes_and_assets(self):
        html = netpages.handle_get("/grid", {})[1]
        if isinstance(html, bytes): html = html.decode("utf-8", "replace")
        self.assertIn("BN_PLANETS3D", html)
        self.assertIn("planets3d.js", html)
        code, body, ctype = netmap.handle_get("/api/netmap/planets3d.js")
        self.assertEqual(code, 200)
        self.assertIn("javascript", ctype)
        self.assertIn(b"BNPlanets", body)
        self.assertIn(b"openSite", body)
        for name, want in (
            ("planets/moon.jpg", "image/jpeg"),
            ("planets/mars.jpg", "image/jpeg"),
            ("planets/earth.jpg", "image/jpeg"),
            ("planets/jupiter.jpg", "image/jpeg"),
            ("planets/saturn.jpg", "image/jpeg"),
            ("planets/saturn_hex.webp", "image/webp"),
            ("planets/earth_night.jpg", "image/jpeg"),
            ("planets/sites.json", "application/json"),
            ("planets/CREDITS.txt", "text/plain"),
        ):
            c, b, t = netmap.handle_get("/api/netmap/" + name)
            self.assertEqual(c, 200, name)
            self.assertIn(want.split("/")[1] if "plain" not in want else "text/plain", t, (name, t))
            self.assertGreater(len(b), 100, name)
        self.assertEqual(netmap.handle_get("/api/netmap/planets/../net.js")[0], 404)
        self.assertEqual(netmap.handle_get("/api/netmap/planets/nope.jpg")[0], 404)

    def test_apollo11_and_sites(self):
        c, body, t = netmap.handle_get("/api/netmap/planets/sites.json")
        self.assertEqual(c, 200)
        d = json.loads(body)
        a11 = next(s for s in d["moon"] if s["id"] == "apollo11")
        self.assertAlmostEqual(a11["lat"], 0.67416, places=4)
        self.assertAlmostEqual(a11["lon"], 23.47314, places=4)
        self.assertIn("Armstrong", a11["crew"])
        self.assertIn("Tranquility", a11["place"])
        self.assertTrue(a11["source"].startswith("https://"))
        names = {s["id"] for s in d["moon"]}
        for i in ("apollo11","apollo12","apollo14","apollo15","apollo16","apollo17",
                  "luna9","luna16","luna17","change3","change4","change5","change6",
                  "chandrayaan3","slim","im1"):
            self.assertIn(i, names, i)
        mnames = {s["id"] for s in d["mars"]}
        for i in ("viking1","viking2","pathfinder","spirit","opportunity","phoenix",
                  "curiosity","insight","perseverance","zhurong"):
            self.assertIn(i, mnames, i)
        feat = {s["id"]: s for s in d["features"]}
        self.assertIn("grs", feat)
        self.assertIn("hexagon", feat)
        self.assertLess(feat["grs"]["lat"], 0)
        v2 = next(s for s in d["mars"] if s["id"] == "viking2")
        self.assertGreater(v2["lon"], 180)  # 225.7 E, Utopia

    def test_hook_and_copy_rules(self):
        js = open(os.path.join(STATIC, "solar3d.js"), encoding="utf-8").read()
        self.assertIn("attachPlanets", js)
        self.assertIn("BN_PLANETS3D", js)
        self.assertIn("BNPlanets.info", js)
        self.assertIn("BNPlanets.focusDist", js)
        self.assertIn("cancelFly", js)
        self.assertIn("o !== SEL", js)
        self.assertIn("BNPlanets.tick", js)
        self.assertIn(".s3-labs{", js)
        self.assertIn("pointer:coarse", js)
        nl = open(os.path.join(os.path.dirname(STATIC), "netlaunch.py"), encoding="utf-8").read()
        self.assertIn("_fetch_ll2", nl)
        self.assertIn("_kick_bg", nl)
        self.assertIn("_fetch_ll2(28)", nl)
        self.assertIn("_fetch_ll2(45)", nl)
        pjs = open(os.path.join(STATIC, "planets3d.js"), encoding="utf-8").read()
        self.assertNotIn("ConeGeometry", pjs)
        self.assertIn("RingGeometry", pjs)
        self.assertIn("tick:", pjs)
        self.assertIn("addAurora", pjs)
        self.assertIn("AdditiveBlending", pjs)
        self.assertIn("illustrative shader", pjs.lower())
        self.assertIn("addAtmosphere", pjs)
        self.assertIn("fixLights", pjs)
        self.assertIn("earth_night.jpg", pjs)
        self.assertIn("fixCraftDots", pjs)
        self.assertIn("model.visible = selected", pjs)
        self.assertIn("focusDir", pjs)
        self.assertIn("metalness: 0", pjs)
        self.assertIn("MeshLambertMaterial", pjs)
        self.assertNotIn("metalness: isEarth ? 0.14", pjs)
        self.assertNotIn("TorusGeometry", pjs)
        self.assertIn("AmbientLight(0xffffff, 0.045)", js)
        self.assertIn("BNPlanets.focusDir", js)
        self.assertIn("BNUnits", pjs)
        self.assertIn("isImperial", pjs)
        blob = (js + pjs + open(os.path.join(STATIC, "planets", "sites.json"), encoding="utf-8").read()).lower()
        for w in BANNED:
            self.assertNotIn(w, blob, w)
        # 'first' is banned in public copy
        self.assertNotRegex(blob, r"\bfirst\b")
        low = pjs.lower()
        for c in YELLOW:
            self.assertNotIn(c, low, c)
        self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", pjs, flags=re.S).lower())
        credits = open(os.path.join(STATIC, "planets", "CREDITS.txt"), encoding="utf-8").read()
        self.assertIn("Public domain", credits)
        self.assertIn("PIA07782", credits)
        self.assertIn("CGI Moon Kit", credits)
        self.assertIn("MDIM", credits)
        self.assertIn("Black Marble", credits)
        self.assertNotIn("non-commercial", credits.lower().replace("no non-commercial sources", ""))

    def test_textures_are_clean_jpegs(self):
        from PIL import Image
        from io import BytesIO
        for name, min_w in (("moon.jpg", 3000), ("mars.jpg", 3000), ("jupiter.jpg", 2000), ("earth.jpg", 2000), ("earth_night.jpg", 2000)):
            c, b, t = netmap.handle_get("/api/netmap/planets/" + name)
            self.assertEqual(c, 200)
            im = Image.open(BytesIO(b))
            self.assertGreaterEqual(im.size[0], min_w, name)
            self.assertEqual(im.size[0], im.size[1] * 2, name)  # 2:1 equirectangular
            # no EXIF/XMP
            self.assertFalse(getattr(im, "info", {}).get("exif"))
            self.assertFalse(any("xml" in k.lower() or "exif" in k.lower() for k in im.info))

if __name__ == "__main__":
    unittest.main()
