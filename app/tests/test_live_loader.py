""" /live acquisition overlay + per-module skeletons (Nov 17 2026).
    Run: cd app && python3 -m unittest tests.test_live_loader tests.test_theme tests.test_menu_icon -v
"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import theme

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as f: return f.read()

class Markup(unittest.TestCase):
    def test_overview_ships_acquisition_and_skeletons(self):
        h = theme.live_overview_html()
        self.assertIn('id="bntl"', h)
        self.assertIn("l-loading", h)
        self.assertIn('aria-busy="true"', h)
        self.assertIn('id="bntl_acq"', h)
        self.assertIn("Acquiring signals", h)
        self.assertIn("blackout.network", h)
        self.assertIn("l-acq-globe", h)
        self.assertIn("l-acq-sweep", h)
        self.assertIn("Wire desk", h)
        self.assertIn("l-sk-gauge", h)
        self.assertIn("l-sk-card", h)
        self.assertEqual(h.count("l-sk-card"), 3)
        self.assertEqual(h.count("l-sk-bar"), 11)
        self.assertIn("l-sk-map", h)
        self.assertIn("l-sk-vol", h)
        self.assertIn("/?intro=1", h)
        self.assertIsNone(re.search("[\U0001F000-\U0001FAFF\u2600-\u27BF]", h))
        self.assertNotRegex(h.lower(), r"verified|before the news")

class Assets(unittest.TestCase):
    def test_css_motion_and_mono(self):
        css = _read("theme_static", "live.css")
        self.assertIn("live acquisition", css)
        self.assertIn("@keyframes l-sweep", css)
        self.assertIn("@keyframes l-scan", css)
        self.assertIn("@keyframes l-tick", css)
        self.assertIn("@keyframes l-fade", css)
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertIn(".bnt-live.l-loading .l-acq", css)
        self.assertIn(".bnt-live.l-ready .l-acq", css)
        tail = css.split("live acquisition", 1)[1]
        self.assertNotRegex(tail, r"#F5A|#FFD|#F2C|yellow|#FF0", "loader stays monochrome")
        self.assertNotIn("#FF4D4F", tail)

    def test_js_min_display_and_no_retrigger(self):
        js = _read("theme_static", "live.js")
        self.assertIn("MIN=reduce?0:600", js)
        self.assertIn("function reveal()", js)
        self.assertIn("function failSoft()", js)
        self.assertIn("if(!revealed)reveal()", js)
        self.assertIn("prefers-reduced-motion: reduce", js)
        # interval refresh still calls load() but reveal() no-ops once shown
        self.assertIn("setInterval(function(){if(!d.hidden&&root.getBoundingClientRect().height>0)load()}", js)
        self.assertIn("if(revealed||!root.classList.contains(\"l-loading\"))return", js)

class MenuEscape(unittest.TestCase):
    def test_sitenav_has_document_escape(self):
        js = _read("static", "sitenav.js")
        self.assertIn('document.addEventListener("keydown",function(e){if(e.key!=="Escape"', js)
        self.assertIn("bn-settings-open", js)
        i = js.find('document.addEventListener("keydown",function(e){if(e.key!=="Escape"')
        self.assertGreater(i, 0)
        chunk = js[i:i+700]
        self.assertIn("bnMenuClose()", chunk)
        self.assertIn("bn-open", chunk)
        # still does not steal from the settings pop
        self.assertIn("bn_settings", chunk)

if __name__ == "__main__":
    unittest.main()
