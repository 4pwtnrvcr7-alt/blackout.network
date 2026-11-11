"""Nuclear threat and Election disputes cards: per-day stories so day bars are clickable like the other threat cards.
Run: cd app && python3 -m unittest tests.test_special_cards -v
"""
import os, re, sys, time, sqlite3, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import apple_v1 as A

# ~Tuesday Nov 10, 2026 15:00 UTC (10:00 AM ET)
NOW = time.mktime(time.strptime("2026-11-10 15:00", "%Y-%m-%d %H:%M")) - time.timezone

def seed(db, rows):
    c = sqlite3.connect(db)
    c.execute("""CREATE TABLE clusters (
      cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
      event_time TEXT, first_seen TEXT, updated TEXT, score INT, confidence TEXT, n_items INT,
      n_families INT, families TEXT, links TEXT, watchlist INT, brief TEXT, high_at TEXT,
      rising INT, mentions_3h INT, eff_families INT, rank INT, pushed_at TEXT)""")
    for r in rows:
        c.execute("INSERT INTO clusters (cluster_id,title,category,location,first_seen,updated,watchlist,rank,n_families) VALUES (?,?,?,?,?,?,?,?,?)", r)
    c.commit(); c.close()

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "bn-apple-home.js")


class SpecialCardsStories(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(); self.db = os.path.join(self.td, "blackout.db")
        self._base = A.BASE; A.BASE = self.td
        rows = [
            ("a"*16, "Iran test-fires Fattah-1 hypersonic warheads in a new military drill", "war/conflict", None,
             "2026-11-10T14:00:00Z", "2026-11-10T14:00:00Z", 0, 6, 3),
            ("b"*16, "IAEA reports new uranium enrichment activity at a declared nuclear facility", "other", None,
             "2026-11-08T12:00:00Z", "2026-11-08T12:00:00Z", 0, 5, 2),
            ("c"*16, "Republicans file a lawsuit challenging ballot certification in Georgia", "political", "Georgia",
             "2026-11-10T13:00:00Z", "2026-11-10T13:00:00Z", 0, 4, 2),
            ("d"*16, "A county clerk extends voting hours after a polling-place glitch", "political", None,
             "2026-11-09T18:00:00Z", "2026-11-09T18:00:00Z", 1, 2, 1),
            ("e"*16, "Shoppers find cheaper milk at the grocery store this week", "other", None,
             "2026-11-10T12:00:00Z", "2026-11-10T12:00:00Z", 0, 1, 1),
        ]
        seed(self.db, rows)

    def tearDown(self):
        A.BASE = self._base

    def test_nuke_and_disp_include_stories_by_day(self):
        s = A.special_cards(NOW)
        nuke, disp = s["nuke"], s["disp"]
        self.assertIn("stories", nuke)
        self.assertIn("stories", disp)
        self.assertEqual(list(nuke["stories"]), [d[0] for d in nuke["days"]])
        nuke_titles = [x["title"] for v in nuke["stories"].values() for x in v]
        self.assertTrue(any("Fattah-1" in t or "warheads" in t for t in nuke_titles))
        self.assertTrue(any("IAEA" in t or "uranium" in t for t in nuke_titles))
        self.assertFalse(any("milk" in t.lower() for t in nuke_titles))
        days_with = [d[0] for d in nuke["days"] if d[1] + d[2] > 0]
        self.assertTrue(days_with)
        self.assertTrue(all(nuke["stories"].get(d) for d in days_with))
        st = nuke["stories"][days_with[-1]][0]
        self.assertTrue(st["url"].startswith("/wire/"))
        self.assertIn("rank", st)
        self.assertIn("src", st)
        disp_titles = [x["title"] for v in disp["stories"].values() for x in v]
        self.assertTrue(any("lawsuit" in t.lower() or "ballot" in t.lower() or "polling" in t.lower() for t in disp_titles))
        self.assertFalse(any("warheads" in t for t in disp_titles))
        self.assertIsNotNone(nuke.get("top"))
        self.assertIn("Fattah-1", nuke["top"]["title"] or "")

    def test_js_passes_day_keys_for_special_cards(self):
        with open(JS) as f: js = f.read()
        self.assertIn("bars(cols(N),{labels:1,days:dayKeys(N)})", js)
        self.assertIn("bars(cols(P),{labels:1,days:dayKeys(P)})", js)
        self.assertIn("cn._bnaO=N", js)
        self.assertIn("cp._bnaO=P", js)
        # Other 7-day threat cards already go through wg(), which passes days.
        self.assertIn("c:bars(cols,{labels:1,days:dayKeys})", js)
        # Nuclear/disputes must not still call bars without days.
        self.assertNotIn("bars(cols(N),{labels:1}),", js)
        self.assertNotIn("bars(cols(P),{labels:1}),", js)


if __name__ == "__main__":
    unittest.main()
