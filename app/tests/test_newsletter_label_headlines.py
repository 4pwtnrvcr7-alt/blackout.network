"""Nov 21 2026 fix: the 7 AM brief went to 3 of 5 subscribers. Two personalised variants were blocked by the QA gate (blocked_qa)
because their story cards printed the alert-card LABEL as the headline ("Ballistic Missile Attack", "Missile Strike"): the card
headline kept only the text before the first " | " of titles like
"Ballistic Missile Attack | 9/10 <flag> Ballistic Missile Strike on Zatoka, Odesa Region - 2 OTRK-5\\nTwo Russian ...",
a cut-short prefix of the story title. The fix is in the build (newsletter.headline_text / _fit_headline); the gate is unchanged.
Offline: no network, no email sent (live sending is not approved in this config). Run: cd app && python3 -m unittest tests.test_newsletter_label_headlines -v
"""
import json, os, socket, sqlite3, sys, tempfile, unittest
from datetime import datetime, timezone, timedelta
TMP = tempfile.mkdtemp(prefix="nllabel_")
for k, v in {"NEWSLETTER_DB": "nl.db", "NEWSLETTER_SRC_DB": "src.db", "NEWSLETTER_CONFIG": "nl_config.json",
             "NEWSLETTER_OUTBOX": "outbox", "NEWSLETTER_ENV": "creds/newsletter.env", "NEWSLETTER_PASSFILE": "PASS.txt",
             "NEWSLETTER_LOG": "nl.log", "NEWSLETTER_BO_CONFIG": "bo.json"}.items():
    os.environ[k] = os.path.join(TMP, v)
os.environ["NEWSLETTER_NO_WORKER"] = "1"
os.makedirs(os.path.join(TMP, "creds"), exist_ok=True)
open(os.path.join(TMP, "PASS.txt"), "w").write("x\n")
open(os.path.join(TMP, "bo.json"), "w").write("{}")
open(os.path.join(TMP, "nl_config.json"), "w").write(json.dumps({"live_sending_approved": False, "base_url": "https://blackout.network"}))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _blocked(*a, **k): raise RuntimeError("network access attempted during tests")
socket.socket.connect = _blocked
socket.create_connection = _blocked
import newsletter as NL
import newsletter_qa as QA
import story_report as SR

# The two raw cluster titles behind the Nov 21 7 AM blocked_qa variants (shape as stored by the scanner, flag emoji included).
ODESA = ("Ballistic Missile Attack | 9/10 \U0001F1FA\U0001F1E6 Ballistic Missile Strike on Zatoka, Odesa Region - 2 OTRK-5\n"
         "Two Russian ballistic missiles (OTRK-5 class) struck Zatoka in Odesa Region overnight; damage to port infrastructure is reported.")
KYIV = ("Missile Strike | 10/10 Ballistic Missiles Strike Bridges in Kyiv\n"
        "Ballistic missile strikes confirmed on Northern Bridge and Darnytskyi Bridge in Kyiv; traffic across the Dnipro is stopped.")

class HeadlineText(unittest.TestCase):
    def test_alert_card_gives_the_real_headline(self):
        self.assertEqual(NL.card_headline({"title": NL.tighten_title(ODESA)}), "Ballistic Missile Strike on Zatoka, Odesa Region - 2 OTRK-5")
        self.assertEqual(NL.card_headline({"title": NL.tighten_title(KYIV)}), "Ballistic Missiles Strike Bridges in Kyiv")

    def test_never_the_bare_label(self):
        for raw in (ODESA, KYIV, "Naval/Missile Anomaly | 7/10 Explosion Reported from Sea off Sirik, Iran's Hormozgan Province\nResidents heard it."):
            h = NL.card_headline({"title": NL.tighten_title(raw)})
            self.assertNotIn("|", h)
            self.assertGreaterEqual(len(h.split()), 4, h)

    def test_gate_prefix_rule_passes_against_raw_and_tightened_title(self):
        for raw in (ODESA, KYIV):
            h = NL.card_headline({"title": NL.tighten_title(raw)})
            self.assertIsNone(QA._prefix_of(h, [raw, NL.clean_title(raw), NL.tighten_title(raw)]), h)
            self.assertIsNone(QA._dangling(h))

    def test_old_behaviour_was_the_cut(self):
        # what the gate saw on Nov 21: the label is a cut-short prefix of the title
        self.assertIsNotNone(QA._prefix_of("Ballistic Missile Attack", [NL.clean_title(ODESA)]))
        self.assertIsNotNone(QA._prefix_of("Missile Strike", [NL.clean_title(KYIV)]))

    def test_outlet_and_aggregator_tails(self):
        self.assertEqual(NL.tighten_title("Russia strikes Zelenskyy's hometown as airstrike burns cargo ship | Daily Sabah"),
                         "Russia strikes Zelenskyy's hometown as airstrike burns cargo ship")
        self.assertEqual(NL.tighten_title('Two new Ebola vaccines to join DR Congo clinical trial\n->UN News | More on "Ebola vaccines clinical trial"'),
                         "Two new Ebola vaccines to join DR Congo clinical trial")

    def test_other_bar_titles_kept_whole_not_cut(self):
        t = "Dr. Mustafa Başkara | International Maritime Law Expert | Ankara University: Greece must respect the Aegean status quo"
        h = NL.card_headline({"title": NL.tighten_title(t)})
        self.assertEqual(h, NL.clean_title(t))
        self.assertIsNone(QA._prefix_of(h, [NL.tighten_title(t)]))
        self.assertEqual(NL.tighten_title("Nov. 19, 2026 | News 19 at 6 p.m."), "Nov. 19, 2026 | News 19 at 6 p.m.")   # short head: not an outlet tail

    def test_plain_titles_unchanged(self):
        for t in ("A magnitude 4.4 earthquake struck the Los Angeles area early Friday morning",
                  "Overnight storms cause extensive flooding in Broward, Miami-Dade"):
            self.assertEqual(NL.headline_text(t), t)
            self.assertEqual(NL.card_headline({"title": NL.tighten_title(t)}), t)

    def test_idempotent(self):
        for raw in (ODESA, KYIV):
            once = NL.headline_text(raw); self.assertEqual(NL.headline_text(once), once)

# ------------------------------------------------------------------ full offline build: build_issue -> render -> qa_gate (no send)
AT = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)   # 7:00 AM ET slot
STORIES = [("aa11" * 4, ODESA, "war/conflict", "Zatoka, Odesa Oblast, Ukraine", 46.07, 30.46, 6),
           ("bb22" * 4, KYIV, "war/conflict", "Kyiv, Ukraine", 50.45, 30.52, 6),
           ("cc33" * 4, "Overnight storms cause extensive flooding in Broward, Miami-Dade", "weather", "Broward County, Florida", 26.19, -80.36, 6),
           ("dd44" * 4, "A magnitude 4.4 earthquake struck the Los Angeles area early Friday morning", "earthquake", "Commerce, California", 34.0, -118.15, 6)]

def seed():
    p = os.path.join(TMP, "src.db")
    if os.path.exists(p): os.remove(p)
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT,
                 first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT,
                 watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER, eff_families INTEGER, rank INTEGER, pushed_at TEXT)""")
    c.execute("CREATE TABLE alerts(id TEXT, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT)")
    t = (AT - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for cid, title, cat, loc, lat, lon, rank in STORIES:
        c.execute("INSERT INTO clusters VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, title, cat, loc, lat, lon, t, t, t, 70, "High", 4, 3, json.dumps(["AP", "BBC", "Reuters"]), "[]", 0, "", t, 0, 0, 3, rank, None))
        c.execute("INSERT INTO alerts(id,source,family,title,category,source_url,event_time,base,official,extra,first_seen,last_seen,cluster_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid + "x", "AP", "AP", title, cat, "https://example.org/" + cid, t, 60, 1, "{}", t, t, cid))
    c.commit(); c.close()

NOTES = {s[0]: {"what_happened": f"Officials confirmed the event in {s[3]} and gave details on Saturday.", "analysis": "Authorities are still assessing the damage.",
                "outlook": "More reports are expected through the day.", "confidence": "Medium", "sources": ["https://example.org/" + s[0]]} for s in STORIES}

class FullBuild(unittest.TestCase):
    def setUp(self):
        self._P = dict(NL.P); NL.P.update({"src": os.path.join(TMP, "src.db"), "db": os.path.join(TMP, "nl.db"), "cfg": os.path.join(TMP, "nl_config.json"),
                                           "outbox": os.path.join(TMP, "outbox"), "log": os.path.join(TMP, "nl.log")})
        seed()
        if os.path.exists(NL.P["db"]): os.remove(NL.P["db"])
        NL._INIT.clear(); NL.db().close()
        self.rep = os.path.join(TMP, "story_reports.json"); self._old = SR.REPORTS; SR.REPORTS = self.rep
        with open(self.rep, "w") as f: json.dump({"notes": NOTES}, f)   # notes without a headline: the card falls back to the title (Nov 21 case)
        SR._RC.update(mt=None, v={})
    def tearDown(self):
        NL.P.clear(); NL.P.update(self._P); NL._INIT.clear(); SR.REPORTS = self._old; SR._RC.update(mt=None, v={})

    def test_morning_issue_with_alert_card_titles_passes_the_gate(self):
        c = NL.cfg()
        sub = {"id": None, "frequency": "both", "interests": '["all"]', "follows": [], "last_sent_at": None}
        issue = NL.build_issue(sub, at=AT, slot="morning", c=c)
        self.assertFalse(issue["empty"])
        L = NL.links_for({"id": 0, "token": "t", "email": "x@example.org"}, c) if hasattr(NL, "links_for") else {}
        subj, hb, tx = NL.render(issue, L, c)
        heads = QA.extract(hb)["headlines"]
        self.assertNotIn("Ballistic Missile Attack", heads); self.assertNotIn("Missile Strike", heads)
        r = NL.qa_gate(issue, subj, hb, tx, c)
        self.assertTrue(r["ok"], r["blockers"])

if __name__ == "__main__":
    unittest.main()
