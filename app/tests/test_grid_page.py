"""The Grid (/grid, Nov 21 2026, pt1737u): menu label + link, route, no yellow, page skeleton."""
import os, sys, re, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

class GridPage(unittest.TestCase):
    def test_menu_links_the_grid_page(self):
        import sitenav, sitenav_ui
        rows = {k: (l, h) for _, _, _, rs in sitenav_ui.menu3_sections(sitenav) for k, l, h in rs}
        self.assertEqual(rows["grid"], ("The Grid", "/grid"))
        html = sitenav.header_html("")
        self.assertIn('<a href="/grid">The Grid</a>', html)
        self.assertNotIn("/live#grid", html)

    def test_route_and_page(self):
        import addons, gridpage
        self.assertEqual(addons.ROUTES["/grid"], "gridpage")
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
