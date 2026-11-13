"""Homepage top row (Matt, Nov 13): green EAS desk card in position 2, no repeats, no junk titles.
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_home_carousel -v"""
import os, sys, re, time, types, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import home_feed as H
import desk_stories as DS

NOW = DS._ts("2026-11-13T13:00:00Z")
def C(cid, title, rank=7, fam=3, cat="war/conflict", t="2026-11-13T10:00:00Z", families=None):
    d = {"cluster_id": cid, "title": title, "rank": rank, "n_families": fam, "category": cat, "location": "", "lat": None, "lon": None,
            "updated": t, "first_seen": t, "event_time": t}
    if families is not None: d["families"] = families
    return d
# The row Matt saw on Nov 13 (titles from /api/apple/home at 8:56 AM ET)
LIVE_ROW = [
    C("ed62f62c7c6492a2", "LIVE] Times Now: Trump Announcement Live | Nuclear Attack on Iran? Trump Speech LIVE", 6),
    C("f7dd6f7a45562e44", "Wider use of Ervebo vaccine urged as DR Congo Ebola outbreak nears 11,000 cases", 7, cat="disease"),
    C("4c1b364af6b12691", "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", 7, cat="disease"),
    C("eb9828967e1bc90c", "An assassination attempt on the commander of the Airborne Brigade was foiled in Mykolaiv", 7),
    C("ff9e5add02c443c4", "Trump\u2019s Next Coup Attempt by Timothy Snyder - Project Syndicate rcooley123.wordpress.com/2026/04/13/t...", 7, cat="political"),
    C("9e63d729bb63212d", "Garry Kasparov canceled his trip to Berlin due to a threat of an assassination attempt", 7),
    C("38dad02c3cdcc6bf", "Israeli occupation forces carried out a new massacre at dawn today, bombing the intensive care unit at Nasser hospital", 5),
    C("b088fc62318af3d0", "This morning in St. Petersburg, a Russian colonel was killed in a car explosion; he is believed to have been Deputy Commander", 5),
    C("e3036d760fe60d4a", "A car exploded on Kirovogradskaya Street in Moscow, according to Russian media. The driver was injured", 5),
    C("a26c8e86db5ab3f1", "Ripple-linked Uphold faces withdrawal delays amid \u2018bank run\u2019 claims", 6, cat="financial"),
    C("7490c9cb3b99065a", "Today in History: November 10, white supremacists stage coup in Wilmington, North Carolina", 5, cat="political"),
    C("f014ce9ad2ebed3d", "2026-020: Critical Vulnerabilities in Citrix NetScaler ADC and NetScaler Gateway", 3, cat="cyber"),
]

class Junk(unittest.TestCase):
    def j(self, t, cid="0" * 16): return H.row_junk({"cluster_id": cid, "title": t})
    def test_url_and_domain_paths(self):
        self.assertTrue(self.j("Something happened rcooley123.wordpress.com/2026/04/13/t..."))
        self.assertTrue(self.j("See https" + "://example.org/a for more"))
        self.assertTrue(self.j("Read www.example.com today"))
    def test_livestreams(self):
        for t in ("LIVE] Times Now: Trump Announcement Live", "[LIVE] Senate hearing", "LIVE: Rally in Ohio", "Trump Speech LIVE",
                  "Watch live: launch from Florida", "Ukraine war live updates: strikes on Kyiv", "Gaza livestream from the border"):
            self.assertTrue(self.j(t), t)
    def test_opinion_and_history(self):
        for t in ("Trump's Next Coup Attempt by Timothy Snyder - Project Syndicate", "Opinion: The grid is not ready", "Why NATO must act | Opinion",
                  "Op-ed: our hospitals", "Today in History: November 10, coup in Wilmington", "On this day in 1989 the wall fell"):
            self.assertTrue(self.j(t), t)
    def test_block_list(self):
        self.assertTrue(self.j("A normal looking headline about a coup attempt", "ff9e5add02c443c4"))
    def test_real_headlines_pass(self):
        for t in ("Troops conduct live-fire drills near the border after missile launch", "Russia strikes Kyiv power plants overnight",
                  "Ripple-linked Uphold faces withdrawal delays amid 'bank run' claims", "U.S. Navy deploys carrier to the Red Sea",
                  "Wider use of Ervebo vaccine urged as DR Congo Ebola outbreak nears 11,000 cases", "Strike killed by Israeli forces - Al Jazeera reports"):
            self.assertFalse(self.j(t), t)
    def test_kill_switch(self):
        os.environ["BN_HOME_ROW_FILTER"] = "0"
        try:
            self.assertFalse(self.j("LIVE] Times Now")); self.assertEqual(len(H.dedupe_row(LIVE_ROW)), len(LIVE_ROW))
        finally: os.environ.pop("BN_HOME_ROW_FILTER", None)

class Repeats(unittest.TestCase):
    def test_themes(self):
        self.assertEqual(H.themes("Kenya begins Ebola-free countdown"), {"outbreak:ebola"})
        self.assertIn("attack:assassination", H.themes("Kasparov cancels trip over assassination threat"))
        self.assertIn("attack:car-bomb", H.themes("A car exploded on Kirovogradskaya Street in Moscow"))
        self.assertEqual(H.themes("Russia strikes Kyiv power plants"), set())
    def test_live_row_from_nov13(self):
        out = H.dedupe_row(LIVE_ROW)
        ids = [e["cluster_id"] for e in out]
        self.assertEqual(ids, ["f7dd6f7a45562e44", "eb9828967e1bc90c", "38dad02c3cdcc6bf", "b088fc62318af3d0", "a26c8e86db5ab3f1", "f014ce9ad2ebed3d"])
        th = [t for e in out for t in H.themes(e["title"])]
        self.assertEqual(len(th), len(set(th)))
    def test_same_cluster_and_near_identical_titles(self):
        a = C("1" * 16, "Ukraine says it foiled a Russian plot against a brigade commander in Mykolaiv")
        b = dict(a, cluster_ids=["2" * 16, "1" * 16], cluster_id="2" * 16, title="Different words entirely here please now")
        c = C("3" * 16, "Ukraine says it foiled Russian plot against brigade commander in Mykolaiv - Kyiv Independent")
        d = C("4" * 16, "Ukraine says it foiled a Russian plot against a brigade commander in Mykolaiv")
        self.assertEqual([e["cluster_id"] for e in H.dedupe_row([a, b, c, d])], ["1" * 16])
    def test_skip_ids_keeps_featured_story_out(self):
        x = C("ed747e9064795131", "FEMA and FCC nationwide Emergency Alert System test on Nov. 17", 2, cat="other")
        self.assertEqual(H.dedupe_row([x, LIVE_ROW[1]], skip_ids=["ed747e9064795131"]), [LIVE_ROW[1]])
    def test_different_events_stay(self):
        evs = [C("1" * 16, "Russia strikes Kyiv power plants overnight"), C("2" * 16, "China holds drills around Taiwan"),
               C("3" * 16, "Citrix NetScaler flaw exploited in the wild", cat="cyber")]
        self.assertEqual(len(H.dedupe_row(evs)), 3)
    def test_latest_applies_filter_and_keeps_strongest(self):
        out = H.latest(LIVE_ROW, now=NOW, limit=40)
        titles = [e["title"] for e in out]
        self.assertFalse(any(H.row_junk(e) for e in out))
        self.assertEqual(sum("Ebola" in t for t in titles), 1)
        self.assertEqual(sum(bool(re.search("assassinat", t, re.I)) for t in titles), 1)
        self.assertEqual(len({e["cluster_id"] for e in out}), len(out))
        ebola = [e for e in out if "Ebola" in e["title"]][0]
        self.assertIn("4c1b364af6b12691", ebola.get("cluster_ids") or [])
        self.assertEqual(H.also_line(ebola), "Also: Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases.")

class HomeBuild(unittest.TestCase):
    def test_feature_in_payload_and_not_repeated_in_main(self):
        import apple_v1 as A
        eas = C("ed747e9064795131", "FEMA and FCC nationwide Emergency Alert System test on Nov. 17, 2026, at 2:20 PM ET", 2, cat="other")
        srv = types.SimpleNamespace(api_state=lambda: {"generated": "2026-11-13T13:00:00Z", "main": LIVE_ROW + [eas]},
                                    _addon_mod=lambda n: types.SimpleNamespace(handle_get=lambda p, q: (404, {})))
        real_mod, real_fc, real_ev = sys.modules.get("server"), DS.feature_card, A._events
        sys.modules["server"] = srv
        DS.feature_card = lambda now=None: real_fc(NOW)
        A._events = lambda main: H.latest(main, now=NOW, limit=40)
        try:
            out = A._home_build()
        finally:
            DS.feature_card = real_fc; A._events = real_ev
            if real_mod is None: sys.modules.pop("server", None)
            else: sys.modules["server"] = real_mod
        self.assertEqual(out["feature"]["cluster_id"], "ed747e9064795131"); self.assertEqual(out["feature"]["href"], "/wire/ed747e9064795131")
        ids = [x["cluster_id"] for x in out["main"]]
        self.assertNotIn("ed747e9064795131", ids); self.assertNotIn("ff9e5add02c443c4", ids); self.assertNotIn("ed62f62c7c6492a2", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_feature_none_after_window(self):
        self.assertIsNone(DS.feature_card(DS._ts("2026-11-18T05:00:00Z")))
        self.assertIsNotNone(DS.feature_card(DS._ts("2026-11-18T04:59:00Z")))


class SiteDedupe(unittest.TestCase):
    """SITE-DEDUPE-1: same-event angles fold into one card with an Also: line (display only)."""
    def test_ebola_outbreak_and_vaccine_fold(self):
        outbreak = C("f7dd6f7a45562e44", "Wider use of Ervebo vaccine urged as DR Congo Ebola outbreak nears 11,000 cases", 7, cat="disease")
        vaccine = C("4c1b364af6b12691", "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", 7, cat="disease")
        ev = H.events([outbreak, vaccine], now=NOW, limit=10)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["cluster_id"], outbreak["cluster_id"])
        self.assertEqual(sorted(ev[0]["cluster_ids"]), sorted([outbreak["cluster_id"], vaccine["cluster_id"]]))
        self.assertEqual(H.also_line(ev[0]), "Also: Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases.")
    def test_merged_card_uses_combined_distinct_sources(self):
        outbreak = C("f7dd6f7a45562e44", "Wider use of Ervebo vaccine urged as DR Congo Ebola outbreak nears 11,000 cases", 7, fam=1, cat="disease", families=["CIDRAP"])
        kenya = C("4c1b364af6b12691", "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", 7, fam=1, cat="disease", families=["CIDRAP"])
        kids = C("b1bba3904c6dd786", "DR Congo: Fast facts: Ebola's toll on children six months into the outbreak and response", 6, fam=3, cat="disease",
                 families=["ReliefWeb", "rescue.org", "unicef.org"])
        ev = H.events([outbreak, kenya, kids], now=NOW, limit=10)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["n_families"], 4)   # CIDRAP counted once, plus ReliefWeb, rescue.org, unicef.org
        self.assertEqual(ev[0]["grouped"], 3)
        self.assertEqual(H.source_meta(ev[0]), ("4 sources", "3 stories merged"))
        # no family lists: counts are added
        a = C("1" * 16, "Overnight explosion levels Warren home, hurling debris in all directions", 5, fam=2, cat="natural disaster")
        b = C("2" * 16, "Warren house explosion", 4, fam=1, cat="natural disaster")
        ev2 = H.events([a, b], now=NOW, limit=10)
        self.assertEqual(len(ev2), 1)
        self.assertEqual(ev2[0]["n_families"], 3)
        self.assertEqual(H.source_meta(ev2[0])[1], "2 stories merged")
    def test_unrelated_outbreaks_do_not_fold(self):
        a = C("1" * 16, "Yakima County, Washington, reports 2 more avian flu cases, 1 death", 7, fam=4, cat="disease")
        b = C("2" * 16, "Quick takes: Clade 1 mpox in California, H9N2 avian flu cases in China, more Ebola deaths", 5, fam=1, cat="disease")
        ev = H.events([a, b], now=NOW, limit=10)
        self.assertEqual(len(ev), 2)
        self.assertFalse(any(H.also_line(e) for e in ev))
    def test_fold_story_list_for_feed_cards(self):
        stories = [
            {"title": "Wider use of Ervebo vaccine urged as DR Congo Ebola outbreak nears 11,000 cases",
             "url": "/wire/f7dd6f7a45562e44", "rank": 7, "src": "The Wire"},
            {"title": "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases",
             "url": "/wire/4c1b364af6b12691", "rank": 7, "src": "The Wire"},
        ]
        out = H.fold_story_list(stories)
        self.assertEqual(len(out), 1)
        self.assertIn("Also: Kenya begins Ebola-free countdown", H.also_line(out[0]))
    def test_slim_passes_also_and_keeps_pin_feature_keys(self):
        import apple_v1 as A
        outbreak = C("f7dd6f7a45562e44", "Wider use of Ervebo vaccine urged as DR Congo Ebola outbreak nears 11,000 cases", 7, cat="disease")
        vaccine = C("4c1b364af6b12691", "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", 7, cat="disease")
        ev = H.events([outbreak, vaccine], now=NOW, limit=10)[0]
        d = A._slim(ev)
        self.assertTrue(d.get("also"))
        self.assertEqual(d["also"][0]["text"], "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases")
    def test_js_and_css_draw_also_line(self):
        js = open(os.path.join(APP, "static", "bn-apple-home.js"), encoding="utf-8").read()
        css = open(os.path.join(APP, "static", "bn-apple.css"), encoding="utf-8").read()
        self.assertIn("function also(", js)
        self.assertIn("bna-also", js)
        self.assertIn("Also:", js)
        self.assertIn("stories merged", js)
        self.assertIn("function srcLine(", js)
        self.assertIn(".bna-also{", css)
        # Hamas pin and EAS featured cards stay in their slots; Also: is only on regular cards
        self.assertIn("cards.unshift(pcard(P))", js)
        self.assertIn("cards.splice(Math.min(1,cards.length),0,fcard(F))", js)
        self.assertNotIn("also(P)", js)
        self.assertNotIn("also(F)", js)

class Static(unittest.TestCase):
    def setUp(self):
        self.js = open(os.path.join(APP, "static", "bn-apple-home.js"), encoding="utf-8").read()
        self.css = open(os.path.join(APP, "static", "bn-apple.css"), encoding="utf-8").read()
    def test_js_puts_feature_second_and_green(self):
        self.assertIn("cards.splice(Math.min(1,cards.length),0,fcard(F))", self.js)
        self.assertIn("bna-rk grn", self.js); self.assertIn('href="/wire/\'+f.cluster_id+\'"', self.js)
        self.assertIn("Date.now()>=u", self.js)                    # hides itself at show_until even from a stale snapshot
    def test_css_green(self):
        self.assertIn(".bna-it.bna-feat{", self.css); self.assertIn("#3fa66a", self.css); self.assertIn(".bna-rk.grn{", self.css)
    def test_no_banned_words(self):
        for src in (self.js, self.css, open(os.path.join(APP, "home_feed.py"), encoding="utf-8").read()):
            self.assertNotRegex(src, re.compile(r"meshtastic|\blora\b", re.I))

if __name__ == "__main__":
    unittest.main()
