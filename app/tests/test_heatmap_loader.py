"""Heat map "Signal acquisition" loader (Nov 20 2026, pt1675u). Run: cd app && python3 -m unittest tests.test_heatmap_loader -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import signal_map

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _read(*p):
    with open(os.path.join(APP, *p), encoding="utf-8") as f: return f.read()

class LoaderMarkup(unittest.TestCase):
    def setUp(self):
        self.code, self.body, _ = signal_map.handle_get("/map", {})
    def test_loader_in_page_and_served(self):
        self.assertEqual(self.code, 200)
        self.assertIn('id="bnm_ld"', self.body)
        self.assertIn('id="bnl_msg"', self.body)
        for s in ("link", "exact", "approx", "region", "global", "base"): self.assertIn('data-s="%s"' % s, self.body)
        code, js, ct = signal_map.handle_get("/api/signal/map2_loader.js", {})
        self.assertEqual((code, ct), (200, "application/javascript"))
    def test_loader_runs_before_maplibre(self):
        a, b = self.body.find("map2_loader.js"), self.body.find("maplibre-gl.js?")
        self.assertTrue(0 < a < b)
    def test_hidden_without_js(self):
        css = _read("signal_map_static", "map2.css")
        self.assertIn(".bnl{display:none}", css)
        self.assertIn("html.bnm-js .bnl{", css)
        self.assertIn('classList.add("bnm-js")', self.body)

class LoaderBehaviour(unittest.TestCase):
    js = _read("signal_map_static", "map2_loader.js")
    css = _read("signal_map_static", "map2.css")
    m2 = _read("signal_map_static", "map2.js")
    def test_real_stages_and_retry(self):
        self.assertIn("getReader", self.js)            # streamed byte count, not a fake timer
        self.assertIn("Retry now", self.js)
        self.assertIn("Slow link", self.js)
        self.assertIn("AbortController", self.js)
    def test_map2_hooks(self):
        for h in ("L.feed()", "L.data(rows)", "BNML.mapReady()", "BNML.engineFail()", "BNML.tile("): self.assertIn(h, self.m2)
    def test_never_blocks_controls(self):
        block = re.search(r"html\.bnm-js \.bnl\{[^}]*\}", self.css).group(0)
        self.assertIn("pointer-events:none", block)
        self.assertIn("z-index:15", block)          # below the chip, filters and zoom (20+)
    def test_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.js)
        self.assertRegex(self.css, r"prefers-reduced-motion:reduce\)\{\.bnl")
    def test_palette_no_yellow_red_only_high(self):
        both = (self.js + self.css[self.css.find("Signal acquisition"):]).lower()
        for y in ("#ffc21a", "#c97b00", "gold", "yellow", "255,194", "255, 194", "#ff0", "#fc0"): self.assertNotIn(y, both)
        self.assertIn("high: [255, 77, 79]", self.js)
        self.assertIn('r >= 7 ? "high"', self.js)
    def test_no_emoji_or_banned_words(self):
        txt = self.js + _read("signal_map.py")
        self.assertFalse(re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]", self.js))
        for w in ("verified", "before the news"): self.assertNotIn(w, self.js.lower())

if __name__ == "__main__": unittest.main()
