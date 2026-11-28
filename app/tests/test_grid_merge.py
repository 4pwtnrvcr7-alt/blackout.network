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
        self.assertIn(("net", "The Grid", "/grid"), its)   # Nov 24 2026 8:32 AM ET: /grid is canonical
        self.assertFalse(any(h.split("?")[0] == "/network" for _, _, h in its))

    def test_network_redirects_to_grid(self):
        """Nov 24 2026 8:32 AM ET (Matt): /grid is canonical; /network and /network/* 302 to the same path under /grid."""
        import deactivated as D
        self.assertEqual(D.renamed("/network"), "/grid")
        self.assertEqual(D.renamed("/network", "a=1"), "/grid?a=1")
        self.assertEqual(D.renamed("/network/"), "/grid")
        self.assertEqual(D.renamed("/network/status/aws"), "/grid/status/aws")
        self.assertEqual(D.renamed("/GRID"), "/grid")
        for p in ("/grid", "/grid/aws", "/api/network/aws/brief", "/api/netmap/data", "/networks", "/api/gridpage/data"):
            self.assertIsNone(D.renamed(p), p)
        self.assertFalse(D.redirects("/grid")); self.assertFalse(D.is_off("/grid"))
        self.assertTrue(D.redirects("/grid/starlink"))
        self.assertIn("grid", D.KEYS)   # the old menu key stays hidden; The Grid is the "net" item

    def test_page_has_the_merged_grid(self):
        import netpages, netmap
        code, body, ct = netpages.handle_get("/grid", {})
        self.assertEqual(code, 200)
        self.assertIn("<title>The Grid:", body)
        self.assertIn('<h1 class="nx-vh">The Grid:', body)
        self.assertIn('og:title" content="The Grid:', body)
        self.assertNotIn("Network Status", body)
        for s in ('data-k="grid"', 'id="gx_more_btn"', 'id="gx_more"', 'id="gx_card"', 'id="gx_reg"', 'id="gx_kpis"', 'id="nb_grid"',
                  "/api/netmap/gridlayer.js", "/api/netmap/gridlayer.css", "Energizing the grid"):
            self.assertIn(s, body)
        for sid in ("gx-regions", "gx-world", "gx-outages", "gx-weather", "gx-threats", "gx-space", "gx-local", "gx-sources"):
            self.assertEqual(body.count(f'id="{sid}"'), 1, sid)
        for f in ("gridlayer.js", "gridlayer.css"): self.assertEqual(netmap.handle_get("/api/netmap/" + f)[0], 200)

    def test_gridlayer_rules(self):
        js = _read("netmap_static", "gridlayer.js"); css = _read("netmap_static", "gridlayer.css")
        # pt2007u: Refresh yellow/orange/red is approved on the /grid loader only. Strip that block before the yellow ban.
        ld0, ld1 = css.find("/* ---------- loader:"), css.find(".gx-b,.gx-x{")
        self.assertGreater(ld0, -1); self.assertGreater(ld1, ld0)
        loader, rest = css[ld0:ld1], css[:ld0] + css[ld1:]
        for h in ("#FFE566", "#FF9A1A", "#FF5A3C"):
            self.assertIn(h, loader)
        self.assertIn("@keyframes gx-ld-drop", loader)
        self.assertIn("prefers-reduced-motion", loader)
        for t in (js.lower(), rest.lower()):
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            self.assertNotIn("tile.openstreetmap.org", t)
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#ffc21a", "#c97b00"): self.assertNotIn(c, t)
        self.assertIn("new maplibregl.Map", _read("netmap_static", "net.js"))
        self.assertNotIn("new maplibregl.Map", js)              # one map: the grid layer attaches to the network map
        self.assertIn("if (w.lat == null || w.lon == null) return;", js)   # alerts with no place stay off the map
        self.assertIn('("grid", "Power grid")', _read("netmap.py"))   # Nov 24 2026: one Power grid chip runs outages + operators + lines
        self.assertIn("ON.power = ON.ops = !!ON.grid", _read("netmap_static", "net.js"))
        for k in ('"ops"', '"power"', '"mobile"', '"sat"', '"pay"', '"apps"'):   # chips with no map items are gone (they live on Status)
            self.assertNotIn("(" + k + ",", _read("netmap.py").split("CHIPS = ")[1].split("\n")[0])

    def test_old_grid_code_kept(self):
        for p in (("gridpage.py",), ("gridpage_static", "grid.js"), ("gridpage_static", "grid.css")):
            self.assertTrue(os.path.exists(os.path.join(APP, *p)), p)

    def test_no_internal_links_to_network(self):
        for f in ("theme.py", "apple_v1.py", "ready.py", "welcome.py", "growth.py", "menu5.py", "sitenav_ui.py", "meshnet.py", "netpages.py",
                  os.path.join("signal_map_static", "app.js"), os.path.join("netmap_static", "net.js"), os.path.join("netmap_static", "board.js"), os.path.join("static", "bn-apple.js")):
            t = _read(f)
            self.assertIsNone(re.search(r'href=["\']/network\b|href: "/network"|"/network"\)|: "/network"|blackout\.network/network', t), f)

if __name__ == "__main__": unittest.main()
