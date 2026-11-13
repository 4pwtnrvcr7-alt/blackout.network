"""Matt, Nov 13 4:39 PM ET: "Need this featured tonight in the email and on the website, need a full write-up." The FAA nationwide
ground stop desk story leads the homepage top row (card 1), the Hamas pin moves to card 2, the green EAS card follows; it also
leads the 7 PM ET newsletter and names its subject line.
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_faa_feature -v"""
import os, sys, re, types, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import home_feed as H
import desk_stories as DS

FAA = "59bef563ad245e29"
PIN = "c6abb98df0496535"
EAS = "ed747e9064795131"
EVE = DS._ts("2026-11-13T23:30:00Z")   # 6:30 PM ET, before the 7 PM issue
BEFORE = DS._ts("2026-11-13T21:00:00Z")

class Data(unittest.TestCase):
    def test_story_complete_and_sourced(self):
        s = DS.get(FAA); self.assertTrue(s)
        n = DS.note(FAA)
        for k in ("headline", "what_happened", "why_it_matters", "analysis", "rank_why", "risk", "if_true", "if_false", "what_to_do", "confidence"):
            self.assertTrue(n.get(k), k)
        self.assertGreaterEqual(len({x["domain"] for x in n["sources"]}), 5)
        self.assertIn("3:54 p.m. ET", n["what_happened"])
        r, rows = DS.cluster(FAA); self.assertEqual(len(rows), 7); self.assertEqual(r["rank"], 8)
        sec = DS.sections_html(FAA)
        for h in ("What happened", "Timeline", "How big is it", "What caused it", "What it means", "What to do if you are flying", "Sources"):
            self.assertIn(h, sec)
        self.assertIn("Our analysis", sec); self.assertIn("nasstatus.faa.gov", sec)
        self.assertIn("Timeline", DS.lead_html(FAA))
        self.assertNotRegex(sec, re.compile(r"\bverified\b|\bbreaking\b", re.I))

class Home(unittest.TestCase):
    def test_pin_order(self):
        ps = DS.pin_cards(EVE)
        self.assertEqual([p["cluster_id"] for p in ps], [FAA, PIN])
        self.assertEqual(DS.pin_card(EVE)["cluster_id"], FAA)
        self.assertEqual(DS.pin_card(BEFORE)["cluster_id"], PIN)   # before the FAA window, Hamas is still card 1
        self.assertEqual(DS.feature_card(EVE)["cluster_id"], EAS)
        os.environ["BN_HOME_PIN"] = "0"
        try: self.assertEqual(DS.pin_cards(EVE), []); self.assertIsNone(DS.pin_card(EVE))
        finally: os.environ.pop("BN_HOME_PIN", None)

    def test_payload(self):
        import apple_v1 as A
        srv = types.SimpleNamespace(api_state=lambda: {"generated": "2026-11-13T23:00:00Z", "main": [
            {"cluster_id": "3" * 16, "title": "FAA halts departing flights at all U.S. airports after an air traffic control communications failure", "rank": 8, "n_families": 3,
             "category": "infrastructure", "location": "", "lat": None, "lon": None, "updated": "2026-11-13T22:00:00Z", "first_seen": "2026-11-13T22:00:00Z", "event_time": None},
            {"cluster_id": "4" * 16, "title": "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", "rank": 7, "n_families": 3,
             "category": "disease", "location": "", "lat": None, "lon": None, "updated": "2026-11-13T22:00:00Z", "first_seen": "2026-11-13T22:00:00Z", "event_time": None}]},
            _addon_mod=lambda n: types.SimpleNamespace(handle_get=lambda p, q: (404, {})))
        real, rps, rp, rf, rev = sys.modules.get("server"), DS.pin_cards, DS.pin_card, DS.feature_card, A._events
        sys.modules["server"] = srv
        DS.pin_cards = lambda now=None, limit=3: rps(EVE, limit); DS.pin_card = lambda now=None: rp(EVE); DS.feature_card = lambda now=None: rf(EVE)
        A._events = lambda main: main
        try: out = A._home_build()
        finally:
            DS.pin_cards, DS.pin_card, DS.feature_card, A._events = rps, rp, rf, rev
            if real is None: sys.modules.pop("server", None)
            else: sys.modules["server"] = real
        self.assertEqual([p["cluster_id"] for p in out["pins"]], [FAA, PIN]); self.assertEqual(out["pin"]["cluster_id"], FAA)
        self.assertEqual(out["feature"]["cluster_id"], EAS)
        self.assertEqual([x["cluster_id"] for x in out["main"]], ["4" * 16])   # scanner copy of the FAA story dropped

    def test_js_order(self):
        js = open(os.path.join(APP, "static", "bn-apple-home.js"), encoding="utf-8").read()
        i, j, k = js.find("if(P)cards.unshift(pcard(P));"), js.find("cards.splice(Math.min(pi,cards.length),0,pcard(PS[pi]))"), js.find("cards.splice(Math.min(PS.length||1,cards.length),0,fcard(F))")
        self.assertTrue(0 < i < j < k, (i, j, k))

class Newsletter(unittest.TestCase):
    def test_lead_and_subject(self):
        import tests.test_newsletter_featured_desk as T
        N, QA = T.N, T.QA
        from datetime import datetime, timezone
        T._src()
        at = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)   # the 7 PM ET issue
        f = N.featured_desk(at)
        self.assertEqual([x["cluster_id"] for x in f], [FAA, PIN, EAS])
        self.assertTrue(f[0]["lead"]); self.assertFalse(f[1]["lead"])
        self.assertEqual([x["cluster_id"] for x in N.featured_desk(datetime(2026, 11, 14, 5, 0, tzinfo=timezone.utc))], [PIN, EAS])
        issue = N.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=at, slot="evening")
        subj, html, text = N.render(issue, T.LINKS)
        self.assertIn("FAA halts departing flights at all U.S. airports", subj)
        i, j, k = html.find(f"/wire/{FAA}"), html.find(f"/wire/{PIN}"), html.find(f"/wire/{EAS}")
        self.assertTrue(0 < i < j < k, (i, j, k))
        qa = QA.check(subj, html, text, QA.sources_from_issue(issue), QA.titles_from_issue(issue))
        self.assertTrue(qa["ok"], qa["blockers"])

if __name__ == "__main__":
    unittest.main()
