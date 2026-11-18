"""Map menu close + iPad panel-above-scrim (Nov 17 2026). Run: cd app && python3 -m unittest tests.test_map_menu -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import signal_map, sitenav_ui as UI

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as f: return f.read()

class MapPageLoadsSitenav(unittest.TestCase):
    def test_heat_map_html_loads_sitenav_js_and_shared_header(self):
        code, body, ctype = signal_map.handle_get("/map", {})
        self.assertEqual((code, ctype), (200, "text/html"))
        self.assertIn('src="/sitenav.js"', body)
        self.assertIn('id="bn-menu"', body)
        self.assertIn('class="bn-hx"', body)
        self.assertIn('id="bnm_mb"', body)
        self.assertIn('href="#bn-menu"', body)
        # in-head defer, not only the 1.5s retry
        self.assertRegex(body, r'<script src="/sitenav\.js"[^>]*defer')

    def test_classic_map_also_loads_sitenav_js(self):
        code, body, ctype = signal_map.handle_get("/map", {"classic": ["1"]})
        self.assertEqual((code, ctype), (200, "text/html"))
        self.assertIn('src="/sitenav.js"', body)
        self.assertIn('id="bn-menu"', body)

class HeaderStaysForClose(unittest.TestCase):
    def test_map2_js_detects_real_open_class(self):
        js = _read("signal_map_static", "map2.js")
        self.assertIn("bn-menu-on", js)
        self.assertIn("function menuOpen()", js)
        self.assertIn("syncMenuHead", js)
        self.assertIn("bn-closing", js)
        # the old selectors never matched sitenav.js (html.bn-menu-on / .bn-open)
        self.assertNotRegex(js, r'body\.bn-menu-open')
        self.assertNotRegex(js, r'\.bn-drawer\.open')

    def test_map2_css_pins_header_above_menu(self):
        css = _read("signal_map_static", "map2.css")
        self.assertIn("html.bn-menu-on body.bnm .bnm-head", css)
        self.assertIn("z-index:2700!important", css)
        self.assertIn("transform:none!important", css)
        self.assertIn("html.bn-menu-on body.bnm .bnm-mb", css)
        self.assertIn("pointer-events:none!important", css)

class IpadPanelAboveScrim(unittest.TestCase):
    def test_sitenav_css_panel_stacks_above_scrim(self):
        css = _read("static", "sitenav.css")
        self.assertIn(".bn-scrim{position:absolute;inset:0;z-index:0;", css)
        self.assertIn(".bn-panel{position:absolute;top:0;right:0;bottom:0;z-index:1;", css)
        self.assertIn("html.bn-menu-on #bn-menu .bn-scrim", css)
        self.assertIn("html.bn-menu-on #bn-menu .bn-panel", css)
        self.assertIn("html.bn-menu-on #bn-menu{z-index:2600;isolation:isolate}", css)
        # settings / alert pop (restyled in #39) stays its own layer above the drawer
        self.assertIn(".bn-pop-scrim{position:fixed;inset:0;", css)
        self.assertIn("z-index:calc(var(--bn-z-drawer) + 205)", css)

    def test_m4_css_panel_stacks_above_scrim(self):
        css = UI.M4_CSS
        self.assertIn("html .bn-m4 .bn-scrim{", css)
        self.assertIn("z-index:0!important", css)
        self.assertIn("html .bn-m4 .bn-panel{position:absolute!important;", css)
        self.assertIn("z-index:1!important", css)
        self.assertIn("backdrop-filter:none!important", css)
        # settings / alert pop rules stay out of this layer
        self.assertNotIn("bn-pop", css)
        self.assertNotIn("bn-settings", css)
        self.assertNotIn("bn-pop-scrim", css)

    def test_drawer_markup_still_puts_scrim_before_panel(self):
        html = UI.drawer(__import__("sitenav"), "")
        i = html.find('class="bn-scrim"')
        j = html.find('class="bn-panel"')
        self.assertGreater(i, 0)
        self.assertGreater(j, i)

if __name__ == "__main__":
    unittest.main()
