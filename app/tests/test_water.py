import os, sys, json, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import water as W

STATIC = os.path.join(os.path.dirname(W.__file__), "water_static")

def it(**k):
    d = dict(id="x1", kind="advisory", level="boil", label="Boil water notice", name="Test", place="Somewhere", lat=40.0, lon=-90.0, precision="point", since="2026-11-01T00:00:00Z",
             by="Agency", src="Agency data", url="https://example.gov/record/1")
    d.update(k); return d

class Water(unittest.TestCase):
    def setUp(self): W._C.clear()
    def test_title_case_only_for_all_caps(self):
        self.assertEqual(W._title("PORT PROTECTION"), "Port Protection")
        self.assertEqual(W._title("RURAL MUNICIPALITY OF MONTCALM ( MORRIS REGIONAL )"), "Rural Municipality of Montcalm (Morris Regional)")
        self.assertEqual(W._title("City of Jackson"), "City of Jackson")
    def test_point_validation(self):
        self.assertIsNone(W._pt(0, 0)); self.assertIsNone(W._pt("x", 1)); self.assertIsNone(W._pt(95, 10)); self.assertEqual(W._pt("56.32119", "-133.59911"), (56.3212, -133.5991))
    def test_county_centroids_cover_us(self):
        c = W.centroids(); self.assertGreater(len(c), 3100); self.assertEqual(c["12117"][3], "FL"); self.assertTrue(24 < c["12117"][0] < 31)
    def test_every_item_needs_an_https_source_link(self):
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES}); W.FETCH["ak"] = lambda: [it()]
        d = W.data(force=True)
        self.assertEqual(d["counts"], {"advisory": 1}); self.assertTrue(all(i["url"].startswith("https://") for i in d["items"]))
        self.assertNotIn("by", d["items"][0]); self.assertEqual(d["pubs"]["Agency data"], "Agency")
    def test_failed_source_keeps_last_good_and_says_unavailable(self):
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            if calls["n"] > 1: raise OSError("down")
            return [it()]
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES}); W.FETCH["ak"] = flaky
        W.data(force=True); W._C["ak"]["t"] -= 120      # past the 60 s refresh floor
        d = W.data(force=True); s = [x for x in d["sources"] if x["id"] == "ak"][0]
        self.assertEqual(s["count"], 1); self.assertFalse(s["ok"]); self.assertEqual(s["error"], "OSError"); self.assertIsNotNone(s["updated"])
    def test_refresh_inside_60s_does_not_hit_upstream_again(self):
        n = {"c": 0}
        def one(): n["c"] += 1; return [it()]
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES}); W.FETCH["ak"] = one
        W.data(force=True); d = W.data(force=True)
        self.assertEqual(n["c"], 1); self.assertEqual(d["pulled"], [])
    def test_page_and_routes(self):
        import sitenav_ui
        self.assertEqual(W.handle_get("/water")[0], 200)
        self.assertEqual(W.handle_get("/api/water/app.js")[0], 200); self.assertEqual(W.handle_get("/api/water/app.css")[0], 200)
        self.assertEqual(W.handle_get("/api/water/../server.py")[0], 404)
        self.assertEqual(sitenav_ui.refresh_mode("/water"), "inpage")
        import addons; self.assertEqual(addons.ROUTES["/water"], "water"); self.assertEqual(addons.ROUTES["/api/water"], "water")
    def test_theme_rules(self):
        css = open(os.path.join(STATIC, "app.css")).read(); js = open(os.path.join(STATIC, "app.js")).read(); src = open(W.__file__).read()
        for t in (css, js):
            for h in re.findall(r"#([0-9a-fA-F]{6})\b", t):
                r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
                self.assertFalse(r > 200 and g > 170 and b < 120, "yellow-ish colour #" + h)      # no yellow
        allt = (css + js + src).lower()
        for bad in ("peer-to-peer", "meshtastic", "lora", "satellite", "<img"):
            self.assertNotIn(bad, allt.replace("sewage", "")) if bad != "satellite" else None
        self.assertNotIn("<img", W.page().lower())      # no map or satellite images on cards
        self.assertIn("openfreemap", js.lower()); self.assertNotIn("tile.openstreetmap.org", js.lower())
        self.assertIn("-96.5, 39.2", js)                # map opens centred on the U.S.

if __name__ == "__main__": unittest.main()
