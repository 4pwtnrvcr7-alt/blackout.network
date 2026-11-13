"""Matt, Nov 13 (t1349u): the Hamas bodyguard story is pinned as card 1 of the homepage top row (green EAS card stays card 2),
featured in the newsletter next to the EAS card, and its headline is shown verbatim everywhere.
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_home_pin -v"""
import os, sys, re, types, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import home_feed as H
import desk_stories as DS

PIN = "c6abb98df0496535"
EAS = "ed747e9064795131"
HEADLINE = "Hamas leader's former bodyguard granted British citizenship - 'then plotted terror attack in Europe'"
NOW = DS._ts("2026-11-13T15:05:00Z")   # 10:05 AM ET, when the patch goes live and the catch-up issue is sent
END = DS._ts("2026-11-15T05:00:00Z")   # end of Nov 14 ET

class Pin(unittest.TestCase):
    def test_exact_headline_in_data(self):
        s = DS.get(PIN)
        self.assertEqual(s["title"], HEADLINE)
        self.assertEqual(s["pin"]["title"], HEADLINE)
        self.assertEqual(s["newsletter"]["title"], HEADLINE)
        self.assertEqual(s["brief"]["headline"], HEADLINE)
        self.assertEqual(DS.note(PIN)["headline"], HEADLINE)   # word filter leaves it untouched

    def test_pin_window_and_kill_switch(self):
        p = DS.pin_card(NOW)
        self.assertEqual(p["cluster_id"], PIN); self.assertEqual(p["href"], f"/wire/{PIN}"); self.assertEqual(p["title"], HEADLINE)
        self.assertEqual(p["rank"], 7)
        self.assertIsNotNone(DS.pin_card(END - 60)); self.assertIsNone(DS.pin_card(END))
        os.environ["BN_HOME_PIN"] = "0"
        try: self.assertIsNone(DS.pin_card(NOW))
        finally: os.environ.pop("BN_HOME_PIN", None)
        self.assertEqual(DS.feature_card(NOW)["cluster_id"], EAS)   # the green card is still the EAS story

    def test_brief_complete_and_sourced(self):
        n = DS.note(PIN)
        for k in ("what_happened", "why_it_matters", "analysis", "rank_why", "risk", "if_true", "if_false", "what_to_do"):
            self.assertTrue(n.get(k), k)
        self.assertGreaterEqual(len({x["domain"] for x in n["sources"]}), 2)
        self.assertIn("Timeline", DS.lead_html(PIN)); self.assertIn("Granted British citizenship", DS.lead_html(PIN))
        self.assertIn("ds-chain", DS.lead_html(EAS))   # EAS keeps its alert-path diagram
        r, rows = DS.cluster(PIN)
        self.assertEqual(r["title"], HEADLINE); self.assertEqual(len(rows), 4)

    def test_row_dedupe_drops_scanner_copies_of_the_pinned_story(self):
        pin = DS.pin_card(NOW); feat = DS.feature_card(NOW)
        ev = [{"cluster_id": "1" * 16, "title": HEADLINE, "rank": 7, "n_families": 3, "category": "terrorism"},
              {"cluster_id": PIN, "title": "x", "rank": 7, "n_families": 3, "category": "terrorism"},
              {"cluster_id": "2" * 16, "title": "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", "rank": 7, "n_families": 3, "category": "disease"}]
        out = H.dedupe_row(ev, skip_ids=[PIN, EAS], skip_items=[pin, feat])
        self.assertEqual([e["cluster_id"] for e in out], ["2" * 16])

    def test_home_payload_has_pin_and_feature(self):
        import apple_v1 as A
        srv = types.SimpleNamespace(api_state=lambda: {"generated": "2026-11-13T15:00:00Z", "main": [
            {"cluster_id": "3" * 16, "title": "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", "rank": 7, "n_families": 3,
             "category": "disease", "location": "", "lat": None, "lon": None, "updated": "2026-11-13T14:00:00Z", "first_seen": "2026-11-13T14:00:00Z", "event_time": None}]},
            _addon_mod=lambda n: types.SimpleNamespace(handle_get=lambda p, q: (404, {})))
        real_mod, rp, rf, rev, rps = sys.modules.get("server"), DS.pin_card, DS.feature_card, A._events, DS.pin_cards
        sys.modules["server"] = srv
        DS.pin_cards = lambda now=None, limit=3: rps(NOW, limit); DS.pin_card = lambda now=None: rp(NOW); DS.feature_card = lambda now=None: rf(NOW); A._events = lambda main: main
        try: out = A._home_build()
        finally:
            DS.pin_card, DS.feature_card, A._events, DS.pin_cards = rp, rf, rev, rps
            if real_mod is None: sys.modules.pop("server", None)
            else: sys.modules["server"] = real_mod
        self.assertEqual(out["pin"]["title"], HEADLINE); self.assertEqual(out["feature"]["cluster_id"], EAS)
        self.assertNotIn(PIN, [x["cluster_id"] for x in out["main"]])

class Static(unittest.TestCase):
    def test_js_pin_first_feature_second(self):
        js = open(os.path.join(APP, "static", "bn-apple-home.js"), encoding="utf-8").read()
        self.assertIn("if(P)cards.unshift(pcard(P));", js)
        i, j = js.find("if(P)cards.unshift(pcard(P));"), js.find("cards.splice(Math.min(PS.length||1,cards.length),0,fcard(F))")
        self.assertTrue(0 < i < j)   # pin goes in first, then the green card at index 1
        self.assertIn("'<h3>'+esc(f.title)+'</h3>", js)   # verbatim, not title()
        self.assertNotRegex(js, re.compile(r"meshtastic|\blora\b", re.I))

class Newsletter(unittest.TestCase):
    def test_featured_order_and_exact_headline(self):
        import tests.test_newsletter_featured_desk as T   # same offline env (temp DBs, preview sender, no worker)
        N, QA = T.N, T.QA
        from datetime import datetime, timezone
        T._src()
        at = datetime(2026, 11, 13, 15, 5, tzinfo=timezone.utc)
        f = N.featured_desk(at)
        self.assertEqual([x["cluster_id"] for x in f], [PIN, EAS])
        self.assertEqual(f[0]["title"], HEADLINE); self.assertTrue(f[0]["url"].endswith(f"/wire/{PIN}"))
        self.assertEqual([x["cluster_id"] for x in N.featured_desk(datetime(2026, 11, 15, 5, 0, tzinfo=timezone.utc))], [EAS])
        issue = N.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=at, slot="morning")
        subj, html, text = N.render(issue, T.LINKS)
        import html as h
        self.assertIn(h.escape(HEADLINE, quote=True), html); self.assertIn(HEADLINE, text)
        i, j = html.find(f"/wire/{PIN}"), html.find(f"/wire/{EAS}")
        self.assertTrue(0 < i < j, (i, j))
        for later in ("Top threats", "Patterns we", "Where these stories"):
            k = html.find(later)
            if k > 0: self.assertLess(j, k, later)
        qa = QA.check(subj, html, text, QA.sources_from_issue(issue), QA.titles_from_issue(issue))
        self.assertTrue(qa["ok"], qa["blockers"])

if __name__ == "__main__":
    unittest.main()
