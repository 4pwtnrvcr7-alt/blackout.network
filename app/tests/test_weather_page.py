"""Weather map (/weather, Nov 22 2026, pt1742u / pt1743u / pt1744u): menu link, route, page skeleton, US-centred start, worldwide sources, no yellow in the interface."""
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
        self.assertIn('"wxr://" + s.k', js)                 # worldwide satellite / model layers ride the same tile protocol
        self.assertNotIn("tile.openstreetmap.org", js)

    def test_free_worldwide_sources_only(self):
        """pt1744u: worldwide layers come from NASA GIBS, EUMETSAT (CC BY 4.0, credited) and NOAA GFS; RainViewer is gone (its terms do not fit a public site)."""
        import wxmap, wxgfs
        txt = "".join(open(os.path.join(APP, *f), encoding="utf-8").read() for f in (("wxmap.py",), ("wxgfs.py",), ("wxmap_static", "wx.js"), ("wxmap_static", "wxw.js")))
        self.assertNotIn("rainviewer", txt.lower())
        js = open(os.path.join(APP, "wxmap_static", "wx.js"), encoding="utf-8").read()
        for s in ("gibs.earthdata.nasa.gov", "view.eumetsat.int", "EUMETSAT</a> (CC BY 4.0)", "/api/wxmap/gfs?f="):
            self.assertIn(s, js)
        self.assertEqual(wxmap.handle_get("/api/wxmap/gfs", {"f": ["x"]})[0], 404)
        wxgfs.kick = lambda: None
        wxgfs._STATE.update(png=None, meta=None, err=None)
        self.assertEqual(wxmap.handle_get("/api/wxmap/gfs", {"f": ["p"]})[0], 503)   # still loading: a reason, never a crash
        wxgfs._STATE.update(png={"p": b"\x89PNG", "c": b"\x89PNG"})
        r = wxmap.handle_get("/api/wxmap/gfs", {"f": ["c"]}); self.assertEqual((r[0], r[2]), (200, "image/png"))

    def test_grib_bit_helpers(self):
        import wxgfs
        self.assertEqual(wxgfs._bits(bytes([0b10110011, 0b01000000]), 0, 3, 3)[0], [5, 4, 6])
        self.assertEqual(wxgfs._smag(0x8005, 16), -5)
        self.assertEqual(wxgfs._smag(5, 16), 5)
        self.assertEqual(wxgfs._enc_rate(None), 0)
        self.assertEqual(wxgfs._enc_rate(100 / 3600), 255)

    def test_no_yellow_in_interface(self):
        for f in ("wx.css", "wxw.js"):
            t = open(os.path.join(APP, "wxmap_static", f), encoding="utf-8").read().lower()
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15"): self.assertNotIn(c, t)
        js = open(os.path.join(APP, "wxmap_static", "wx.js"), encoding="utf-8").read().lower()
        for c in ("#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#f5a524"): self.assertNotIn(c, js)

if __name__ == "__main__": unittest.main()
