"""Homepage dedupe + social links. Run: cd app && python3 -m unittest tests.test_home_feed -v"""
import os, sys, json, time, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import home_feed as H
XS = "https://x.com/BlkoutNtw/" + "status/"   # deleted/hidden test posts: built at runtime so the link gate skips them

NOW = time.mktime(time.strptime("2026-11-09 03:00", "%Y-%m-%d %H:%M")) - time.timezone
def C(cid, title, rank=6, fam=3, cat="political", loc=None, lat=None, lon=None, t="2026-11-08T12:00:00Z", ev=None):
    return {"cluster_id": cid, "title": title, "rank": rank, "n_families": fam, "category": cat, "location": loc, "lat": lat, "lon": lon,
            "updated": t, "first_seen": t, "event_time": ev or t}

class Dedupe(unittest.TestCase):
    def ids(self, items): return [sorted(e["cluster_ids"]) for e in H.events(items, now=NOW, limit=99)]
    def test_same_event_different_headlines(self):
        g = self.ids([C("a" * 16, "Paraguay: President under investigation for bank failure", 7, 9),
                      C("b" * 16, "Paraguay Bank Failure", 7, 7),
                      C("c" * 16, "Ousted Paraguayan president placed under house arrest after bank collapse", 5, 9),
                      C("d" * 16, "Gov. Cox declares state of emergency after repeat flooding in Southern Utah", 7, 17),
                      C("e" * 16, "DeSantis declares state of emergency for flooding in DeSoto and six other counties across Florida", 7, 11),
                      C("f" * 16, "Gov. DeSantis declares State of Emergency for 7 counties, including Brevard", 6, 2)])
        self.assertIn(["a" * 16, "b" * 16, "c" * 16], g)
        self.assertIn(["e" * 16, "f" * 16], g)
        self.assertIn(["d" * 16], g)                     # Utah is a different event, not merged with Florida
    def test_lowercase_topic_words_do_not_merge(self):
        g = self.ids([C("1" * 16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease"),
                      C("2" * 16, "Quick takes: Clade 1 mpox in California, H9N2 avian flu cases in China, more Ebola deaths", 5, 1, "disease")])
        self.assertEqual(len(g), 2)
    def test_quakes(self):
        g = self.ids([C("1" * 16, "JMA: M6.1 earthquake - Off the east Coast of Kanto, max seismic intensity 3", 5, 5, "natural disaster", "Off the east Coast of Kanto, Japan", 35.0, 142.2, ev="2026-11-06T10:39:00Z"),
                      C("2" * 16, "Magnitude 6.1 Earthquake Strikes Off Japan's Eastern Coast Near Tokyo", 6, 15, "war/conflict", ev="2026-11-07T20:00:00Z"),
                      C("3" * 16, "EMSC: M6.1 earthquake Fiji Region", 5, 3, "natural disaster", "Fiji Region", -21.1, -178.7, ev="2026-11-06T11:00:00Z"),
                      C("4" * 16, "GEOFON: M5.8 earthquake Central Mid-Atlantic Ridge", 4, 5, "natural disaster", "Central Mid-Atlantic Ridge", 7.36, -36.75, ev="2026-11-07T20:10:00Z")])
        self.assertIn(["1" * 16, "2" * 16], g); self.assertEqual(len(g), 3)
    def test_nws_reissues_and_expired(self):
        ev = H.events([C("1" * 16, "Flood Warning issued November 8 at 8:11PM CST until November 11 at 1:00PM CST by NWS Corpus Christi TX", 4, 1, "natural disaster", "Nueces, TX"),
                       C("2" * 16, "Flood Warning issued November 8 at 12:00PM CST until November 11 at 6:00PM CST by NWS Corpus Christi TX", 4, 1, "natural disaster", "Nueces, TX"),
                       C("3" * 16, "Tornado Warning issued November 3 at 11:14AM CST until November 3 at 11:45AM CST by NWS Shreveport LA", 5, 1, "natural disaster", "Bossier, LA")], now=NOW)
        self.assertEqual(len(ev), 1); self.assertEqual(ev[0]["grouped"], 2)
    def test_titles(self):
        self.assertIsNone(H.clean_title("www.threads.com/share/BCMysM...\nHope he doesn't declare martial law"))
        self.assertIsNone(H.clean_title("youtube.com/shorts/PpZNP"))
        self.assertEqual(H.clean_title("\U0001F1FA\U0001F1F8 \u2622\ufe0f \U0001F1EE\U0001F1F7 Tucker Carlson claims Donald Trump could order a strike"), "Tucker Carlson claims Donald Trump could order a strike")
        self.assertIsNone(H.clean_title("Hope he doesn't declare martial law \U0001FA78\U0001FA78"))
    def test_ranked_by_usefulness(self):
        ev = H.events([C("1" * 16, "Low rank story about something in Ohio", 3, 9), C("2" * 16, "High rank story about strikes in Kharkiv", 8, 2)], now=NOW)
        self.assertEqual(ev[0]["cluster_id"], "2" * 16)

class Links(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); H.F_LINKS = os.path.join(self.d, "social_links.json"); H._LC.update(m=None, v={})
    def write(self, stories):
        json.dump({"version": 1, "stories": stories}, open(H.F_LINKS, "w")); os.utime(H.F_LINKS, (time.time() + len(stories), time.time() + len(stories)))
    def test_only_verified_links(self):
        self.write({"a" * 16: {"x_url": "https://x.com/BlkoutNtw/status/2117653441124221070", "x_ok": True, "yt_url": "https://www.youtube.com/shorts/RONKwjR71EU", "yt_ok": False, "posted_at": "2026-11-08T23:00:00Z"},
                    "b" * 16: {"x_url": XS + "2119581032081211874", "x_ok": False, "yt_url": None, "yt_ok": False},
                    "c" * 16: {"x_url": "https://evil.example.com/BlkoutNtw/status/1", "x_ok": True},
                    "d" * 16: {"x_url": XS + "2117653441124221071", "x_ok": True, "hidden": ["x"], "yt_url": "https://www.youtube.com/shorts/rBt5RqqZOI4", "yt_ok": True}})
        L = H.links()
        self.assertEqual(set(L), {"a" * 16, "d" * 16})
        self.assertIsNone(L["a" * 16]["yt"]); self.assertIsNone(L["d" * 16]["x"]); self.assertEqual(L["a" * 16]["story"], "/wire/" + "a" * 16)
    def test_attach_and_pin(self):
        self.write({"b" * 16: {"x_url": "https://x.com/BlkoutNtw/status/2117653441124221070", "x_ok": True, "posted_at": "2026-11-09T01:00:00Z"}})
        ev = H.attach(H.events([C("a" * 16, "Paraguay: President under investigation for bank failure", 7, 9), C("b" * 16, "Paraguay Bank Failure", 7, 7)], now=NOW), now=NOW)
        self.assertEqual(len(ev), 1); self.assertTrue(ev[0]["posted"]); self.assertTrue(ev[0]["social"]["x"].endswith("2117653441124221070"))

if __name__ == "__main__": unittest.main()
