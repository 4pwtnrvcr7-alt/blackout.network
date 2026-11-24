"""Reworked standalone pages (solo.py, Nov 24 2026 pt1846u): serve 200, stay unlisted, no emoji, no yellow, text wordmark."""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import solo, deactivated as D

class Solo(unittest.TestCase):
    def test_pages_serve_and_stay_unlisted(self):
        for p in solo.PATHS:
            r = solo.handle_get(p, {}); self.assertEqual(r[0], 200, p); b = r[1]
            self.assertIn('class="w2-wm"', b); self.assertIn("blackout.network</a>", b)
            self.assertIsNone(solo._EMO.search(b), p)
            self.assertIsNone(re.search(r"#(?:ffd666|facc15|fbbf24)\b", b, re.I), p)
            self.assertTrue(D.is_off(p), p); self.assertFalse(D.redirects(p), p)
    def test_assets(self):
        for n in ["solo.css", "solo.js"] + ["js/%s.js" % k for k in solo.ADDON_JS]:
            r = solo.handle_get("/api/solo/" + n, {}); self.assertEqual(r[0], 200, n)
        self.assertIsNone(solo._EMO.search(solo.handle_get("/api/solo/js/preppers.js", {})[1].decode()))
        self.assertEqual(solo.handle_get("/api/solo/js/../x.js", {})[0], 404)
    def test_kill_switch(self):
        os.environ["BN_SOLO"] = "0"
        try: self.assertEqual(solo.handle_get("/games", {})[0], 404)
        finally: os.environ.pop("BN_SOLO")

if __name__ == "__main__": unittest.main()
