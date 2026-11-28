"""Water layer on /grid: redirects, chips, loader weights unchanged, plant inventory rules."""
import json, os, re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
NET = (APP / "netmap_static" / "net.js").read_text()
WL = (APP / "netmap_static" / "waterlayer.js").read_text()
CSS = (APP / "netmap_static" / "waterlayer.css").read_text()
PY = (APP / "netmap.py").read_text()

class GridWater(unittest.TestCase):
    def test_loader_weights_unchanged(self):
        m = re.search(r"W8\s*=\s*\{[^}]+\}", NET)
        self.assertTrue(m, "W8 missing")
        self.assertEqual(m.group(0).replace(" ", ""), "W8={map:0.3,nets:0.3,out:0.1,dc:0.15,rep:0.15}")
        self.assertNotIn("water:", m.group(0))
        self.assertIn('MAP_ORDER = ["internet", "grid", "sea", "dc", "towers", "hydro", "cloud"]', NET)

    def test_water_is_lazy_and_not_in_boot_order(self):
        self.assertNotIn('"water"', re.search(r"MAP_ORDER = (\[[^\]]+\])", NET).group(1))
        self.assertIn("/api/netmap/water?", WL)
        self.assertIn("/api/water/map", WL)
        self.assertNotIn("/api/water/data", WL)   # advisories load as map markers, not a list panel
        self.assertNotIn("water_plants.json", WL)
        self.assertFalse((APP / "netmap_static" / "water_plants.json").exists(), "no 9.7 MB JSON in the tree")
        self.assertIn("window.__wtHit", WL)
        self.assertIn("window.__wtHit", NET)
        self.assertIn("BNShare", WL)

    def test_no_panel_or_stray_water_button(self):
        self.assertNotIn("nx_water_btn", PY)
        self.assertNotIn('id="nx_water"', PY)
        # #353 hides the old floating button if a stale build still has the markup
        if "nx-water-btn" in CSS:
            self.assertIn("display:none!important", CSS)
        self.assertNotIn("openPanel", WL)
        self.assertNotIn("accountForPanel", WL)
        self.assertNotIn("Loading water data", PY)
        self.assertNotIn("Get the free brief", WL)
        self.assertNotIn("wt-panel", PY)
        self.assertNotIn('id="nx_water"', WL)

    def test_plain_grid_opens_with_only_power_grid_on(self):
        import netmap
        html = netmap.page({})
        self.assertIn('data-k="grid" aria-pressed="true"', html)
        for k in ("internet", "water", "hydro", "cloud", "sea", "towers", "dc"):
            self.assertIn(f'data-k="{k}" aria-pressed="false"', html)
        html_w = netmap.handle_get("/grid/water")[1]
        self.assertIn('data-k="water" aria-pressed="true"', html_w)
        self.assertIn('data-k="grid" aria-pressed="true"', html_w)
        self.assertIn('data-k="internet" aria-pressed="false"', html_w)
        self.assertNotIn("wt-panel", html_w)
        self.assertNotIn('id="nx_water"', html_w)

    def test_advisory_since_is_formatted_in_et(self):
        self.assertIn("function fmtSince", WL)
        self.assertIn("America/New_York", WL)
        self.assertIn("esc(fmtSince(it.since))", WL)
        self.assertNotIn('esc(it.since)', WL)

    def test_no_yellow_in_water_layer(self):
        for t in (WL, CSS, PY):
            # only check the water layer assets and the water legend snippet
            chunk = t
            if t is PY:
                i = t.find('data-leg="water"')
                chunk = t[i:i + 900] if i >= 0 else ""
            for h in re.findall(r"#([0-9a-fA-F]{6})\b", chunk):
                r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
                self.assertFalse(r > 200 and g > 170 and b < 120, "yellow-ish colour #" + h)

    def test_operating_plants_are_blue_circles(self):
        self.assertIn("#4FC3F7", WL)
        self.assertIn("#4FC3F7", PY)
        self.assertNotIn("#2EE6D6", WL)
        self.assertNotIn("#C084FC", WL)
        self.assertNotIn("icon-image", WL)
        self.assertNotIn("wt-dw", WL)
        self.assertIn('type: "circle"', WL)
        self.assertIn("#FF3B3B", WL)   # do-not-drink, same red as other layers
        self.assertIn("#FFA040", WL)   # boil / violation, same watch colour as other layers
        self.assertIn("Plant operating", PY)
        self.assertIn("id=\"nx_card\"", PY)

    def test_redirects_and_grid_route(self):
        import water, netmap, netpages
        r = water.handle_get("/water")
        self.assertEqual(r[0], 301)
        self.assertEqual(r[3]["Location"], "/grid/water")
        r = water.handle_get("/water/akabc123defg")
        self.assertEqual(r[0], 301)
        self.assertEqual(r[3]["Location"], "/grid/water/akabc123defg")
        code, html, ctype = netmap.handle_get("/grid/water")
        self.assertEqual(code, 200)
        self.assertIn("text/html", ctype)
        self.assertIn('data-k="water"', html)
        self.assertNotIn("id=\"nx_water\"", html)
        self.assertNotIn("nx_water_btn", html)
        self.assertIn("waterlayer.js", html)
        self.assertIn("BN_WATER", html)
        src = (APP / "netpages.py").read_text()
        self.assertIn("/grid/water", src)

    def _db(self):
        import waterdb
        c = waterdb.conn()
        self.assertIsNotNone(c, "water.db.b64.N parts missing")
        return waterdb, c

    def test_plant_store_rows_cite_a_source_and_cover_the_world(self):
        waterdb, c = self._db()
        n, = c.execute("SELECT COUNT(*) FROM p").fetchone()
        self.assertGreater(n, 100000)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM p WHERE src NOT IN (SELECT id FROM s)").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM p WHERE lat=0 OR lon=0 OR abs(lat)>90 OR abs(lon)>180").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM p WHERE k NOT IN (0,1)").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM p WHERE uid NOT GLOB '[A-Za-z]*'").fetchone()[0], 0)
        self.assertGreaterEqual(c.execute("SELECT COUNT(DISTINCT cc) FROM p").fetchone()[0], 100)
        states = {r[0] for r in c.execute("SELECT DISTINCT st FROM p WHERE cc='US' AND st!=''")}
        self.assertGreaterEqual(len(states), 50, sorted(states))
        for label, tpl in c.execute("SELECT label,tpl FROM s"):
            self.assertTrue(label and tpl.startswith("https://"), label)

    def test_viewport_endpoint_is_small_and_capped(self):
        import json as J
        waterdb, c = self._db()
        code, body, ct, hdr = waterdb.view({"w": "-180", "s": "-90", "e": "180", "n": "90", "z": "1"})
        self.assertEqual(code, 200)
        self.assertLess(len(body), 40_000, "world cluster view must stay tiny")
        d = J.loads(body); self.assertEqual(d["t"], "c")
        code, body, ct, hdr = waterdb.view({"w": "-125", "s": "24", "e": "-66", "n": "50", "z": "4"})
        self.assertLess(len(body), 120_000)
        code, body, ct, hdr = waterdb.view({"w": "-118.6", "s": "33.7", "e": "-117.9", "n": "34.3", "z": "10"})
        d = J.loads(body); self.assertEqual(d["t"], "p"); self.assertLessEqual(len(d["r"]), waterdb.POINT_CAP)
        self.assertLess(len(body), 400_000)
        code, det = waterdb.detail({"id": d["r"][0][3]})[:2]
        self.assertEqual(code, 200); self.assertTrue(det["src"] and det["url"].startswith("https://"))
        self.assertEqual(waterdb.detail({"id": "../etc/passwd"})[0], 404)
        self.assertEqual(waterdb.detail({"id": "zz999999"})[0], 404)

    def test_plant_permalink_item_has_share_fields(self):
        import water
        waterdb, c = self._db()
        uid = c.execute("SELECT uid FROM p WHERE cc='US' LIMIT 1").fetchone()[0]
        it = water.item_by_id(uid)
        self.assertTrue(it and it["permalink"].endswith("/water/" + uid) and "x.com/intent" in it["xu"] and it["src"])

    def test_grid_boot_gate_script_still_valid(self):
        gate = (ROOT / "tools" / "grid_boot_gate.py").read_text()
        self.assertIn("window.__nxMap", gate)
        self.assertIn("GATE_OK", gate)

    def test_water_view_centers_on_the_lower_48(self):
        self.assertIn("var US = [[-125.5, 23.5], [-66, 50]]", WL)
        self.assertIn("fitBounds(US", WL)
        self.assertNotIn("accountForPanel", WL)

    def test_boot_payload_still_reads_the_shipped_db(self):
        import waterdb, netmap
        st = waterdb.stats()
        self.assertTrue(st and st["plants"] > 100000)
        boot = netmap._water_boot(True, "", None)
        self.assertEqual(boot["plants"], st["plants"])
        self.assertEqual(boot["countries"], st["countries"])
