"""The Grid + Network Status merge (Nov 24 2026, Matt pt1795u): one "The Grid" menu item at /network, /grid 302s to /network,
the grid operator layer and "More about the grid" sheet are on /network, the old /grid code stays in the repo."""
import os, sys, re, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"

def _read(*p):
    with open(os.path.join(APP, *p), encoding="utf-8") as fh: return fh.read()

class GridMerge(unittest.TestCase):
    def test_menu_has_the_grid_once(self):
        import menu5
        its = menu5.items()
        labels = [l for _, l, _ in its]
        self.assertEqual(labels.count("The Grid"), 1)
        self.assertNotIn("Network Status", labels)
        self.assertIn(("net", "The Grid", "/network"), its)
        self.assertFalse(any(h.split("?")[0] == "/grid" for _, _, h in its))

    def test_old_grid_url_redirects_to_network(self):
        import deactivated as D
        if not D.ON: self.skipTest("BN_DEACTIVATE_PAGES=0")
        for p in ("/grid", "/grid/", "/GRID", "/grid/anything"):
            self.assertTrue(D.redirects(p), p)
            self.assertEqual(D.location(p), "/network", p)
        self.assertEqual(D.location("/live"), "/")
        for p in ("/network", "/api/gridpage/data", "/api/gridpage/grid.js", "/api/gridstatus", "/gridx"):
            self.assertFalse(D.redirects(p), p)
        self.assertTrue(D.href_off("/grid"))
        self.assertIn("grid", D.KEYS)

    def test_page_has_the_merged_grid(self):
        import netpages, netmap
        code, body, ct = netpages.handle_get("/network", {})
        self.assertEqual(code, 200)
        self.assertIn("<title>The Grid:", body)
        self.assertIn('<h1 class="nx-vh">The Grid:', body)
        self.assertIn('og:title" content="The Grid:', body)
        self.assertNotIn("Network Status", body)
        for s in ('data-k="ops"', 'id="gx_more_btn"', 'id="gx_more"', 'id="gx_card"', 'id="gx_reg"', 'id="gx_kpis"', 'id="nb_grid"',
                  "/api/netmap/gridlayer.js", "/api/netmap/gridlayer.css", "Energizing the grid"):
            self.assertIn(s, body)
        for sid in ("gx-regions", "gx-world", "gx-outages", "gx-weather", "gx-threats", "gx-space", "gx-local", "gx-sources"):
            self.assertEqual(body.count(f'id="{sid}"'), 1, sid)
        for f in ("gridlayer.js", "gridlayer.css"): self.assertEqual(netmap.handle_get("/api/netmap/" + f)[0], 200)

    def test_gridlayer_rules(self):
        js = _read("netmap_static", "gridlayer.js"); css = _read("netmap_static", "gridlayer.css")
        for t in (js.lower(), css.lower()):
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            self.assertNotIn("tile.openstreetmap.org", t)
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#ffc21a", "#c97b00"): self.assertNotIn(c, t)
        self.assertIn("new maplibregl.Map", _read("netmap_static", "net.js"))
        self.assertNotIn("new maplibregl.Map", js)              # one map: the grid layer attaches to the network map
        self.assertIn("if (w.lat == null || w.lon == null) return;", js)   # alerts with no place stay off the map
        self.assertIn('"ops"', _read("netmap.py"))
        self.assertIn("ops: true", _read("netmap_static", "net.js"))

    def test_old_grid_code_kept(self):
        for p in (("gridpage.py",), ("gridpage_static", "grid.js"), ("gridpage_static", "grid.css")):
            self.assertTrue(os.path.exists(os.path.join(APP, *p)), p)

    def test_no_internal_links_to_grid(self):
        for f in ("theme.py", "apple_v1.py", "ready.py", "welcome.py", "growth.py", "menu5.py", "sitenav_ui.py", os.path.join("signal_map_static", "app.js"), os.path.join("netmap_static", "net.js")):
            t = _read(f)
            self.assertIsNone(re.search(r'href=["\']/grid\b|href: "/grid"|"/grid"\)|: "/grid"', t), f)

if __name__ == "__main__": unittest.main()
