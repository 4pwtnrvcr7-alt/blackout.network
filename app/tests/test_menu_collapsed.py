"""Mobile menu starts fully collapsed (t1310u). Run: cd app && python3 -m unittest tests.test_menu_collapsed -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sitenav
import sitenav_ui as UI

DETAILS_OPEN = re.compile(r"<details\b[^>]*\bopen\b", re.I)
CURRENT = re.compile(r'<a\b[^>]*aria-current="page"[^>]*>', re.I)

class MenuCollapsed(unittest.TestCase):
    def test_drawer_has_no_preopened_sections(self):
        for active in ("", "threat", "sources", "@stats", "net"):
            html = UI.drawer(sitenav, active=active)
            self.assertNotRegex(html, DETAILS_OPEN, f"details pre-opened for active={active!r}")
            self.assertGreaterEqual(html.count('<details class="bn-grp'), 7)
            if active:
                self.assertRegex(html, CURRENT)

    def test_current_page_is_highlighted_inside_a_closed_section(self):
        html = UI.drawer(sitenav, active="threat")
        self.assertIn('data-tab="threat" aria-current="page"', html)
        # The Wire sits in 01 Latest; that details tag must not have the open attribute
        m = re.search(r'<details class="bn-grp m3-p m3-latest"[^>]*>', html)
        self.assertIsNotNone(m)
        self.assertNotIn(" open", m.group(0))
