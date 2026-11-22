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

class OpenMeteoBudget(unittest.TestCase):
    """pt1745u: deploys never refill the grids from Open-Meteo; 429 backs off; a stopped refresh resumes; last good grid is served."""
    def setUp(self):
        import tempfile, wxmap, om_budget as OMB
        self.w, self.B = wxmap, OMB
        self.dir = tempfile.mkdtemp(); wxmap.PDIR = self.dir
        OMB._S.update(log=[], until=0.0, why=None, last429=0.0)
        for k in [k for k in wxmap._C if k[0] in ("grid", "griderr", "gridb", "gfsgrid")]: wxmap._C.pop(k, None)
        wxmap._PART.clear(); wxmap._PEER_ST["state"] = "off"; wxmap.CHUNK_GAP = 0
        self._jget = wxmap.jget

    def tearDown(self):
        self.w.jget = self._jget; self.w.CHUNK_GAP = 40
        self.B._S.update(log=[], until=0.0, why=None, last429=0.0)

    def _fake(self, fail_at=None):
        import io, urllib.error, urllib.parse
        calls = []
        def jget(u, **kw):
            calls.append(u)
            if fail_at is not None and len(calls) == fail_at:
                raise urllib.error.HTTPError(u, 429, "Too Many Requests", {"Retry-After": "3600"}, io.BytesIO(b'{"error":true,"reason":"Hourly API request limit exceeded"}'))
            n = len(urllib.parse.parse_qs(urllib.parse.urlparse(u).query)["latitude"][0].split(","))
            h = {"time": ["2026-11-22T00:00", "2026-11-22T03:00"], "temperature_2m": [10.0, 11.0], "precipitation": [0.0, 1.2], "snowfall": [0.0, 0.0]}
            return [{"hourly": h} for _ in range(n)]
        self.w.jget = jget
        return calls

    def test_429_backs_off_then_resumes_without_repeating_chunks(self):
        w = self.w
        calls = self._fake(fail_at=2)
        with self.assertRaises(Exception): w.grid("us")              # chunk 1 ok, chunk 2 -> 429
        self.assertTrue(self.B.limited()[0])
        self.assertEqual(len(calls), 2)
        with self.assertRaises(w.Limited): w.grid("us")              # backing off: no call at all
        self.assertEqual(len(calls), 2)
        self.B._S["until"] = 0
        g = w.grid("us")                                              # resumes at chunk 2, not from scratch
        self.assertEqual(len(calls), 2 + (len(w._cells(w.GRIDS["us"])) - 1) // w.CHUNK)
        self.assertEqual(len(g["temp"]), 2 * len(w._cells(w.GRIDS["us"])))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "grid_us.json.gz")))

    def test_last_good_grid_survives_restart_and_is_served_while_limited(self):
        w = self.w
        self._fake(); g = w.grid("us")
        w._C.pop(("grid", "us"), None)
        w._restore()                                                  # what a restarted instance does at import
        self.assertEqual(w.grid_peek("us")["generated"], g["generated"])
        self.B._S["until"] = __import__("time").time() + 600; self.B._S["why"] = "Daily API request limit exceeded"
        import json
        d = json.loads(w.grid_bytes("us"))
        self.assertEqual(d["as_of"], g["generated"]); self.assertIn("rate-limited", d["note"])

    def test_budget_caps_and_handoff_state(self):
        B = self.B
        B.note(B.GRID_HOUR_CAP, "grid")
        self.assertGreater(B.wait_s(300, "grid"), 0)                 # the grids' share is used up ...
        self.assertEqual(B.wait_s(4, "card"), 0)                      # ... place cards still fit
        st = B.state(); B._S.update(log=[], until=0.0)
        self.assertTrue(B.adopt(st)); self.assertEqual(B.used(3600, "grid"), B.GRID_HOUR_CAP)
        code, body = self.w.handle_get("/api/wxmap/omstate", {})[:2]
        self.assertEqual(code, 200); self.assertIn("summary", body)
        self.assertNotIn("key", str(body).lower())

    def test_place_card_fallback_shapes(self):
        import weather
        d = weather.fallback_nws({"periods": [{"startTime": "2026-11-22T14:00:00-05:00", "temperature": 72, "temperatureUnit": "F", "probabilityOfPrecipitation": 20, "windSpeed": "10 mph", "shortForecast": "Partly Sunny", "isDaytime": True}]},
                                 {"periods": [{"startTime": "2026-11-22T12:00:00-05:00", "temperature": 74, "isDaytime": True, "shortForecast": "Sunny", "probabilityOfPrecipitation": 10},
                                              {"startTime": "2026-11-22T18:00:00-05:00", "temperature": 60, "isDaytime": False, "shortForecast": "Clear", "probabilityOfPrecipitation": 0}]}, None)
        self.assertEqual(d["current"]["time"], "2026-11-22T14:00"); self.assertAlmostEqual(d["current"]["temperature_2m"], 22.2, 1)
        self.assertEqual(d["daily"]["time"], ["2026-11-22"]); self.assertEqual(d["daily"]["weather_code"], [0])
        self.assertEqual(weather._wmo_text("Chance Light Snow"), 71)
