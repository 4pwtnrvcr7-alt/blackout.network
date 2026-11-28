"""The Wire background is an original canvas scan animation, not stock video."""
import os, re, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import wire_timeline as W

STATIC = os.path.join(os.path.dirname(W.__file__), "wire_timeline_static")


class ScanBg(unittest.TestCase):
    def test_page_uses_canvas_not_stock_video(self):
        html = W.page_html()
        self.assertIn('class="tl-scanbg"', html)
        self.assertIn('id="tl_scanbg"', html)
        self.assertIn("/api/wire_tl/scan-bg.js", html)
        self.assertNotIn("tl-vid", html)
        self.assertNotIn("<video", html)
        self.assertNotIn("wtvid-d", html)
        self.assertNotIn("wthero-m", html)
        self.assertIn("scan-bg.js", W.FILES)
        code, body, ct = W.handle_get("/api/wire_tl/scan-bg.js", {})
        self.assertEqual(code, 200)
        self.assertEqual(ct, "application/javascript")
        self.assertIn(b"prefers-reduced-motion", body)
        # controls stay in the page and are not inside the pointer-events-none layer
        self.assertIn('id="tl_ref"', html)
        self.assertIn(">Refresh</span>", html)
        self.assertIn('id="tl_enter"', html)
        self.assertLess(html.index('class="tl-bg"'), html.index('id="tl_ref"'))
        with open(os.path.join(STATIC, "app.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertIn('pointer-events:none', css.split(".tl-bg")[1][:240])

    def test_scan_bg_js_performance_and_palette(self):
        with open(os.path.join(STATIC, "scan-bg.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(STATIC, "app.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("visibilitychange", js)
        self.assertIn("document.hidden", js)
        self.assertIn("devicePixelRatio", js)
        self.assertIn("Math.min(2", js)
        self.assertIn("requestAnimationFrame", js)
        self.assertIn(".tl-scanbg", css)
        self.assertIn("pointer-events:none", css)
        self.assertNotRegex(js, r"https?://")
        self.assertNotIn("three.js", js.lower())
        self.assertNotIn("webgl", js.lower())
        for src in (js, css):
            self.assertNotIn("#FFC", src)
            self.assertNotRegex(src, r"#[0-9A-Fa-f]*[Yy]ellow|yellow|gold|#FF0|#ff0|#FFC21A|#C97B00")


if __name__ == "__main__":
    unittest.main()
