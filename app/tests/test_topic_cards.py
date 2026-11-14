"""Topic cards (TOPIC-CARDS-1): UK/region place matching, ET day bucketing (first-seen AND last-updated day),
widened food/outbreak matchers, dated gap backfill, and the empty-day QA check.

Run: cd app && NEWSLETTER_NO_WORKER=1 BN_UNREST_FEEDS=0 python3 -m unittest tests.test_topic_cards -v
Live check (fails on any empty day on any card): BN_QA_DASH_URL=http://127.0.0.1:8861/api/apple/dash python3 -m unittest tests.test_topic_cards -v
"""
import json, os, sqlite3, sys, tempfile, unittest, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
os.environ.setdefault("BN_UNREST_FEEDS", "0")
os.environ.setdefault("NEWSLETTER_NO_WORKER", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import et_days
import topic_cards as TC
import unrest_feeds as U
import apple_v1 as A

ET = ZoneInfo("America/New_York")
def ets(s): return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=ET).timestamp()
def iso(ts): return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
NOW = ets("2026-11-14 12:30")   # Saturday midday ET


class UKPlace(unittest.TestCase):
    FALSE = [
        "The impacts of the drenching on British Columbia's south coast have been increasing as heavy rain triggers evacuation orders and alerts",
        "Flooding shuts highways in British Columbia",
        "Storms sweep New South Wales after record rain in Sydney",
        "New England governors meet on winter fuel prices",
        "Police in London, Ontario investigate downtown stabbing",
        "Birmingham, Alabama police investigate shooting",
        "Manchester, N.H. officers respond to standoff",
        "British Virgin Islands brace for storm",
        "uk-based startup raises funds",            # lower-case 'uk' is not the abbreviation
    ]
    TRUE = [
        "United Kingdom deploys extra police in London ahead of mass protest",
        "Cyber chief: UK facing AI-powered attacks on critical infrastructure within two years",
        "Met Police declare a critical incident after a stabbing",
        "Keir Starmer makes a Downing Street statement on the Westminster security review",
        "Thousands turn out in Edinburgh to protest against AI data centres",
        "Birmingham city centre stabbing: two arrested",
        "Northern Ireland police attacked during Belfast disorder",
    ]
    def test_rejects_homonyms(self):
        for t in self.FALSE:
            self.assertFalse(TC.is_uk_place(t), t)
            self.assertFalse(U.is_uk(t), t)
            self.assertFalse(U.is_uk(t, True), t)   # even from a UK feed, a story about British Columbia is not UK
    def test_accepts_real_uk(self):
        for t in self.TRUE:
            self.assertTrue(TC.is_uk_place(t), t)
    def test_loc_field_masked(self):
        self.assertFalse(TC.is_uk_place("Heavy rain triggers evacuation orders", "65 miles SW of Port Alice, British Columbia"))
        self.assertTrue(TC.is_uk_place("Man arrested after attack", "London"))


class RegionAudit(unittest.TestCase):
    def test_us_homonyms_never_hit_region_cards(self):
        for t in ["Lebanon, Pa. police say two killed in crash", "Lebanon County shooting suspect arrested",
                  "University of Idaho killings: Moscow, Idaho police update", "Odessa, Texas shooting leaves 3 dead",
                  "Jerusalem artichoke harvest", "Russian River flooding forces evacuations in Sonoma County",
                  "St. Petersburg, Florida officers shot"]:
            self.assertFalse(TC.is_il(t) or TC.is_ir(t) or TC.is_ru(t) or TC.is_uk_place(t), t)
    def test_real_regions(self):
        self.assertTrue(TC.is_il("Israeli strikes kill 12 in Gaza"))
        self.assertTrue(TC.is_il("Hezbollah fires rockets from southern Lebanon"))
        self.assertTrue(TC.is_ru("Russian drones hit Odesa port overnight"))
        self.assertTrue(TC.is_ru("Moscow says air defences downed 30 Ukrainian drones"))
        self.assertTrue(TC.is_ir("Iran launches Mid-East drone attack"))
    def test_weather_and_quakes_not_conflict(self):
        for t in ['"For the Beach Hazards Statement, An increased risk for sneaker waves and strong rip currents"',
                  "The impacts of the drenching on British Columbia's south coast have been increasing as heavy rain triggers evacuation orders",
                  "Tsunami Information Statement Number 1: 65 miles SW of Port Alice"]:
            self.assertFalse(TC.conflict_ok(t), t)
        self.assertTrue(TC.conflict_ok("Missile strike kills 5 as storm hampers rescue in Kharkiv"))


class Matchers(unittest.TestCase):
    def test_food_widened(self):
        for t in ["USDA confirms highly pathogenic avian influenza in a commercial poultry flock; 1.2 million birds culled",
                  "FDA announces a nationwide recall of packaged salads over listeria",
                  "FSIS: Class I recall of frozen chicken due to foreign material",
                  "FAO Food Price Index edges down in October",
                  "WFP warns of famine as IPC phase 5 confirmed in parts of Sudan",
                  "Egg prices climb as bird flu hits layer barns",
                  "Port congestion delays grain exports from the Black Sea",
                  "Fertilizer prices jump after Red Sea shipping attacks",
                  "SNAP benefits delayed for millions as funding lapses"]:
            self.assertTrue(TC.is_food(t), t)
        for t in ["British couple in Krakow recall seeing 250 people running after shooting",
                  "Japan PM weighs a snap election", "Hackers hit npm in software supply chain attack",
                  "Prisoners on hunger strike in Belmarsh", "Docker security advisory (AV26-1123)"]:
            self.assertFalse(TC.is_food(t), t)
    def test_outbreaks(self):
        self.assertTrue(TC.is_outbreak("Middle East respiratory syndrome (MERS) - Qatar"))
        self.assertTrue(TC.is_outbreak("Cholera outbreak spreads in Sudan camps"))
        self.assertFalse(TC.is_outbreak("Tornado outbreak hits Oklahoma"))
        self.assertFalse(TC.is_outbreak("Clip of senator goes viral"))
        self.assertFalse(TC.is_outbreak("Ebola cases near 11,000 in DR Congo"))   # Ebola has its own card
    def test_disputes_recount_verb(self):
        self.assertFalse(TC.is_disp('Witnesses recount shooting at Washington, D.C. gym: "Everyone is running"'))
        self.assertTrue(TC.is_disp("Salazar declared winner of Miami congressional race after a two-day recount"))
        self.assertTrue(TC.is_disp("Campaign files a lawsuit over rejected absentee ballots"))
    def test_other_conflict_feed_matcher(self):
        m = U.KIND_MATCH["other"]
        self.assertTrue(m("RSF fighters kill dozens in attack on El Fasher camp, Sudan army says"))
        self.assertFalse(m("Israeli strikes kill 12 in Gaza"))                # has its own card
        self.assertFalse(m("Three killed in Chicago shooting, police say"))   # U.S. crime is not a war zone


class DayBuckets(unittest.TestCase):
    """Root cause of 'today bar empty while the card says 1 story in 24 hours': bars bucketed by first_seen,
    the 24-hour headline by last update. A story now counts on its first-seen AND last-updated ET day."""
    def setUp(self):
        self.days = et_days.et_last_days(7, NOW)
    def test_combine_updated_today_lands_on_today(self):
        w = [{"title": "Iran launches Mid-East drone attack on shipping", "url": "/wire/" + "a" * 16,
              "t": ets("2026-11-13 09:00"), "ut": ets("2026-11-14 12:22"), "rank": 6, "n": 4, "loc": "", "us": False}]
        o = U.combine(w, [], self.days, et_days.et_day, NOW, "Iran")
        by = {r[0]: r[1] + r[2] for r in o["days"]}
        self.assertEqual(o["n24"], 1)
        self.assertEqual(by["2026-11-14"], 1)   # today: last update
        self.assertEqual(by["2026-11-13"], 1)   # first seen
        self.assertEqual(o["n7"], 1)            # one distinct story
        self.assertTrue(o["stories"]["2026-11-14"])
    def test_et_midnight_boundary(self):
        # 11:30 PM ET Friday = 04:30 UTC Saturday: belongs on Friday's bar, not Saturday's.
        late = ets("2026-11-13 23:30")
        w = [{"title": "Russian drones strike Kharkiv overnight, officials say", "url": "/wire/" + "b" * 16, "t": late, "ut": late, "rank": 5, "n": 3, "loc": "", "us": False}]
        by = {r[0]: r[1] + r[2] for r in U.combine(w, [], self.days, et_days.et_day, NOW, "Russia and Ukraine")["days"]}
        self.assertEqual(by["2026-11-13"], 1); self.assertEqual(by["2026-11-14"], 0)
    def test_wire_groups_from_db(self):
        td = tempfile.mkdtemp(); db = os.path.join(td, "blackout.db")
        c = sqlite3.connect(db)
        c.execute("CREATE TABLE clusters (cluster_id TEXT, title TEXT, category TEXT, location TEXT, rank INT, first_seen TEXT, updated TEXT, n_families INT, watchlist INT)")
        rows = [("c" * 16, "Iran launches Mid-East drone attack on Gulf shipping lanes", "war/conflict", "", 6, iso(ets("2026-11-12 10:00")), iso(ets("2026-11-14 11:00")), 4),
                ("d" * 16, "The impacts of the drenching on British Columbia's south coast have been increasing as heavy rain triggers evacuation orders", "war/conflict",
                 "British Columbia", 2, iso(ets("2026-11-12 09:34")), iso(ets("2026-11-12 20:07")), 2),
                ("e" * 16, "For the Beach Hazards Statement, An increased risk for sneaker waves and strong rip currents", "war/conflict", "", 3,
                 iso(ets("2026-11-14 08:00")), iso(ets("2026-11-14 09:00")), 2)]
        for r in rows: c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,0)", r)
        c.commit(); c.close()
        base = A.BASE; A.BASE = td
        try: g = A.wire_groups(NOW)
        finally: A.BASE = base
        ir = {r[0]: r[1] + r[2] for r in g["conf"]["ir"]["days"]}
        self.assertEqual(ir["2026-11-14"], 1); self.assertEqual(ir["2026-11-12"], 1); self.assertEqual(g["conf"]["ir"]["n24"], 1)
        uk_titles = [s["title"] for d in g["conf"]["uk"]["stories"].values() for s in d]
        self.assertFalse(any("British Columbia" in t for t in uk_titles), uk_titles)
        other = [s["title"] for d in g["conf"]["other"]["stories"].values() for s in d]
        self.assertFalse(any("Beach Hazards" in t or "British Columbia" in t for t in other), other)


class Coverage(unittest.TestCase):
    def test_sources_per_card(self):
        urls = " ".join(u for u, *_ in U.RSS)
        for needle in ("fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/food-safety-recalls", "cidrap.umn.edu/rss.xml", "woah.org/en/feed",
                       "who.int/rss-feeds/news-english.xml", "reliefweb.int/updates/rss.xml", "iaea.org/feeds/topnews", "ecdc.europa.eu"):
            self.assertIn(needle, urls)
        food = " ".join(U.FOOD_Q)
        for needle in ("site:aphis.usda.gov", "site:fsis.usda.gov", "site:fao.org", "site:wfp.org", "HPAI", "food price index", "IPC", "egg prices", "fertilizer", "port"):
            self.assertIn(needle, food)
        for kind in ("il", "ir", "ru", "other", "ebola", "measles", "outbreak", "uk", "nuke", "disp"):
            self.assertTrue(any(q.endswith("when:1d") for q in U.TOPIC_Q[kind]) or kind == "uk", kind)   # today's bar
        self.assertEqual(set(U.BACKFILL_Q), {"il", "ir", "ru", "uk", "other", "ebola", "measles", "outbreak", "u", "food", "nuke", "disp"})
        self.assertEqual(U.outlet("www.aphis.usda.gov")[1], "USDA APHIS"); self.assertEqual(U.outlet("www.cidrap.umn.edu")[1], "CIDRAP")
        self.assertIsNone(U.outlet("randomblog.example")[0])
    def test_dated_backfill_fills_empty_day(self):
        U._BF["want"].clear(); U._BF["done"] = {}
        U.want_backfill("food", ["2026-11-10"])
        seen = []
        def fake(q):
            seen.append(q)
            return [{"title": "USDA confirms avian influenza in commercial poultry flock, birds culled", "url": "https://www.aphis.usda.gov/news/x",
                     "domain": "www.aphis.usda.gov", "t": ets("2026-11-10 14:00"), "direct": True}]
        import time as _t
        sl = _t.sleep; _t.sleep = lambda s: None
        try: got = U.backfill([], NOW, [], fetch=fake)
        finally: _t.sleep = sl
        self.assertEqual(len(seen), 1); self.assertIn("after:2026-11-09", seen[0]); self.assertIn("before:2026-11-12", seen[0])
        ev = U.build_events(got, "food", NOW)
        self.assertTrue(any(TC.active_days(e["t"], e["t1"], {"2026-11-10"}) for e in ev))
        self.assertEqual(U.backfill([], NOW, [], fetch=fake), [])   # same pair not searched again within 6 hours
    def test_merge_feed_into_special_card(self):
        days = et_days.et_last_days(7, NOW)
        card = {"days": [[d, 0, 0] for d in days], "stories": {d: [] for d in days}, "n24": 0, "n7": 0, "max24": 0}
        ev = [{"title": "IAEA says Zaporizhzhia nuclear plant lost off-site power again", "url": "https://www.iaea.org/x", "t": ets("2026-11-11 10:00"),
               "t1": ets("2026-11-14 10:00"), "rank": 3, "n_outlets": 2, "outlets": ["IAEA", "Reuters"]}]
        U.merge_feed(card, ev, days, et_days.et_day, NOW)
        by = {r[0]: r[1] + r[2] for r in card["days"]}
        self.assertEqual(by["2026-11-11"], 1); self.assertEqual(by["2026-11-14"], 1); self.assertEqual(card["n24"], 1); self.assertEqual(card["max24"], 0)
        self.assertEqual(card["latest"][0]["url"], "https://www.iaea.org/x")   # the card's subline is never "No reports in 7 days" over full bars


class EmptyDayQA(unittest.TestCase):
    def test_check_flags_any_empty_day_and_missing_card(self):
        days = et_days.et_last_days(7, NOW)
        full = {"days": [[d, 1, 0] for d in days]}
        dash = {g: {} for g in ("conf", "health", "hard", "spec")}
        for g, k in TC.TOPIC_CARDS: dash[g][k] = full
        self.assertEqual(TC.check_dash(dash), {})
        dash["hard"]["food"] = {"days": [[d, 0 if d == days[-1] else 1, 0] for d in days]}
        del dash["spec"]["disp"]
        bad = TC.check_dash(dash)
        self.assertEqual(bad["hard/food"], [days[-1]]); self.assertEqual(bad["spec/disp"], ["missing"])
    @unittest.skipUnless(os.environ.get("BN_QA_DASH_URL"), "set BN_QA_DASH_URL to check a running server")
    def test_live_dash_has_no_empty_day(self):
        dash = json.load(urllib.request.urlopen(os.environ["BN_QA_DASH_URL"], timeout=60))
        self.assertEqual(TC.check_dash(dash), {}, "empty bars (card: days)")


if __name__ == "__main__":
    unittest.main()
