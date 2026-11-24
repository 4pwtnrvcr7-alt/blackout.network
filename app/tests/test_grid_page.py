"""The Grid (/grid, Nov 21 2026, pt1737u): menu label + link, route, no yellow, page skeleton."""
import os, sys, re, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

class GridPage(unittest.TestCase):
    def test_menu_links_the_grid_page(self):
        """Nov 24 2026 (Matt pt1795u): The Grid is merged into /grid; the menu's one "The Grid" item opens /grid."""
        import sitenav, sitenav_ui
        rows = {k: (l, h) for _, _, _, rs in sitenav_ui.menu3_sections(sitenav) for k, l, h in rs}
        self.assertEqual(rows["net"], ("The Grid", "/grid"))
        self.assertNotIn("grid", rows)
        html = sitenav.header_html("")
        self.assertNotIn('href="/network"', html)   # Nov 24 2026 8:32 AM ET: /grid is canonical
        self.assertNotIn("/live#grid", html)

    def test_route_and_page(self):
        import addons, gridpage
        self.assertEqual(addons.ROUTES["/grid"], "netpages")   # Nov 24 2026: /grid serves the merged page; the old page code below is kept
        code, body, ct = gridpage.handle_get("/grid", {})
        self.assertEqual((code, ct), (200, "text/html"))
        for s in ('id="gx_map"', 'id="gx_ld"', 'id="gx_more"', "/api/signal/maplibre-gl.js", "/api/gridpage/grid.js"):
            self.assertIn(s, body)
        self.assertEqual(gridpage.handle_get("/api/gridpage/nope", {})[0], 404)

    def test_no_yellow_no_osm_tiles(self):
        for f in ("grid.css", "grid.js"):
            t = open(os.path.join(APP, "gridpage_static", f), encoding="utf-8").read().lower()
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            self.assertNotIn("tile.openstreetmap.org", t)
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15"): self.assertNotIn(c, t)

if __name__ == "__main__": unittest.main()

class MapsOpenOnUS(unittest.TestCase):
    """Matt (Nov 21 7:37 PM ET): every map opens on the continental U.S."""
    def test_initial_views(self):
        rd = lambda p: open(os.path.join(APP, p), encoding="utf-8").read()
        self.assertIn("? (VIEWS[state.view] || VIEWS.world) : VIEWS.us", rd("signal_map_static/map2.js"))
        for p in ("heatmap_static/app.js", "solar_seismic_static/app.js", "solar_seismic_static/live.js", "trends_static/app.js", "solar_quake_static/app.js"):
            self.assertIn("fitBounds([[24.5,-125],[49.5,-66.5]])", rd(p), p)
        self.assertNotIn("setView([20,0],2)", rd("static/cohesion.js").replace("MP.map&&MP.map.setView([20,0],2)", ""))
        self.assertIn("bounds: US", rd("gridpage_static/grid.js"))
