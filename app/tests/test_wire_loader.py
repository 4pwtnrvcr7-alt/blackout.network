"""The Wire opens with a short full-screen loading animation (original canvas, real data), then a plain black timeline with no hero and no motion."""
import os, re, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import wire_timeline as W

STATIC = os.path.join(os.path.dirname(W.__file__), "wire_timeline_static")


class WireLoader(unittest.TestCase):
    def test_page_has_loader_and_no_hero_or_background(self):
        html = W.page_html()
        self.assertIn('id="tl_ld"', html)
        self.assertIn('id="tl_ldc"', html)
        self.assertIn("/api/wire_tl/loader.js", html)
        self.assertIn("/api/wire_tl/pulse", html)           # early prefetch from the head
        self.assertLess(html.index('id="tl_ld"'), html.index('id="tl_ref"'))
        for gone in ("tl-hero", "tl-bg", "tl-scanbg", "tl_scanbg", "scan-bg.js", "tl_enter", "tl-cue", "Enter the timeline", "<video"):
            self.assertNotIn(gone, html)
        # the timeline controls and the stale notice stay
        for keep in ('id="tl_q"', 'id="tl_filt"', 'id="tl_when"', 'id="tl_cond"', 'id="tl_ref"', 'id="tl_list"', 'id="tl_stale"'):
            self.assertIn(keep, html)
        self.assertLess(html.index('id="tl_main"'), html.index('id="tl_ctl"'))

    def test_loader_asset_served(self):
        self.assertIn("loader.js", W.FILES)
        self.assertNotIn("scan-bg.js", W.FILES)
        code, body, ct = W.handle_get("/api/wire_tl/loader.js", {})
        self.assertEqual(code, 200)
        self.assertEqual(ct, "application/javascript")
        self.assertIn(b"prefers-reduced-motion", body)

    def test_loader_js_rules(self):
        js = open(os.path.join(STATIC, "loader.js"), encoding="utf-8").read()
        css = open(os.path.join(STATIC, "app.css"), encoding="utf-8").read()
        self.assertIn("devicePixelRatio", js)
        self.assertIn("requestAnimationFrame", js)
        self.assertIn("bn-tl-ready", js)
        self.assertIn("bn-tl-ready", open(os.path.join(STATIC, "app.js"), encoding="utf-8").read())
        self.assertNotRegex(js, r"https?://")
        self.assertNotIn("webgl", js.lower())
        self.assertNotIn("peer-to-peer", (js + css).lower())
        self.assertNotRegex(js, r"(?i)yellow|gold|#ff0|#ffc|#c97b00")
        self.assertNotRegex(css, r"(?i)#ff0|#ffc|#c97b00")
        # no hero, no background layer, no animation on the timeline itself
        for gone in (".tl-hero", ".tl-bg", ".tl-scanbg", ".tl-cue", "@keyframes tlcue"):
            self.assertNotIn(gone, css)

    def test_pulse_endpoint_shape_and_round_robin(self):
        import time
        rows = [{"t": "2026-11-27T10:%02d:00Z" % i, "k": "quake", "r": 3, "lat": 10.0 + i, "lon": 20.0, "p": "X"} for i in range(30)]
        rows += [{"t": "2026-11-27T09:00:00Z", "k": "cyber", "r": 7, "lat": 40.0, "lon": -100.0, "p": "US"}]
        pack = W._pulse_pack(rows)
        self.assertLessEqual(len(pack["signals"]), 24)
        self.assertIn("cyber", [s["k"] for s in pack["signals"]])    # one feed cannot crowd out the rest
        # served from memory; no rebuild thread is started in the test
        old, was = dict(W._PULSE), W._PBG["on"]
        try:
            W._PBG["on"] = True
            W._PULSE.update(t=time.time(), data=pack)
            code, body = W.handle_get("/api/wire_tl/pulse", {})[:2]
        finally:
            W._PULSE.update(old); W._PBG["on"] = was
        self.assertEqual(code, 200)
        for s in body["signals"]:
            self.assertTrue(-90 <= s["lat"] <= 90 and -180 <= s["lon"] <= 180)
            self.assertIn("k", s)


if __name__ == "__main__":
    unittest.main()
