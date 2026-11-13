"""Matt, Nov 13: the EAS nationwide-test desk story (ed747e9064795131) must be featured near the top of the next brief, linking to its
/wire story page. Offline: temp databases, no network, no send."""
import os, sys, json, sqlite3, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
TMP = tempfile.mkdtemp(prefix="nlfeat_")
open(os.path.join(TMP, "nl.env"), "w").write("NEWSLETTER_SENDER=preview\n")
os.environ.update({"NEWSLETTER_NO_WORKER": "1", "NEWSLETTER_ENV": os.path.join(TMP, "nl.env"), "NEWSLETTER_DB": os.path.join(TMP, "nl.db"),
                   "NEWSLETTER_SRC_DB": os.path.join(TMP, "src.db"), "NEWSLETTER_OUTBOX": os.path.join(TMP, "outbox"),
                   "NEWSLETTER_CONFIG": os.path.join(TMP, "newsletter_config.json"), "NEWSLETTER_ANALYSIS_JSON": os.path.join(TMP, "none.json"),
                   "NEWSLETTER_PASSFILE": os.path.join(TMP, "pass.txt"), "BN_STORY_REPORTS": os.path.join(TMP, "none_reports.json")})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import newsletter as N
import newsletter_qa as QA
EAS = "ed747e9064795131"
UTC = timezone.utc
AT = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)          # the Nov 13 morning slot (and any resend of it)
EVE = datetime(2026, 11, 14, 0, 0, tzinfo=UTC)          # Nov 13, 7 PM ET

def _src():
    k = sqlite3.connect(N.P["src"])
    k.executescript("""CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE TABLE IF NOT EXISTS clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER, eff_families INTEGER, rank INTEGER, pushed_at TEXT);
    CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, started TEXT, finished TEXT, trigger TEXT, fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);""")
    k.commit(); k.close()

LINKS = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter", "categories": "https://blackout.network/newsletter",
         "sources": "https://blackout.network/sources", "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}

class FeaturedDeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): _src()

    def test_eas_desk_story_is_eligible_now_and_tonight(self):
        for at in (AT, EVE):
            f = N.featured_desk(at)
            self.assertIn(EAS, [x["cluster_id"] for x in f], at)
            x = [x for x in f if x["cluster_id"] == EAS][0]
            self.assertTrue(x["url"].endswith(f"/wire/{EAS}"))

    def test_not_featured_after_the_window(self):
        self.assertNotIn(EAS, [x["cluster_id"] for x in N.featured_desk(datetime(2026, 11, 18, 6, 0, tzinfo=UTC))])

    def test_config_off_switch(self):
        self.assertEqual(N.featured_desk(AT, dict(N.cfg(), feature_desk_stories=False)), [])

    def test_issue_features_eas_near_top_with_story_link_and_passes_gate(self):
        for slot, at in (("morning", AT), ("evening", EVE)):
            issue = N.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=at, slot=slot)
            self.assertIn(EAS, [x["cluster_id"] for x in issue.get("featured") or []])
            subj, html, text = N.render(issue, LINKS)
            i = html.find(f"/wire/{EAS}")
            self.assertGreater(i, 0, "EAS story link missing from the HTML")
            self.assertIn("Nationwide alert test", html)
            # near the top: before the map, every story section and the analysis patterns
            for later in ("Top threats", "Patterns we", "Where these stories"):
                j = html.find(later)
                if j > 0: self.assertLess(i, j, later)
            self.assertIn(f"/wire/{EAS}", text)
            self.assertLess(text.find(f"/wire/{EAS}"), max(text.find("TOP THREATS"), text.find("Forward to a friend")))
            qa = QA.check(subj, html, text, QA.sources_from_issue(issue), QA.titles_from_issue(issue))
            self.assertTrue(qa["ok"], qa["blockers"])

if __name__ == "__main__":
    unittest.main()
