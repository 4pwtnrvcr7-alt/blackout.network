"""New theme (Nov 17 2026): "/" onboarding, /live overview summary, wordmark."""
import os, re, sys, types, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import theme

STATE = {"generated": "2026-11-17T04:42:20Z", "watchlist_count": 3, "interval_minutes": 60,
         "main": [{"cluster_id": "a" * 16, "title": "Quake \U0001F30B M6.6 near coast", "rank": 7, "score": 80, "n_families": 3, "category": "natural disaster",
                   "location": "Indonesia", "first_seen": "2026-11-16T20:00:00Z", "lat": -7.1, "lon": 131.2},
                  {"cluster_id": "b" * 16, "title": "Single source", "rank": 8, "score": 90, "n_families": 1, "category": "cyber", "first_seen": "2026-11-16T20:00:00Z"},
                  {"cluster_id": "c" * 16, "title": "Calm item", "rank": 2, "score": 10, "n_families": 2, "category": "political", "first_seen": "2026-11-16T20:00:00Z"}],
         "volume": [{"d": "2026-11-15", "category": "cyber", "n": 4}, {"d": "2026-11-16", "category": "political", "n": 9}],
         "sources": [{"ok": 1}, {"ok": 0}], "scans": [{"finished": "2026-11-17T04:37:26Z", "fetched": 900, "new_items": 13}]}

class Summary(unittest.TestCase):
    def setUp(self):
        fake = types.SimpleNamespace(api_state=lambda: STATE)
        self._old = sys.modules.get("server"); sys.modules["server"] = fake; theme._sum.update(t=0, v=None)
    def tearDown(self):
        if self._old is not None: sys.modules["server"] = self._old
        else: sys.modules.pop("server", None)
    def test_numbers(self):
        s = theme.summary()
        self.assertEqual(s["wire"], 3); self.assertEqual(s["bands"], {"calm": 1, "elevated": 0, "high": 2})
        self.assertEqual(s["sources_ok"], 1); self.assertEqual(s["sources_total"], 2); self.assertEqual(s["last_scan_et"], "11:37 PM ET")
        self.assertEqual([t["url"] for t in s["top"]], ["/wire/" + "a" * 16, "/wire/" + "c" * 16])   # 2+ source families only, rank first
        self.assertNotIn("\U0001F30B", s["top"][0]["title"])
        self.assertEqual(s["volume"][-1], {"d": "Mon", "n": 9}); self.assertEqual(s["cats"], {"Politics": 9})

class Home(unittest.TestCase):
    def test_home_page(self):
        h = theme.home_page()
        self.assertIn('<link rel="canonical" href="https://blackout.network/">', h)
        self.assertIn("location.replace('/live'", h)
        self.assertIn('data-bn-alerts', h); self.assertIn('id="nl_app"', h)
        self.assertNotIn('href="/#', h)
        self.assertNotRegex(h.lower(), r"meshtastic|lora\b|/welcome|verified|before the news|concept preview")
        self.assertIsNone(re.search("[\U0001F000-\U0001FAFF\u2600-\u27BF]", h))
        self.assertIn('<span class="bnt-wm">blackout.network</span>', h)
    def test_overview(self):
        h = theme.live_overview_html()
        self.assertIn('id="bntl"', h); self.assertIn('/?intro=1', h)
        self.assertIn('id="bntl_acq"', h); self.assertIn("Acquiring signals", h)
        self.assertIn("l-loading", h)

if __name__ == "__main__": unittest.main()
