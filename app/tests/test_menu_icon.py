"""Hamburger icon + close animation (Nov 17 2026). Run: cd app && python3 -m unittest tests.test_menu_icon -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sitenav, sitenav_ui as UI, theme, wire_v2

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HX = re.compile(r'<span class="bn-hx" aria-hidden="true">(?:<span class="bn-hx-bar"></span>){3}</span>')
BARS = re.compile(r'class="bn-hx-bar"')

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as f: return f.read()

class Markup(unittest.TestCase):
    def test_shared_header_has_three_even_bars_and_labels(self):
        html = UI.topbar(sitenav, active="threat")
        self.assertRegex(html, HX)
        self.assertEqual(len(BARS.findall(html)), 3)
        self.assertIn('aria-label="Open menu"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('class="bn-bl-a">Menu</span>', html)
        self.assertIn('class="bn-bl-b">Close</span>', html)
        self.assertNotIn("<path d=\"M3 6h18M3 12h18M3 18h18\"", html)

    def test_homepage_burger_not_broken_by_menu_label(self):
        h = theme.home_page()
        self.assertRegex(h, HX)
        self.assertEqual(len(BARS.findall(h.split("h-burger")[1].split("</button>")[0])), 3)
        self.assertIn('aria-label="Open menu"', h)
        self.assertIn('class="bn-bl-a">Menu</span>', h)
        self.assertIn('class="bn-bl-b">Close</span>', h)
        # The bug Matt shot: MENU as first child made i:nth-child miss the top bar.
        self.assertNotIn("<i></i><i></i><i></i>", h.split("h-burger")[1].split("</button>")[0])

    def test_wire_header_uses_the_same_icon(self):
        html = wire_v2.shell("Wire", "desc", "<p>x</p>", "/wire")
        self.assertRegex(html, HX)
        self.assertIn('aria-label="Open menu"', html)
        self.assertIn("wire2.css?v=7", html)
        self.assertIn("wire2.js?v=3", html)

class StylesAndScript(unittest.TestCase):
    def test_css_has_fall_standup_and_reduced_motion(self):
        home = _read("theme_static", "home.css")
        self.assertNotIn(".h-burger i:nth-child(1)", home)
        self.assertIn("animation:bn-rise", home)
        self.assertIn("animation:bn-fall", home)
        self.assertIn("prefers-reduced-motion:reduce", home)
        for rel in ("static/sitenav.css", "theme_static/theme.css", "wire_v2_static/wire2.css"):
            css = _read(*rel.split("/"))
            self.assertIn("@keyframes bn-hx-a-open", css, rel)
            self.assertIn("@keyframes bn-hx-a-close", css, rel)
            self.assertIn("@keyframes bn-rise", css, rel)
            self.assertIn("@keyframes bn-fall", css, rel)
            self.assertIn("prefers-reduced-motion:reduce", css, rel)
            self.assertIn("translateY(-6px)", css, rel)
            self.assertIn("rotate(45deg)", css, rel)

    def test_js_toggles_aria_and_delays_close(self):
        js = _read("static", "sitenav.js")
        self.assertIn('Close menu', js)
        self.assertIn("finishClose", js)
        self.assertIn("bn-closing", js)
        self.assertIn("data-bn-hx", js)
        js = _read("theme_static", "home.js")
        self.assertIn("Close menu", js)
        self.assertIn("h-closing", js)
        self.assertIn("data-bn-hx", js)
        js = _read("wire_v2_static", "wire2.js")
        self.assertIn("Close menu", js)
        self.assertIn("w2-closing", js)

if __name__ == "__main__":
    unittest.main()
