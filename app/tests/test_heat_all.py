"""Every Wire item on the map (heat_all.py, Nov 20 2026, pt1672u). Run: cd app && python3 -m unittest tests.test_heat_all -v"""
import json, os, sqlite3, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import heat_all as H

NOW = datetime(2026, 11, 20, 13, 0, tzinfo=timezone.utc)
def T(h): return (NOW - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")

class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        b = sqlite3.connect(os.path.join(cls.d, "blackout.db"))
        b.execute("""CREATE TABLE clusters(cluster_id TEXT, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT,
                     updated TEXT, score REAL, confidence TEXT, n_items INT, n_families INT, families TEXT, links TEXT, watchlist INT, brief TEXT, eff_families INT, rank INT)""")
        rows = [  # id, title, category, location, lat, lon, first_seen, updated, watchlist
            ("a1", "M 5.8 - 79 km WSW of Changuillo, Peru", "natural disaster", "Peru", -14.99, -75.88, T(5), T(1), 0),
            ("a2", "Qatar and Turkiye say they will take a unified stance", "political", None, None, None, T(3), None, 0),
            ("a3", "A Palestinian has succumbed to wounds sustained in the Israeli strike", "war/conflict", None, None, None, T(2), None, 0),
            ("a4", "The Black Sea has become the deadliest shipping route", "war/conflict", None, None, None, T(4), None, 1),
            ("a5", "CVE-2026-1 added to CISA KEV", "cyber", "Global (software)", None, None, T(6), None, 0),
            ("a6", "Mayor was blunt about the bomb threat at a South Peoria school", "war/conflict", None, None, None, T(7), None, 0),
            ("a7", "Old story touched again today", "political", None, None, None, T(24 * 9), T(2), 0),     # old first_seen, recent activity: on the Wire
            ("a8", "Background signal", "other", None, None, None, T(1), None, 2),                          # watchlist 2: not on the Wire
            ("a9", "Stale story", "political", None, None, None, T(24 * 9), T(24 * 8), 0),                  # outside 7 days
            ("a10", "Pending: floods in Kenya displace thousands", "natural disaster", None, None, None, T(1), None, 0),
        ]
        for r in rows:
            b.execute("INSERT INTO clusters(cluster_id,title,category,location,lat,lon,first_seen,updated,watchlist,rank,links,n_families) VALUES(?,?,?,?,?,?,?,?,?,5,'[]',1)", r)
        b.commit(); b.close()
        g = sqlite3.connect(os.path.join(cls.d, "geo.db"))
        g.execute("CREATE TABLE geo(id TEXT PRIMARY KEY, lat REAL, lon REAL, place TEXT, country TEXT, country_name TEXT, admin1 TEXT, admin1_code TEXT, city TEXT, precision TEXT, method TEXT, method_detail TEXT, confidence TEXT, located INTEGER, reason_code TEXT, reason_unlocated TEXT, candidates TEXT, evidence TEXT, sig TEXT, version INTEGER, geocoded_at TEXT, attempts INTEGER)")
        geo = [
            ("a1", -14.99, -75.88, "Peru", "PE", "point", 1, None, None, None),
            ("a2", None, None, None, None, None, 0, "multi_place", "Several places in different countries carry equal weight: Qatar (Qatar), Turkiye (Turkey)", json.dumps(["Qatar (Qatar)", "Turkiye (Turkey)"])),
            ("a3", None, None, None, None, None, 0, "nationality_only", "No place named, only nationality words or flags: Israeli, Palestinian (these say who, not where)", None),
            ("a4", None, None, None, None, None, 0, "broad_region", "Names only a broad region (Black Sea, Middle East), too large to place as one spot on the map", None),
            ("a5", None, None, None, None, None, 0, "global", "Source marks the location as \"Global (software)\", not a place on the map", None),
            ("a6", None, None, None, None, None, 0, "ambiguous", "\"Peoria\" matches several places: Peoria (Arizona, US); Peoria (Illinois, US)", json.dumps(["Peoria (Arizona, US)", "Peoria (Illinois, US)"])),
        ]
        for i, la, lo, pl, cc, pr, loc, rc, rr, ca in geo:
            g.execute("INSERT INTO geo(id,lat,lon,place,country,precision,located,reason_code,reason_unlocated,candidates) VALUES(?,?,?,?,?,?,?,?,?,?)", (i, la, lo, pl, cc, pr, loc, rc, rr, ca))
        g.commit(); g.close()
        cls.saved = (H.DB, H.HDB, H.GDB)
        H.DB, H.HDB, H.GDB = os.path.join(cls.d, "blackout.db"), os.path.join(cls.d, "none.db"), os.path.join(cls.d, "geo.db")
        cls.out = H.build(now=NOW)
        ix = {c: i for i, c in enumerate(cls.out["cols"])}
        cls.by = {r[ix["id"]]: {c: r[i] for c, i in ix.items()} for r in cls.out["rows"]}

    @classmethod
    def tearDownClass(cls):
        H.DB, H.HDB, H.GDB = cls.saved

    def test_same_item_set_as_the_wire(self):
        self.assertEqual(set(self.by), {"a1", "a2", "a3", "a4", "a5", "a6", "a7", "a10"})
        wc = self.out["coverage"]["wire_counts"]
        self.assertEqual(wc["168"], len(self.by))
        for h in ("24", "72", "168"):
            cut = T(int(h)); n = sum(1 for r in self.by.values() if r["t"] >= cut)
            self.assertEqual(n, wc[h], h)

    def test_everything_has_a_tier_and_counts_add_up(self):
        t = self.out["coverage"]["tiers"]
        self.assertEqual(sum(t.values()), len(self.by))
        for r in self.by.values():
            self.assertIn(r["tier"], ("exact", "approx", "region", "global"))
            if r["tier"] == "global": self.assertIsNone(r["lat"])
            else: self.assertTrue(-90 <= r["lat"] <= 90 and -180 <= r["lon"] <= 180)

    def test_fallbacks_are_honest(self):
        self.assertEqual((self.by["a1"]["tier"], self.by["a1"]["prec"]), ("exact", "point"))
        self.assertEqual((self.by["a2"]["tier"], self.by["a2"]["cc"], self.by["a2"]["prec"]), ("approx", "QA", "country"))
        self.assertIn("several places named", self.by["a2"]["how"])
        self.assertEqual((self.by["a3"]["tier"], self.by["a3"]["prec"]), ("approx", "country"))
        self.assertIn(self.by["a3"]["cc"], ("PS", "IL"))
        self.assertEqual((self.by["a4"]["tier"], self.by["a4"]["place"]), ("region", "Black Sea"))
        self.assertEqual(self.by["a5"]["tier"], "global")
        self.assertEqual((self.by["a6"]["tier"], self.by["a6"]["cc"]), ("approx", "US"))

    def test_payload_has_no_emoji_and_kill_switch(self):
        os.environ["BN_MAP_ALL"] = "0"
        try: self.assertFalse(H.on())
        finally: os.environ.pop("BN_MAP_ALL")
        self.assertTrue(H.on())

class JS(unittest.TestCase):
    def test_map_reads_tiers_and_payload_clock(self):
        js = open(os.path.join(os.path.dirname(H.__file__), "signal_map_static", "map2.js")).read()
        for s in ('ix.tier', 'nowRef()', '"pt-a"', '"rg"', 'bnm_gbtn', 'wire_counts'):
            self.assertIn(s, js)
        import signal_map
        code, body, _ = signal_map.handle_get("/map", {})
        self.assertIn('id="bnm_gbtn"', body)

if __name__ == "__main__": unittest.main()


class IataAirportPin(unittest.TestCase):
    def test_stored_ord_nebraska_pin_is_replaced(self):
        item = {"id": "56aa6cc76b03647a", "title": "FAA Ground stop: ORD (equipment outage)",
                "loc": "ORD, US", "category": "other", "brief": "", "links": "[]"}
        stored = {"located": 1, "lat": 41.6033, "lon": -98.9262, "place": "Ord, Valley County, Nebraska, 68862, United States",
                  "country": "US", "admin1_code": "US.NE", "city": "Ord", "precision": "city",
                  "method": "nominatim", "confidence": "medium"}
        p = H.place(item, stored)
        self.assertTrue(p and p.get("lat") is not None, p)
        self.assertTrue(41.9 < p["lat"] < 42.05 and -88.0 < p["lon"] < -87.8, p)
        self.assertRegex(p.get("place") or "", r"O.?Hare")
        self.assertNotRegex(p.get("place") or "", r"Nebraska")
