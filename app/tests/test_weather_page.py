"""Weather map (/weather, Nov 22 2026, pt1742u / pt1743u): menu link, route, page skeleton, US-centred start, worldwide sources, no yellow in the interface."""
import os, sys, re, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

class WeatherPage(unittest.TestCase):
    def test_menu_links_the_weather_page(self):
        import sitenav, sitenav_ui
        rows = {k: (l, h) for _, _, _, rs in sitenav_ui.menu3_sections(sitenav) for k, l, h in rs}
        self.assertEqual(rows["weather"], ("Weather", "/weather"))
        html = sitenav.header_html("")
        self.assertIn('<a href="/weather">Weather</a>', html)
        self.assertNotIn('data-tab="weather"', html)

    def test_route_and_page(self):
        import addons, wxmap
        self.assertEqual(addons.ROUTES["/weather"], "wxmap")
        self.assertEqual(addons.ROUTES["/api/wxmap"], "wxmap")
        wxmap.warm_once = lambda: None
        code, body, ct = wxmap.handle_get("/weather", {})
        self.assertEqual((code, ct), (200, "text/html"))
        for s in ('id="wx_map"', 'id="wx_ld"', 'id="wx_range"', 'id="wx_modes"', 'id="wx_lays"', "/api/signal/maplibre-gl.js", "/api/wxmap/wx.js", "/api/wxmap/wx.css"):
            self.assertIn(s, body)
        self.assertEqual(wxmap.handle_get("/api/wxmap/nope", {})[0], 404)
        self.assertEqual(wxmap.handle_get("/api/wxmap/wx.js", {})[0], 200)
        self.assertEqual(wxmap.handle_get("/api/wxmap/wxw.js", {})[0], 200)   # decode worker
        for s in ('id="wx_reg"', 'data-r="world"', 'id="wx_srcs"', 'id="wx_ldg"', 'id="wx_ldfill"'):
            self.assertIn(s, body)

    def test_grid_regions_and_global_alerts(self):
        import wxmap
        self.assertEqual(sorted(wxmap.GRIDS), ["us", "world"])
        self.assertEqual(wxmap.handle_get("/api/wxmap/grid", {"r": ["mars"]})[0], 404)
        wxmap.gdacs = lambda: {"type": "FeatureCollection", "features": [], "tc": {"type": "FeatureCollection", "features": []}}
        self.assertEqual(wxmap.handle_get("/api/wxmap/global", {})[0], 200)

    def test_us_start_and_map_native_layers(self):
        js = open(os.path.join(APP, "wxmap_static", "wx.js"), encoding="utf-8").read()
        self.assertIn("bounds: US0", js)
        self.assertIn("US = [[-125.5, 23.5], [-66, 50]]", js)
        self.assertIn('type: "raster", tiles:', js)     # radar frames are map raster sources, not positioned images
        self.assertIn('type: "image", url: "wxg://', js)   # model fields are georeferenced image sources, decoded off the main thread
        self.assertNotIn("tile.openstreetmap.org", js)

    def test_no_yellow_in_interface(self):
        for f in ("wx.css", "wxw.js"):
            t = open(os.path.join(APP, "wxmap_static", f), encoding="utf-8").read().lower()
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15"): self.assertNotIn(c, t)
        js = open(os.path.join(APP, "wxmap_static", "wx.js"), encoding="utf-8").read().lower()
        for c in ("#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#f5a524"): self.assertNotIn(c, js)

if __name__ == "__main__": unittest.main()
