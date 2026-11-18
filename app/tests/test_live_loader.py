""" /live vacuum-strip loader + per-module skeletons (Nov 17 2026, 8:20 PM ET).
    Run: cd app && python3 -m unittest tests.test_live_loader tests.test_theme tests.test_menu_icon -v
"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import theme

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as f: return f.read()

class Markup(unittest.TestCase):
    def test_overview_ships_vacuum_strip_and_skeletons(self):
        h = theme.live_overview_html()
        self.assertIn('id="bntl"', h)
        self.assertIn("l-loading", h)
        self.assertIn('aria-busy="true"', h)
        self.assertIn('id="bntl_acq"', h)
        self.assertIn('id="bntl_acq_cv"', h)
        self.assertIn('id="bntl_acq_pct"', h)
        self.assertIn("l-acq-unit", h)
        self.assertIn(">00<", h)
        self.assertIn("Loading 0 percent", h)
        self.assertIn("l-sk-gauge", h)
        self.assertIn("l-sk-card", h)
        self.assertEqual(h.count("l-sk-card"), 3)
        self.assertEqual(h.count("l-sk-bar"), 11)
        self.assertIn("l-sk-map", h)
        self.assertIn("l-sk-vol", h)
        self.assertIn("/?intro=1", h)
        self.assertNotIn("Acquiring signals", h)
        self.assertNotIn("l-acq-globe", h)
        self.assertNotIn("Wire desk", h)
        self.assertNotIn("Seismic net", h)
        self.assertNotIn("bntl_acq_n", h)
        self.assertNotRegex(h, r"\bchannels\b")
        self.assertIsNone(re.search("[\U0001F000-\U0001FAFF\u2600-\u27BF]", h))
        self.assertNotRegex(h.lower(), r"verified|before the news")

    def test_flag_off_drops_strip(self):
        old = os.environ.get("BN_LIVE_ACQ")
        os.environ["BN_LIVE_ACQ"] = "0"
        try:
            self.assertFalse(theme.live_acq_on())
            h = theme.live_overview_html()
            self.assertNotIn("l-loading", h)
            self.assertNotIn("bntl_acq", h)
            self.assertNotIn("aria-busy", h)
            self.assertIn('id="bntl"', h)
        finally:
            if old is None: os.environ.pop("BN_LIVE_ACQ", None)
            else: os.environ["BN_LIVE_ACQ"] = old

class Assets(unittest.TestCase):
    def test_css_compact_strip_and_mono(self):
        css = _read("theme_static", "live.css")
        self.assertIn("live vacuum strip", css)
        self.assertIn("height:52px", css)
        self.assertIn("height:48px", css)
        self.assertIn("l-acq-fold", css)
        self.assertIn("@keyframes l-scan", css)
        self.assertIn("@keyframes l-up", css)
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertIn(".bnt-live.l-loading .l-acq", css)
        self.assertIn(".bnt-live.l-ready .l-acq", css)
        self.assertNotIn("@keyframes l-sweep", css)
        self.assertNotIn("@keyframes l-tick", css)
        tail = css.split("live vacuum strip", 1)[1]
        self.assertNotRegex(tail, r"#F5A|#FFD|#F2C|yellow|#FF0", "strip CSS stays monochrome")
        # red accent lives on the canvas, not in CSS
        self.assertNotIn("#FF4D4F", tail)

    def test_js_progress_canvas_and_no_retrigger(self):
        js = _read("theme_static", "live.js")
        self.assertIn("MIN=reduce?0:1200", js)
        self.assertIn("acqPart", js)
        self.assertIn("reveal=function()", js)
        self.assertIn("failSoft=function()", js)
        self.assertIn("if(!revealed)reveal()", js)
        self.assertIn("prefers-reduced-motion: reduce", js)
        self.assertIn("getContext(\"2d\"", js)
        self.assertIn("Math.min(t,98)", js)
        self.assertIn("shown=100", js)
        self.assertIn("#FF4D4F", js)
        self.assertIn("setInterval(function(){if(!d.hidden&&root.getBoundingClientRect().height>0)load()}", js)
        self.assertNotIn("bntl_acq_n", js)
        self.assertNotIn("Acquiring", js)
        self.assertNotIn("Wire desk", js)

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
        self.assertIn("bn_settings", chunk)

if __name__ == "__main__":
    unittest.main()
