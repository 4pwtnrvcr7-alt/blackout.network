"""One event = one card (Matt, Nov 13 2026; NL-DEDUPE-1/2, SITE-DEDUPE-1). event_dedupe matching, the newsletter merge before layout,
and the QA gate's hard duplicate check. Offline: temp databases, no network, no send, no worker. Nothing is set at import time
beyond NEWSLETTER_NO_WORKER, so `unittest discover` cannot leak state into other modules."""
import os, sys, json, sqlite3, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
os.environ["NEWSLETTER_NO_WORKER"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import event_dedupe as ED

TMP = tempfile.mkdtemp(prefix="nldedupe_")
UTC = timezone.utc
AT = datetime(2026, 11, 14, 0, 0, tzinfo=UTC)   # Nov 13, 7 PM ET
ATTACK = ("dddddddddddddd01", "A car bomb in southern Moscow badly wounds a former aide to Ukraine's pro-Russian ex-prime minister", "war/conflict", "Moscow, Russia", 7)
ANGLE = ("dddddddddddddd02", "The Moscow bombing victim is a longtime Kremlin propagandist named in a US Senate report on election meddling", "war/conflict", "Not specified", 6)
OTHER = ("dddddddddddddd03", "A Russian air defense colonel is killed by a car bomb in St. Petersburg, the second such blast there since August", "war/conflict", "St. Petersburg, Russia", 5)
QUAKE = ("dddddddddddddd04", "Magnitude 6.8 earthquake strikes off Hokkaido, Japan, with a tsunami advisory", "natural disaster", "Hokkaido, Japan", 6)
WATCH = ("dddddddddddddd05", "Moscow car bomb suspect detained, Russian investigators say", "war/conflict", "Moscow, Russia", 3)
STORIES = [ATTACK, ANGLE, OTHER, QUAKE]
REPORTS = {"notes": {s[0]: {"what_happened": "Sourced brief text for the test story."} for s in STORIES + [WATCH]},
           "people": {"profiles": {"mykola-azarov": {"slug": "mykola-azarov", "name": "Mykola Azarov", "rx": r"\bAzarov\b"}},
                      "story_people": {}, "lead": {}, "places": {}, "country_alias": {}}, "images": {}, "shares": {}}


class Matching(unittest.TestCase):
    def test_moscow_two_angles_are_one_event(self):
        a, b = {"title": ATTACK[1], "where": "Moscow, Russia"}, {"title": ANGLE[1]}
        self.assertIn("moscow", ED.same_event(a, b) or "")
        self.assertIsNone(ED.same_event(a, {"title": OTHER[1], "where": "St. Petersburg, Russia"}))   # different city, different event

    def test_ids_window_hazard_people_and_politics(self):
        self.assertEqual(ED.same_event({"cluster_id": "x1", "title": "A"}, {"cluster_id": "x1", "title": "B"}), "same cluster id")
        self.assertEqual(ED.same_event({"cluster_id": "x1", "story_id": "s", "title": "A"}, {"cluster_id": "x2", "story_id": "s", "title": "B"}), "same story id")
        e1 = {"title": "Ebola outbreak in Congo's Equateur province kills 12", "when": AT}
        e2 = {"title": "Congo starts an Ebola vaccination campaign for health workers", "when": AT - timedelta(hours=20)}
        self.assertIn("ebola", ED.same_event(e1, e2) or "")
        self.assertIsNone(ED.same_event(e1, dict(e2, when=AT - timedelta(hours=72))))            # outside 48 h
        self.assertIsNone(ED.same_event({"title": "Bird flu found on a dairy farm", "where": "Yakima, Washington"},
                                        {"title": "Bird flu kills a child", "where": "Phnom Penh, Cambodia"}))   # same disease, different places
        t1 = {"title": "Trump orders new sanctions on Iran's oil exports", "where": "Washington", "people": ["donald-trump"]}
        t2 = {"title": "Trump pardons a former campaign aide", "where": "Washington", "people": ["donald-trump"]}
        self.assertIsNone(ED.same_event(t1, t2))   # same person + capital is not one event
        self.assertEqual(ED.same_event({"title": "Wildfire forces evacuations near Ventura"},
                                       {"title": "Wildfire forces evacuations near Ventura, officials say"}), "near-identical headlines")

    def test_merge_keeps_highest_rank_and_order(self):
        a = {"title": ANGLE[1], "rank": 6}; b = {"title": ATTACK[1], "where": "Moscow", "rank": 7}; c = {"title": QUAKE[1], "rank": 6}
        kept, folded = ED.merge([a, b, c])
        self.assertEqual(kept, [b, c]); self.assertEqual([(k is b, d is a) for k, d, _ in folded], [(True, True)])
        self.assertEqual(len(ED.duplicates([a, b, c])), 1)


def _src(path, rows):
    k = sqlite3.connect(path)
    k.executescript("""CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE TABLE IF NOT EXISTS clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER, eff_families INTEGER, rank INTEGER, pushed_at TEXT);
    CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, started TEXT, finished TEXT, trigger TEXT, fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);
    DELETE FROM clusters; DELETE FROM alerts;""")
    t = (AT - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for (cid, title, cat, loc, rk), wl in rows:
        fams = ["Reuters", "AP", "BBC"]
        k.execute("INSERT INTO clusters(cluster_id,title,category,location,event_time,first_seen,updated,score,confidence,n_items,n_families,families,links,watchlist,brief,eff_families,rank,high_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, title, cat, loc, t, t, t, rk * 10, "high", 6, 3, json.dumps(fams), "[]", wl, title + ".", 3, rk, t))
        for i, f in enumerate(fams):
            k.execute("INSERT INTO alerts(id,source,family,title,category,source_url,event_time,location,base,official,first_seen,last_seen,cluster_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (f"{cid}-{i}", f, f, title, cat, f"https://example.org/{cid}/{i}", t, loc, 5, 1 if i == 0 else 0, t, t, cid))
    k.commit(); k.close()


class Newsletter(unittest.TestCase):
    OWN_P = {"db": "nl.db", "src": "src.db", "outbox": "outbox", "cfg": "newsletter_config.json", "env": "nl.env", "pass": "pass.txt"}

    @classmethod
    def setUpClass(cls):
        import newsletter as N, story_report as SR
        cls.N, cls.SR = N, SR
        open(os.path.join(TMP, "nl.env"), "w").write("NEWSLETTER_SENDER=preview\n")
        json.dump(REPORTS, open(os.path.join(TMP, "reports.json"), "w"))
        json.dump({"base_url": "https://blackout.network", "max_watchlist": 3, "watchlist_enabled": True}, open(os.path.join(TMP, "newsletter_config.json"), "w"))
        cls._env = {k: os.environ.get(k) for k in ("NEWSLETTER_ANALYSIS_JSON", "BN_NL_V2")}
        os.environ["NEWSLETTER_ANALYSIS_JSON"] = os.path.join(TMP, "none.json"); os.environ.pop("BN_NL_V2", None)
        cls._P = dict(N.P); cls._sr = SR.REPORTS
        N.P.update({k: os.path.join(TMP, v) for k, v in cls.OWN_P.items()})
        SR.REPORTS = os.path.join(TMP, "reports.json"); SR._RC.update(mt=None, v={}); N._INIT.clear()

    @classmethod
    def tearDownClass(cls):
        N, SR = cls.N, cls.SR
        for k, v in cls._env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        N.P.clear(); N.P.update(cls._P); N._INIT.clear(); SR.REPORTS = cls._sr; SR._RC.update(mt=None, v={})

    def _issue(self, rows):
        _src(self.N.P["src"], rows)
        return self.N.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=AT, since=AT - timedelta(hours=12), slot="evening")

    def _all(self, issue):
        return [it for sec in ("near", "main", "politics", "follow", "updates", "notable", "developing", "watchlist") for it in issue.get(sec) or []]

    def test_two_angles_merge_into_the_ranked_story(self):
        N = self.N
        issue = self._issue([(s, 0) for s in STORIES])
        ids = [it["cluster_id"] for it in self._all(issue)]
        self.assertIn(ATTACK[0], ids); self.assertNotIn(ANGLE[0], ids)
        self.assertIn(OTHER[0], ids); self.assertIn(QUAKE[0], ids)          # St. Petersburg bomb and the quake are other events
        self.assertEqual([(k, d) for k, d, _ in issue["merged"]], [(ATTACK[0], ANGLE[0])])
        kept = next(it for it in self._all(issue) if it["cluster_id"] == ATTACK[0])
        self.assertTrue(N.also_line(kept).startswith("Also: The Moscow bombing victim is a longtime Kremlin propagandist"))
        import newsletter_qa as QA
        self.assertEqual(QA.duplicate_events(issue), [])
        subj, html, text = N.render(issue, {"unsubscribe": "https://blackout.network/newsletter/unsubscribe?token=x", "manage": "https://blackout.network/newsletter",
                                            "categories": "https://blackout.network/newsletter", "sources": "https://blackout.network/sources",
                                            "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/", "_row": None})
        self.assertIn("Also: The Moscow bombing victim", html); self.assertIn("Also: The Moscow bombing victim", text)
        self.assertNotIn(f"/wire/{ANGLE[0]}", html)                              # the angle points to the kept story page only
        self.assertIsNotNone(N.qa_gate(issue, subj, html, text, {"qa_gate": "block"}))

    def test_watchlist_line_about_the_same_event_is_folded(self):
        issue = self._issue([(s, 0) for s in STORIES] + [(WATCH, 1)])
        ids = [it["cluster_id"] for it in self._all(issue)]
        self.assertNotIn(WATCH[0], ids)
        self.assertIn(WATCH[0], [d for _, d, _ in issue["merged"]])

    def test_qa_gate_hard_fails_a_duplicate(self):
        N = self.N
        import newsletter_qa as QA
        issue = self._issue([(s, 0) for s in STORIES])
        angle = N.item_of(dict(zip(("cluster_id", "title", "category", "location", "rank"), ANGLE)) | {
            "event_time": None, "first_seen": "2026-11-13T21:00:00Z", "lat": None, "lon": None, "brief": ANGLE[1], "eff_families": 3,
            "families": "[]", "links": "[]", "score": 60}, "main")
        issue["main"].append(angle)                                   # what a missed merge would look like
        dup = QA.duplicate_events(issue)
        self.assertEqual(len(dup), 1); self.assertIn("duplicate event", dup[0]); self.assertIn(ANGLE[0], dup[0])
        same = dict(angle, title="Totally different headline about markets", display_title=None, cluster_id=ATTACK[0])
        issue["main"][-1] = same
        self.assertTrue(any("same cluster id" in d for d in QA.duplicate_events(issue)))
        r = N.qa_gate(issue, "Evening Brief, Nov 13: test", "<html></html>", "", {"qa_gate": "block"})
        self.assertFalse(r["ok"]); self.assertTrue(any("duplicate event" in b for b in r["blockers"]))


if __name__ == "__main__":
    unittest.main()
