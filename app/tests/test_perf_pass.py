from pathlib import Path
"""Performance pass (Nov 17 2026, 9:13 PM ET): smaller /live HTML, lazy tab assets, deferred GA.
   Run: cd app && python3 -m unittest tests.test_perf_pass -v
"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import perf_load
import apple_v1
import theme

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as f: return f.read()

class Sources(unittest.TestCase):
    def test_cohesion_is_external(self):
        dash = _read("dashboard.html")
        self.assertIn('src="/cohesion.js"', dash)
        self.assertNotIn("shared palette lookups", dash)
        js = _read("static", "cohesion.js")
        self.assertIn("TABHASH", js)
        self.assertGreater(len(js), 10000)

    def test_lazy_loader_exists(self):
        js = _read("static", "bn-lazy.js")
        self.assertIn("bnLazyLoad", js)
        self.assertIn("IntersectionObserver", js)

    def test_apple_snap_is_external_by_default(self):
        os.environ.pop("BN_PERF", None)
        html = apple_v1._snap_js()
        self.assertIn("/bn-apple-home.js", html)
        self.assertNotIn("BNA.render({", html)
        self.assertIn('rel="preload"', html)
        self.assertIn("/api/apple/home", html)

    def test_apple_snap_inline_when_flag_off(self):
        old = os.environ.get("BN_PERF")
        os.environ["BN_PERF"] = "0"
        try:
            html = apple_v1._snap_js()
            # May be empty if no cache, but must not be the external-only path
            if html:
                self.assertNotIn('rel="preload"', html)
        finally:
            if old is None: os.environ.pop("BN_PERF", None)
            else: os.environ["BN_PERF"] = old

class Rewrite(unittest.TestCase):
    def test_strips_tab_assets_and_injects_loader(self):
        sample = (
            b'<!doctype html><html><head>'
            b'<link rel="stylesheet" href="/sitenav.css">'
            b'<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'
            b'<link rel="stylesheet" href="api/weather/app.css">'
            b'</head><body>'
            b'<main id="tab-threat"></main>'
            b'<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
            b'<script src="api/weather/app.js"></script>'
            b'<script src="/sitenav.js" defer></script>'
            b'</body></html>'
        )
        out = perf_load.rewrite(sample)
        self.assertNotIn(b'href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"', out.split(b"BN_LAZY_GROUPS")[0])
        self.assertNotIn(b'href="api/weather/app.css"', out.split(b"BN_LAZY_GROUPS")[0])
        self.assertNotIn(b'src="api/weather/app.js"', out.split(b"BN_LAZY_GROUPS")[0])
        self.assertIn(b"/sitenav.css", out)
        self.assertIn(b"/sitenav.js", out)
        self.assertIn(b"BN_LAZY_GROUPS", out)
        self.assertIn(b"/bn-lazy.js", out)
        self.assertIn(b"leaflet", out)  # in the config
        self.assertIn(b"weather", out)

    def test_flag_off_is_noop_for_rewrite(self):
        sample = b'<!doctype html><html><head><link rel="stylesheet" href="api/weather/app.css"></head><body><main id="tab-threat"></main></body></html>'
        old = os.environ.get("BN_PERF")
        os.environ["BN_PERF"] = "0"
        try:
            out = perf_load.rewrite(sample)
            self.assertEqual(out, sample)
        finally:
            if old is None: os.environ.pop("BN_PERF", None)
            else: os.environ["BN_PERF"] = old

    def test_lazy_images_skip_hero(self):
        sample = (
            b'<!doctype html><html><body>'
            b'<img src="/a.jpg" alt="">'
            b'<img src="/hero.jpg" alt="" fetchpriority="high">'
            b'<img src="/b.jpg" alt="" loading="lazy">'
            b'</body></html>'
        )
        out = perf_load.rewrite(sample)
        # two imgs should mention lazy, hero keeps fetchpriority and no extra lazy required
        self.assertIn(b'<img src="/a.jpg" alt="" loading="lazy">', out)
        self.assertIn(b'fetchpriority="high"', out)
        self.assertEqual(out.count(b'loading="lazy"'), 2)

class Overview(unittest.TestCase):
    def test_live_overview_still_ships_strip(self):
        h = theme.live_overview_html()
        self.assertIn('id="bntl_acq_cv"', h)
        self.assertIn("l-loading", h)
        self.assertNotIn("Acquiring signals", h)

    def test_strips_leaflet_document_write_fallback(self):
        raw = (
            b"<!doctype html><html><head></head><body>"
            b'<main id="tab-threat"></main>'
            b'<script>if(typeof L!="undefined"&&!L.heatLayer)document.write('
            b"'<script src=\"api/heatmap/leaflet-heat.js\"><\\/script>');"
            b'if(typeof L!="undefined"&&!L.markerClusterGroup)document.write('
            b"'<script src=\"api/heatmap/leaflet.markercluster.js\"><\\/script>')</script>"
            b"</body></html>"
        )
        out = perf_load.rewrite(raw)
        self.assertNotIn(b"document.write", out)


    def test_cohesion_does_not_touch_leaflet_until_loaded(self):
        js = Path(__file__).resolve().parents[1].joinpath("static", "cohesion.js").read_text(encoding="utf-8")
        # The old top-level `if(L.HeatLayer&&...)` threw "L is not defined" once Leaflet was lazy.
        self.assertNotIn("if(L.HeatLayer", js)
        self.assertIn("typeof L", js)
        self.assertIn('location.replace("/map"', js)
