"""Floating Report a problem button is gone site-wide (Matt 11:33 PM ET Nov 27)."""
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class ReportFabGone(unittest.TestCase):
    def test_js_does_not_inject_fab(self):
        js = open(os.path.join(ROOT, "reports_static", "app.js"), encoding="utf-8").read()
        self.assertNotIn("init(){fab();", js)
        self.assertNotIn('class":"bnr-fab"', js)
        self.assertNotIn("document.body.appendChild(b)", js)
        self.assertIn("function init(){flags();", js)
        self.assertIn("window.BNReport={open:open", js)

    def test_css_hides_fab_and_drops_reserved_space(self):
        css = open(os.path.join(ROOT, "reports_static", "app.css"), encoding="utf-8").read()
        self.assertIn(".bnr-fab{display:none!important", css)
        self.assertNotIn("html body{padding-bottom:calc(56px + env(safe-area-inset-bottom))!important}", css)
        # per-item flags stay
        self.assertIn(".bnr-flag{", css)

    def test_map_report_opens_form_without_fab(self):
        js = open(os.path.join(ROOT, "signal_map_static", "map2.js"), encoding="utf-8").read()
        self.assertIn("BNReport.open", js)
        self.assertNotIn('querySelector(".bnr-fab")', js)

if __name__ == "__main__":
    unittest.main()
