"""Wire-group widget filters (civil unrest, UK, food, quake-exclusion). Run: cd app && python3 -m unittest tests.test_wire_groups -v"""
import os, sys, time, sqlite3, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import apple_v1 as A

NOW = time.mktime(time.strptime("2026-11-09 03:00", "%Y-%m-%d %H:%M")) - time.timezone  # ~ET morning Nov 9 as UTC-ish

def seed(db, rows):
    c = sqlite3.connect(db)
    c.execute("""CREATE TABLE clusters (
      cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
      event_time TEXT, first_seen TEXT, updated TEXT, score INT, confidence TEXT, n_items INT,
      n_families INT, families TEXT, links TEXT, watchlist INT, brief TEXT, high_at TEXT,
      rising INT, mentions_3h INT, eff_families INT, rank INT, pushed_at TEXT)""")
    for r in rows:
        c.execute("INSERT INTO clusters (cluster_id,title,category,location,first_seen,updated,watchlist,rank,n_families) VALUES (?,?,?,?,?,?,0,?,?)", r)
    c.commit(); c.close()

class WireGroups(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(); self.db = os.path.join(self.td, "blackout.db")
        self._base = A.BASE; A.BASE = self.td
        rows = [
            ("a"*16, "France sees fresh mass protests as police move to block banned rally", "political", None, "2026-11-08T12:00:00Z", "2026-11-08T12:00:00Z", 5, 4),
            ("b"*16, "How the new Charlotte curfew for minors could impact parents", "political", "Charlotte, NC", "2026-11-08T10:00:00Z", "2026-11-08T10:00:00Z", 3, 3),
            ("k"*16, "Protesters clash with police outside ICE facility in Portland, Oregon", "political", "Portland, OR", "2026-11-08T10:30:00Z", "2026-11-08T10:30:00Z", 4, 3),
            ("c"*16, "Shops looted in Frankfurt as riots erupt in Germany after protests", "political", None, "2026-11-07T12:00:00Z", "2026-11-07T12:00:00Z", 4, 2),
            ("d"*16, "Breaking News British couple in Krakow recall seeing 250 people running after shooting", "political", None, "2026-11-08T11:00:00Z", "2026-11-08T11:00:00Z", 2, 1),
            ("e"*16, "From California Milk to Nara Cans: The Supply Chain Behind the Second Infant Formula Botulism Scare", "disease", None, "2026-11-08T09:00:00Z", "2026-11-08T09:00:00Z", 2, 2),
            ("f"*16, "Magnitude 6.1 Earthquake Strikes Off Japan's Eastern Coast Near Tokyo", "war/conflict", None, "2026-11-08T08:00:00Z", "2026-11-08T08:00:00Z", 6, 5),
            ("g"*16, "Cyber chief: UK facing AI-powered attacks on critical infrastructure within two years", "cyber", "United Kingdom", "2026-11-08T07:00:00Z", "2026-11-08T07:00:00Z", 3, 2),
            ("h"*16, "Russian drone targets rescuers at Komyshuvakha site where 55 died in airstrikes", "war/conflict", None, "2026-11-08T06:00:00Z", "2026-11-08T06:00:00Z", 6, 8),
            ("i"*16, "United Kingdom deploys extra police in London ahead of mass protest", "political", "London", "2026-11-08T05:00:00Z", "2026-11-08T05:00:00Z", 4, 3),
            ("j"*16, "Italy braces for mass protests, strikes against Meloni government", "political", None, "2026-11-08T04:00:00Z", "2026-11-08T04:00:00Z", 2, 2),
            ("m"*16, "Egypt holds fertilizer and grain shipments after Red Sea disruption", "other", None, "2026-11-08T03:00:00Z", "2026-11-08T03:00:00Z", 3, 2),
        ]
        seed(self.db, rows)
    def tearDown(self):
        A.BASE = self._base
    def test_civil_unrest_us_and_world(self):
        g = A.wire_groups(NOW)
        u = g["hard"]["unrest"]
        self.assertEqual(u["label"], "Civil unrest")
        self.assertGreaterEqual(u["n7"], 4)          # FR, Portland, Frankfurt, Italy (+ maybe more)
        self.assertGreaterEqual(u["us"]["n7"], 1)    # Portland (minors' curfew is excluded)
        alltitles = [x["title"] for v in u["stories"].values() for x in v]
        self.assertFalse(any("curfew for minors" in x for x in alltitles))
        self.assertGreaterEqual(u["world"]["n7"], 2) # FR, Frankfurt, Italy
        self.assertIn("stories", u)
        # day stories present for a day with counts
        days_with = [d[0] for d in u["days"] if d[1] + d[2] > 0]
        self.assertTrue(days_with)
        self.assertTrue(any(u["stories"].get(d) for d in days_with))
    def test_food_ignores_recall_verb(self):
        g = A.wire_groups(NOW)
        f = g["hard"]["food"]
        self.assertGreaterEqual(f["n7"], 2)  # infant formula supply chain + fertilizer/grain
        self.assertNotIn("Krakow", (f.get("top") or {}).get("title") or "")
    def test_quake_not_in_conflict_other(self):
        g = A.wire_groups(NOW)
        titles = []
        for day, stories in (g["conf"]["other"].get("stories") or {}).items():
            titles += [s["title"] for s in stories]
        if g["conf"]["other"].get("top"):
            titles.append(g["conf"]["other"]["top"]["title"])
        self.assertFalse(any("Earthquake" in t or "earthquake" in t for t in titles))
        self.assertGreaterEqual(g["conf"]["ru"]["n7"], 1)
    def test_uk_includes_united_kingdom_and_security(self):
        g = A.wire_groups(NOW)
        uk = g["conf"]["uk"]
        self.assertGreaterEqual(uk["n7"], 2)  # cyber UK + London protest
        blob = " ".join(s["title"] for stories in (uk.get("stories") or {}).values() for s in stories)
        self.assertTrue("London" in blob or "UK" in blob or "United Kingdom" in blob or "protest" in blob.lower() or "Cyber" in blob)

if __name__ == "__main__":
    unittest.main()
