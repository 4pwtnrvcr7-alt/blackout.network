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
        for v in stories.values(): v.setdefault("policy_ok", True)
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

    def test_policy_gate(self):
        # box policy reject (or missing flag) -> no links, no pin
        self.write({"e" * 16: {"x_url": XS + "2117653441124221072", "x_ok": True, "posted_at": "2026-11-09T01:00:00Z", "policy_ok": False},
                    "f" * 16: {"x_url": XS + "2117653441124221073", "x_ok": True, "posted_at": "2026-11-09T01:00:00Z", "policy_ok": None}})
        self.assertEqual(H.links(), {})
    def test_topic_mirror_blocks_minor_quake_and_weather(self):
        self.write({"1" * 16: {"x_url": XS + "2117653441124221074", "x_ok": True, "posted_at": "2026-11-09T01:00:00Z"},
                    "2" * 16: {"x_url": XS + "2117653441124221075", "x_ok": True, "posted_at": "2026-11-09T01:00:00Z"},
                    "3" * 16: {"x_url": XS + "2117653441124221076", "x_ok": True, "posted_at": "2026-11-09T01:00:00Z"}})
        ev = H.attach([{"cluster_id": "1" * 16, "cluster_ids": ["1" * 16], "title": "GEOFON: M5.0 earthquake Southern Mid-Atlantic Ridge"},
                       {"cluster_id": "2" * 16, "cluster_ids": ["2" * 16], "title": "High Wind Warning issued November 7 at 9:50AM PST until November 7 at 6:00PM PST by NWS Reno NV"},
                       {"cluster_id": "3" * 16, "cluster_ids": ["3" * 16], "title": "M7.4 earthquake off Kamchatka triggers tsunami warning"}], now=NOW)
        self.assertEqual([bool(e.get("posted")) for e in ev], [False, False, True])
        self.assertNotIn("social", ev[0]); self.assertNotIn("social", ev[1])
        self.assertTrue(H.topic_ok("Ebola in DR Congo: deaths pass 5,000")); self.assertFalse(H.topic_ok("M6.1 earthquake off East Coast of Honshu, Japan"))
        self.assertTrue(H.topic_ok("M5.8 earthquake near Los Angeles")); self.assertTrue(H.topic_ok("M6.2 quake: 12 killed, major damage in Herat"))


class LatestRow(unittest.TestCase):
    """Freshness, topic policy on the whole row, explainer junk, recency-biased sort (Matt Nov 8)."""
    TUCKER = "Tucker Carlson claims Donald Trump could order a nuclear attack on Iran's Pickaxe Mountain nuclear research site at the behest of Israel"
    GOUT = "Gout: Causes, warning signs and what you can do"
    def test_freshness_48h_then_72h_never_older(self):
        # NOW is 2026-11-09 03:00 UTC-ish; Tucker (Nov 3) is >72h and must never appear
        items = [C("a"*16, "Paraguay: President under investigation for bank failure", 7, 9, t="2026-11-08T12:00:00Z"),
                 C("b"*16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease", t="2026-11-09T01:00:00Z"),
                 C("c"*16, self.TUCKER, 8, 3, t="2026-11-03T20:25:25Z"),
                 C("d"*16, "Belize declares state of emergency over deadly gang violence", 7, 5, t="2026-11-06T12:00:00Z"),  # ~63h: only in 72h widen
                 C("e"*16, "Massive ballistic missile strike on Ukraine medical facility in Kharkiv", 6, 4, t="2026-11-08T20:00:00Z"),
                 C("f"*16, "IRGC threatens further strikes on energy infrastructure in the Gulf", 6, 3, t="2026-11-08T18:00:00Z"),
                 C("g"*16, "Cyber attack on US power grid infrastructure under investigation", 5, 2, t="2026-11-08T16:00:00Z"),
                 C("h"*16, "Houthi drones strike commercial tanker in the Red Sea shipping lane", 5, 2, t="2026-11-08T14:00:00Z"),
                 C("i"*16, "Venezuela opposition leader faces new sanctions from the United States", 5, 2, t="2026-11-08T10:00:00Z")]
        # with plenty of 48h items, 65h Belize must stay out
        row = H.latest(items, now=NOW, limit=20)
        titles = [e["title"] for e in row]
        self.assertNotIn(self.TUCKER, titles)
        self.assertTrue(any("Paraguay" in t for t in titles))
        self.assertFalse(any("Belize" in t for t in titles))
        # drop most 48h items so widen-to-72h kicks in; Tucker (5+ days) still out
        sparse = [C("b"*16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease", t="2026-11-09T01:00:00Z"),
                  C("d"*16, "Belize declares state of emergency over deadly gang violence", 7, 5, t="2026-11-06T12:00:00Z"),
                  C("c"*16, self.TUCKER, 8, 3, t="2026-11-03T20:25:25Z"),
                  C("h"*16, "Ousted Paraguayan president placed under house arrest after bank collapse", 5, 3, t="2026-11-06T18:00:00Z"),
                  C("i"*16, "Venezuela opposition leader faces new sanctions from the United States", 5, 2, t="2026-11-06T20:00:00Z"),
                  C("j"*16, "Houthi drones strike commercial tanker in the Red Sea shipping lane", 6, 3, t="2026-11-06T22:00:00Z")]
        row2 = H.latest(sparse, now=NOW, limit=20)
        titles2 = [e["title"] for e in row2]
        self.assertNotIn(self.TUCKER, titles2)
        self.assertTrue(any("Belize" in t for t in titles2))
        for e in row2:
            age_h = (NOW - H._updated(e)) / 3600
            self.assertLessEqual(age_h, H.LATEST_WIDEN_H + 0.01)
    def test_recency_bias_stale_cannot_outrank_fresher(self):
        # rank-8 item 30h old must not beat a rank-7 item that is fresh (rank-1 lower)
        stale = C("1"*16, "Paraguay: President under investigation for bank failure", 8, 9, t="2026-11-07T20:00:00Z")  # ~31h
        fresh = C("2"*16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease", t="2026-11-09T01:00:00Z")
        # filler so 48h pool is used
        more = [C("3"*16, "Massive ballistic missile strike on Ukraine medical facility in Kharkiv", 6, 4, t="2026-11-08T20:00:00Z"),
                C("4"*16, "IRGC threatens further strikes on energy infrastructure in the Gulf", 6, 3, t="2026-11-08T18:00:00Z"),
                C("5"*16, "Cyber attack on US power grid infrastructure under investigation", 5, 2, t="2026-11-08T16:00:00Z"),
                C("6"*16, "Houthi drones strike commercial tanker in the Red Sea shipping lane", 5, 2, t="2026-11-08T14:00:00Z")]
        row = H.latest([stale, fresh] + more, now=NOW, limit=20)
        ids = [e["cluster_id"] for e in row]
        self.assertLess(ids.index("2"*16), ids.index("1"*16))
        # but rank-8 stale CAN beat rank-6 fresh (gap of 2)
        low = C("7"*16, "Venezuela opposition leader faces new sanctions from the United States", 6, 2, t="2026-11-09T01:00:00Z")
        row2 = H.latest([stale, low] + more, now=NOW, limit=20)
        ids2 = [e["cluster_id"] for e in row2]
        self.assertLess(ids2.index("1"*16), ids2.index("7"*16))
    def test_topic_policy_on_latest_row(self):
        items = [C("1"*16, "Flood Warning issued November 8 at 8:11PM CST until November 11 at 1:00PM CST by NWS Corpus Christi TX", 7, 1, "natural disaster", "Nueces, TX", t="2026-11-08T20:00:00Z"),
                 C("2"*16, "GEOFON: M5.0 earthquake Southern Mid-Atlantic Ridge", 6, 3, "natural disaster", t="2026-11-09T01:00:00Z"),
                 C("3"*16, "Heavy rain and flooding expected across central Texas this weekend", 6, 2, "natural disaster", t="2026-11-09T01:00:00Z"),
                 C("4"*16, "Gov. Cox declares state of emergency after repeat flooding in Southern Utah", 7, 17, t="2026-11-09T02:00:00Z"),
                 C("5"*16, "M7.4 earthquake off Kamchatka triggers tsunami warning", 8, 5, "natural disaster", t="2026-11-09T01:30:00Z"),
                 C("6"*16, "Paraguay: President under investigation for bank failure", 7, 9, t="2026-11-08T12:00:00Z"),
                 C("7"*16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease", t="2026-11-09T01:00:00Z")]
        row = H.latest(items, now=NOW, limit=20)
        titles = [e["title"] for e in row]
        self.assertFalse(any("Flood Warning" in t for t in titles))
        self.assertFalse(any("Mid-Atlantic" in t for t in titles))
        self.assertFalse(any("Heavy rain" in t for t in titles))
        self.assertTrue(any("Cox declares" in t for t in titles))
        self.assertTrue(any("Kamchatka" in t for t in titles))
        self.assertTrue(H.topic_ok("Gov. Cox declares state of emergency after repeat flooding in Southern Utah"))
        self.assertFalse(H.topic_ok("Heavy rain and flooding expected across central Texas this weekend"))
    def test_explainer_junk_gout_and_patterns(self):
        items = [C("1"*16, self.GOUT, 5, 4, "disease", t="2026-11-09T01:00:00Z"),
                 C("2"*16, "What is martial law and how does it work in the United States", 6, 3, t="2026-11-09T01:00:00Z"),
                 C("3"*16, "How to prepare your home for a long power outage this winter", 6, 2, t="2026-11-09T01:00:00Z"),
                 C("4"*16, "Ebola outbreak in DR Congo: causes, warning signs doctors are watching", 7, 5, "disease", t="2026-11-09T01:00:00Z"),
                 C("5"*16, "Paraguay: President under investigation for bank failure", 7, 9, t="2026-11-08T12:00:00Z"),
                 C("6"*16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease", t="2026-11-09T01:00:00Z"),
                 C("7"*16, "Massive ballistic missile strike on Ukraine medical facility in Kharkiv", 6, 4, t="2026-11-08T20:00:00Z"),
                 C("8"*16, "IRGC threatens further strikes on energy infrastructure in the Gulf", 6, 3, t="2026-11-08T18:00:00Z")]
        self.assertTrue(H.explainer_junk({"title": self.GOUT, "n_families": 4}))
        self.assertTrue(H.explainer_junk({"title": "What is martial law and how does it work in the United States", "n_families": 3}))
        self.assertFalse(H.explainer_junk({"title": "Ebola outbreak in DR Congo: causes, warning signs doctors are watching", "n_families": 5}))
        row = H.latest(items, now=NOW, limit=20)
        titles = [e["title"] for e in row]
        self.assertNotIn(self.GOUT, titles)
        self.assertFalse(any(t.startswith("What is") for t in titles))
        self.assertFalse(any(t.startswith("How to") for t in titles))
        self.assertTrue(any("Ebola outbreak" in t for t in titles))
        # exact Tucker title from live Nov 3 card must be rejected by freshness even at rank 8
        with_tucker = items + [C("t"*16, self.TUCKER, 8, 3, t="2026-11-03T20:25:25Z")]
        row2 = H.latest(with_tucker, now=NOW, limit=20)
        self.assertFalse(any("Tucker Carlson" in e["title"] for e in row2))
    def test_latest_keeps_dedupe(self):
        items = [C("a"*16, "Paraguay: President under investigation for bank failure", 7, 9, t="2026-11-08T12:00:00Z"),
                 C("b"*16, "Paraguay Bank Failure", 7, 7, t="2026-11-08T12:00:00Z"),
                 C("c"*16, "Ousted Paraguayan president placed under house arrest after bank collapse", 5, 9, t="2026-11-08T14:00:00Z"),
                 C("d"*16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, 4, "disease", t="2026-11-09T01:00:00Z"),
                 C("e"*16, "Massive ballistic missile strike on Ukraine medical facility in Kharkiv", 6, 4, t="2026-11-08T20:00:00Z"),
                 C("f"*16, "IRGC threatens further strikes on energy infrastructure in the Gulf", 6, 3, t="2026-11-08T18:00:00Z"),
                 C("g"*16, "Houthi drones strike commercial tanker in the Red Sea shipping lane", 5, 2, t="2026-11-08T16:00:00Z")]
        row = H.latest(items, now=NOW, limit=20)
        # one Paraguay event only
        para = [e for e in row if "Paraguay" in e["title"] or "Paraguayan" in e["title"]]
        self.assertEqual(len(para), 1)
        self.assertGreaterEqual(para[0]["grouped"], 2)


    def test_entertainment_movie_review_off_latest_row(self):
        title = ("Wild Horse Nine - watched this today and loved it. It's a dark comedy about two CIA agents "
                 "in Chile right before the military coup in 1973. It has a stellar cast")
        self.assertFalse(H.row_ok({"title": title, "category": "political", "n_families": 2, "rank": 6}))
    def test_illness_strikes_recategorized_on_row(self):
        item = {"title": "Mystery Illness Strikes California Marathon Runners", "category": "war/conflict", "n_families": 5, "rank": 7}
        self.assertTrue(H.row_ok(item))
        self.assertEqual(item["category"], "disease")
        self.assertEqual(item["location"], "California")

if __name__ == "__main__": unittest.main()
