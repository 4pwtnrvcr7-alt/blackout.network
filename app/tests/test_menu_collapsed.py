"""Mobile menu starts fully collapsed (t1310u). Run: cd app && python3 -m unittest tests.test_menu_collapsed -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sitenav
import sitenav_ui as UI

DETAILS_OPEN = re.compile(r"<details\b[^>]*\bopen\b", re.I)
CURRENT = re.compile(r'<a\b[^>]*aria-current="page"[^>]*>', re.I)

import os as _os_d, sys as _sys_d
_sys_d.path.insert(0, _os_d.path.dirname(_os_d.path.dirname(_os_d.path.abspath(__file__))))
try:
    import deactivated as _deact_mod; _DEACT_ON = _deact_mod.ON
except Exception:
    _DEACT_ON = False
import unittest
class MenuCollapsed(unittest.TestCase):
    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_drawer_has_no_preopened_sections(self):
        for active in ("", "threat", "sources", "newsletter", "net"):
            html = UI.drawer(sitenav, active=active)
            self.assertNotRegex(html, DETAILS_OPEN, f"details pre-opened for active={active!r}")
            self.assertGreaterEqual(html.count('<details class="bn-grp'), 5)
            if active:
                self.assertRegex(html, CURRENT)

    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_current_page_is_highlighted_inside_a_closed_section(self):
        html = UI.drawer(sitenav, active="threat")
        self.assertIn('data-tab="threat" aria-current="page"', html)
        # The Wire sits in 01 Live; that details tag must not have the open attribute
        m = re.search(r'<details class="bn-grp m3-p m3-latest"[^>]*>', html)
        self.assertIsNotNone(m)
        self.assertNotIn(" open", m.group(0))
