"""Key Figures related-alert matcher: per-figure aliases, word boundaries,
headline+summary+entities, event-time window, and false-positive guards.
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_figures_related_alerts -v
"""
import os, sys, sqlite3, tempfile, shutil, unittest
from datetime import datetime, timezone, timedelta
from unittest import mock

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

import figures


def days_ago(n, hour="12:00:00"):
    t = datetime.now(timezone.utc) - timedelta(days=n)
    return t.strftime("%Y-%m-%dT") + hour + "Z"


SCHEMA = """
CREATE TABLE clusters (
  cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT,
  event_time TEXT, first_seen TEXT, updated TEXT, links TEXT, watchlist INTEGER,
  brief TEXT, rank INTEGER
);
"""


class AliasMatching(unittest.TestCase):
    def test_putin_matches_name_aliases_and_russia_war_context(self):
        m = figures.matches
        self.assertTrue(m("putin", "Putin rejects a ceasefire in Ukraine"))
        self.assertTrue(m("putin", "Vladimir Putin spoke in Moscow"))
        self.assertTrue(m("putin", "The Kremlin said talks had collapsed"))
        self.assertTrue(m("putin", "The Russian president arrived in Abu Dhabi"))
        self.assertTrue(m("putin", "President of Russia met envoys"))
        self.assertTrue(m("putin", "Russia's president declined the proposal"))
        self.assertTrue(m("putin", "A Moscow-ordered strike hit energy sites"))
        self.assertTrue(m("putin", "Russian forces struck a city in the Donbas"))
        self.assertTrue(m("putin", "Russian government actions after the summit"))
        self.assertTrue(m("putin", "Russia launched missiles at Kyiv overnight"))
        self.assertTrue(m("putin", "Russians strike Odesa with jet-powered drones"))
        self.assertTrue(m("putin", "Explosion aboard Russian warship in the Gulf of Finland"))

    def test_zelensky_netanyahu_xi_trump_aliases(self):
        m = figures.matches
        self.assertTrue(m("zelensky", "President Zelenskyy addressed the nation"))
        self.assertTrue(m("zelensky", "Volodymyr Zelenskiy says Russian forces are planning new strikes"))
        self.assertTrue(m("zelensky", "The Ukrainian president visited the front"))
        self.assertTrue(m("zelensky", "Ukraine's president called for air defenses"))
        self.assertTrue(m("netanyahu", "Netanyahu met US officials"))
        self.assertTrue(m("netanyahu", "The Israeli prime minister spoke to the cabinet"))
        self.assertTrue(m("netanyahu", "Israeli PM visited the north"))
        self.assertTrue(m("netanyahu", "Israel's government and Hamas agreed a Gaza ceasefire framework"))
        self.assertTrue(m("xi", "Xi Jinping hosted a state visit"))
        self.assertTrue(m("xi", "President Xi arrived in Beijing"))
        self.assertTrue(m("xi", "The Chinese president met European leaders"))
        self.assertTrue(m("xi", "Beijing and the Chinese government, Xi told state media"))
        self.assertTrue(m("trump", "Donald J. Trump commented on the talks"))
        self.assertTrue(m("trump", "POTUS arrived in Miami for the G20"))
        self.assertTrue(m("trump", "Trump said he would invite allies"))

    def test_other_role_aliases(self):
        m = figures.matches
        self.assertTrue(m("mkhamenei", "Iran's supreme leader ordered a response"))
        self.assertTrue(m("araghchi", "Iranian foreign minister held talks in Doha"))
        self.assertTrue(m("carney", "Canada's prime minister said Ottawa can wait"))
        self.assertTrue(m("tedros", "The WHO director-general briefed on Ebola"))
        self.assertTrue(m("lavrov", "The Russian foreign minister arrived in Doha"))
        self.assertTrue(m("pezeshkian", "Iran's president spoke on state TV"))
        self.assertTrue(m("macron", "The French president called for talks"))


class FalsePositiveGuard(unittest.TestCase):
    def test_bare_country_or_city_is_not_enough(self):
        m = figures.matches
        self.assertFalse(m("putin", "Drought is on going in China, Kazakhstan, Mongolia, Russia"))
        self.assertFalse(m("putin", "GEOFON: M4.7 earthquake Kamchatka Peninsula, Russia"))
        self.assertFalse(m("putin", "A winter storm warning was issued for Moscow, Idaho"))
        self.assertFalse(m("putin", "Tourism in Moscow recovered this summer"))
        self.assertFalse(m("zelensky", "A cultural festival opened in Kyiv"))
        self.assertFalse(m("zelensky", "Drought is on going in Ukraine and Moldova"))
        self.assertFalse(m("xi", "China reported stronger factory output"))
        self.assertFalse(m("xi", "A trade fair opened in Beijing"))
        self.assertFalse(m("netanyahu", "A restaurant in Tel Aviv won an award"))
        self.assertFalse(m("netanyahu", "Travel guide to Israel and Jordan"))
        self.assertFalse(m("mkhamenei", "An earthquake was reported in southern Iran"))
        self.assertFalse(m("mkhamenei", "North Korea's supreme leader inspected a factory"))

    def test_word_boundary_and_other_russian_figures(self):
        m = figures.matches
        self.assertFalse(m("putin", "The input in this report is incomplete"))
        self.assertFalse(m("putin", "Rasputin is the subject of a new documentary"))
        # Russian strikes are Putin-level government/military actions, not every Russian official
        war = "Russian forces struck drone production sites in the Rostov region"
        self.assertTrue(m("putin", war))
        self.assertFalse(m("lavrov", war))
        self.assertFalse(m("nikitin", war))
        self.assertTrue(m("lavrov", "Lavrov met his counterpart in Doha"))
        self.assertTrue(m("nikitin", "Governor Nikitin reported damage in Kstovo"))

    def test_cluster_text_includes_brief_and_entities_not_location(self):
        # name only in summary, not the headline
        text = figures.cluster_text("Overnight strikes", "Putin declined a ceasefire offer.")
        self.assertTrue(figures.matches("putin", text))
        # entities field (not a clusters column today, but matcher must consult it if present)
        text = figures.cluster_text("Overnight talks", "Envoys met in Doha.", "", "Vladimir Putin")
        self.assertTrue(figures.matches("putin", text))
        text = figures.cluster_text("Massive barrage", "Missiles and drones overnight.", "Kyiv, Ukraine")
        self.assertFalse(figures.matches("putin", text))  # Ukraine/Kyiv without Russia/Russian/Moscow/Kremlin
        text = figures.cluster_text("Massive barrage", "Russian missiles and drones overnight.", "Kyiv, Ukraine")
        self.assertTrue(figures.matches("putin", text))
        # place names in the location field must not count as a person (Vance County, NC)
        text = figures.cluster_text(
            "Freeze Warning issued November 13 at 11:41AM EST by NWS Raleigh NC",
            "",
            "Person; Granville; Vance; Warren; Halifax",
        )
        self.assertFalse(figures.matches("vance", text))
        self.assertTrue(figures.matches("vance", "Trump and Vance are trying to stop the war"))


class AlertsQuery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "blackout.db")
        self.prev = figures.BDB
        c = sqlite3.connect(self.db)
        c.executescript(SCHEMA)
        ev_new, ev_old = days_ago(1), days_ago(20)
        upd_new = days_ago(0, "18:00:00")
        rows = [
            # should match Putin via alias + context (The Wire, rank 3)
            ("w1", "Russians strike Odesa with jet-powered drones, killing two",
             "war/conflict", "Odesa, Ukraine", ev_new, ev_new, upd_new, "", 0, "Russian drones hit the port.", 3),
            # Watchlist, literal name, rank 4
            ("w2", "Putin is preparing for talks in Abu Dhabi",
             "war/conflict", "", ev_new, ev_new, upd_new, "", 1, "Russia has fired ballistic missiles at Kyiv.", 4),
            # suppressed low-signal: must not count
            ("w3", "Putin Plays Trump For The Fool He Is",
             "war/conflict", "", ev_new, ev_new, upd_new, "", 2, "Kremlin comments on talks.", 1),
            # stale event, freshly updated: outside 7-day event window
            ("w4", "Putin announced a new mobilization",
             "war/conflict", "Moscow", ev_old, ev_old, upd_new, "", 0, "Russian president spoke on TV.", 5),
            # false positive drought, even if updated today and rank 5
            ("w5", "Drought is on going in China, Kazakhstan, Mongolia, Russia",
             "natural disaster", "", ev_old, ev_old, upd_new, "", 0, "A drought is on going in Russia.", 5),
            # Zelensky alias on Watchlist
            ("w6", "The Ukrainian president called for more air defenses",
             "war/conflict", "Kyiv", ev_new, ev_new, upd_new, "", 1, "", 3),
            # rank 1 on The Wire: below MIN_RANK, ignore even with Putin
            ("w7", "Putin comments on grain exports",
             "political", "", ev_new, ev_new, upd_new, "", 0, "", 1),
        ]
        c.executemany("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        c.commit(); c.close()
        figures.BDB = "file:" + self.db + "?mode=ro"
        figures._C["t"] = 0
        figures._C["v"] = None

    def tearDown(self):
        figures.BDB = self.prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_window_rank_watchlist_and_counts(self):
        hits, counts, cats, err = figures._alerts()
        self.assertIsNone(err)
        self.assertEqual(counts["putin"], 2, counts)
        titles = [h["title"] for h in hits["putin"]]
        self.assertTrue(any("Odesa" in t for t in titles))
        self.assertTrue(any("Abu Dhabi" in t for t in titles))
        self.assertFalse(any("Fool" in t for t in titles))
        self.assertFalse(any("mobilization" in t for t in titles))
        self.assertFalse(any("Drought" in t for t in titles))
        self.assertFalse(any("grain" in t for t in titles))
        lists = {h["title"]: h["list"] for h in hits["putin"]}
        self.assertEqual(next(v for k, v in lists.items() if "Odesa" in k), "The Wire")
        self.assertEqual(next(v for k, v in lists.items() if "Abu Dhabi" in k), "Watchlist")
        self.assertEqual(counts["zelensky"], 1)
        self.assertGreaterEqual(counts["lavrov"], 0)
        self.assertEqual(counts["nikitin"], 0)


if __name__ == "__main__":
    unittest.main()
