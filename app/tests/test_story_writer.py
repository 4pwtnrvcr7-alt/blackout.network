"""Instant API story writer (story_writer.py, Nov 21 2026). Mocked API and sources; no network.
Run: cd app && python3 -m unittest tests.test_story_writer -v
"""
import json, os, sqlite3, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

TMP = tempfile.mkdtemp()
_ORIG_ENV = {k: os.environ.get(k) for k in ("BN_WRITER_DB", "BN_WRITER_SOURCE_DB", "BN_STORY_REPORTS", "BN_STORY_V3_BRIEFS", "XAI_API_KEY")}
os.environ["BN_WRITER_DB"] = os.path.join(TMP, "sw.db")
os.environ["BN_WRITER_SOURCE_DB"] = os.path.join(TMP, "blackout.db")
os.environ["BN_STORY_REPORTS"] = os.path.join(TMP, "story_reports.json")
os.environ["BN_STORY_V3_BRIEFS"] = os.path.join(TMP, "nov3.json")
os.environ["XAI_API_KEY"] = "test-not-a-key"
import story_writer as SW
PATHS = {k: os.environ[k] for k in ("BN_WRITER_DB", "BN_WRITER_SOURCE_DB", "BN_STORY_REPORTS", "BN_STORY_V3_BRIEFS")}

def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
NOW = datetime.now(timezone.utc)
U1 = "https://earthquake.usgs.gov/earthquakes/eventpage/us6000test"; U2 = "https://www.example-news.com/quake"
TEXT1 = "M 6.8 earthquake in the Banda Sea, Indonesia, at a depth of 143 km on 2026-11-21. USGS issued a green PAGER alert."
TEXT2 = "Indonesia's BMKG said there was no tsunami threat after the magnitude 6.8 quake. About 70 thousand people felt moderate shaking."

def mkdb(rows):
    p = os.environ["BN_WRITER_SOURCE_DB"]
    if os.path.exists(p): os.unlink(p)
    k = sqlite3.connect(p)
    k.executescript("""CREATE TABLE alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL,
      location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT);
      CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT,
      score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT,
      rising INTEGER DEFAULT 0, mentions_3h INTEGER DEFAULT 0, eff_families INTEGER DEFAULT 0, rank INTEGER DEFAULT 0, pushed_at TEXT);""")
    for i, (cid, title, rank) in enumerate(rows):
        t = iso(NOW - timedelta(minutes=30 + i))
        k.execute("INSERT INTO clusters(cluster_id,title,category,location,first_seen,updated,score,n_items,n_families,families,links,watchlist,brief,rank,eff_families) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,2)", (cid, title, "natural disaster", "Indonesia", t, t, 80, 2, 2, "[]", "[]", "WHAT: " + title, rank))
        k.execute("INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid + "a", "USGS", "USGS", title, "natural disaster", U1, t, 0, 0, "Indonesia", 0, 1, "", t, t, cid))
        k.execute("INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid + "b", "News", "News", title, "natural disaster", U2, t, 0, 0, "Indonesia", 0, 0, "", t, t, cid))
    k.commit(); k.close()

def good(urls=(U1, U2), extra=""):
    para = ("USGS said the magnitude 6.8 earthquake struck the Banda Sea off Indonesia at a depth of 143 km on Nov. 21, 2026. "
            "Indonesia's BMKG said there was no tsunami threat. USGS issued a green alert, which points to a low chance of damage. ") * 2
    return json.dumps({"headline": "A magnitude 6.8 earthquake struck deep under the Banda Sea off Indonesia", "why_it_matters": "Deep quakes rarely do much damage.",
        "what_happened": "USGS said a magnitude 6.8 quake struck at 143 km depth." + extra, "analysis": "The depth limited shaking.", "rank_why": "Ranked high for size; we think that over-ranks it.",
        "risk": "High", "risk_why": "Green alert.", "if_true": "Aftershocks taper.", "if_false": "USGS revises the alert.", "what_to_do": "No action is needed.",
        "confidence": "High", "confidence_why": "USGS and BMKG agree.", "sources": list(urls),
        "story": {"headline": "A deep magnitude 6.8 earthquake shook eastern Indonesia", "dek": "Officials said there was no tsunami threat.",
                  "sections": {"happened": para, "background": "", "analysis": para, "watch": para},
                  "sources": [{"url": u, "label": "USGS"} for u in urls]}})

class Base(unittest.TestCase):
    def setUp(self):
        os.environ.update(PATHS); os.environ["XAI_API_KEY"] = "test-not-a-key"
        for p in (PATHS["BN_WRITER_DB"], PATHS["BN_STORY_REPORTS"], PATHS["BN_STORY_V3_BRIEFS"]):
            assert p.startswith(TMP)
            if os.path.exists(p): os.unlink(p)
        import story_report as SR; self._sr_reports = SR.REPORTS; SR.REPORTS = PATHS["BN_STORY_REPORTS"]; SR._RC.update(mt=None, v={})
        import story_v3 as V3; V3._BR.update(mt=None, v={})
        SW.STATE["initial_done"] = False; SW._NC["t"] = 0; SW._NP_C.update(t=0, v=set()); SW._DEFER.clear()
        self.calls = []
        SW.fetch_all = lambda urls: ([{"url": U1, "final": U1, "ok": True, "text": TEXT1, "label": "USGS", "err": ""},
                                      {"url": U2, "final": U2, "ok": True, "text": TEXT2, "label": "Example News", "err": ""}], [])
    def tearDown(self):
        import story_report as SR; SR.REPORTS = self._sr_reports; SR._RC.update(mt=None, v={})
        import story_v3 as V3; V3._BR.update(mt=None, v={})
        for k, v in _ORIG_ENV.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
    def api(self, *responses):
        it = iter(responses)
        def f(msgs, max_tokens=6000):
            self.calls.append(msgs); return next(it), {"in": 6000, "out": 1500}
        return f
    def run_all(self, api):
        n = 0
        while True:
            k = SW.db(); j = SW.next_job(k); k.close()
            if not j: return n
            SW.write_one(j, api=api); n += 1

class Writer(Base):
    def test_new_item_written_and_rendered(self):
        mkdb([("aaaaaaaaaaaaaaaa", "M6.8 earthquake Banda Sea Indonesia", 6)])
        SW.scan(); self.assertEqual(self.run_all(self.api(good())), 1)
        n = SW.note_for("aaaaaaaaaaaaaaaa")
        self.assertEqual(n["risk"], "Medium")            # capped to the rank 6 band
        self.assertEqual(n["sources"], [U1, U2]); self.assertIn("sections", n["story"])
        import story_v3 as V3
        self.assertEqual(V3.note_for("aaaaaaaaaaaaaaaa")["file"], "story_writer")
        st = SW.status(); self.assertEqual(st["briefs"]["written"], 1)
        self.assertAlmostEqual(st["spend_today"]["usd"], 6000 * 1.25e-6 + 1500 * 2.5e-6, places=6)
        self.assertNotIn("test-not-a-key", json.dumps(st))

    def test_arrival_after_boot_is_new_with_latency(self):
        mkdb([("9999999999999999", "Old story already on the board", 6)])
        SW.scan(); self.run_all(self.api(good()))
        mkdb([("9999999999999999", "Old story already on the board", 6), ("8888888888888888", "M6.8 earthquake Banda Sea Indonesia", 5)])
        SW.scan()
        k = SW.db(); j = k.execute("SELECT reason FROM jobs WHERE cid='8888888888888888'").fetchone(); k.close()
        self.assertEqual(j["reason"], "new")
        self.run_all(self.api(good()))
        st = SW.status(); self.assertEqual(st["latency_new_s"]["n"], 1); self.assertLess(st["latency_new_s"]["median"], 5)

    def test_near_duplicates_get_one_write_up(self):
        mkdb([("3333333333333333", "Edgewater declares a state of emergency as flooding hits the city", 7),
              ("4444444444444444", "Edgewater declares state of emergency amid flooding", 7),
              ("5555555555555555", "Edgewater declares a state of emergency as flooding hits the city", 7)])
        SW.scan(); self.assertEqual(self.run_all(self.api(good())), 1)
        a, b, c = (SW.note_for(x) for x in ("3333333333333333", "4444444444444444", "5555555555555555"))
        self.assertIsNotNone(a); self.assertEqual(a, b); self.assertEqual(a, c)

    def test_below_min_rank_ignored(self):
        mkdb([("bbbbbbbbbbbbbbbb", "Small quake somewhere", 4)])
        SW.scan(); self.assertEqual(self.run_all(self.api()), 0)

    def test_retry_once_then_publish(self):
        mkdb([("cccccccccccccccc", "M6.8 earthquake Banda Sea Indonesia", 7)])
        SW.scan(); self.run_all(self.api(good(extra=" At least 412 people died."), good()))
        self.assertEqual(len(self.calls), 2)
        self.assertIn("412", self.calls[1][-1]["content"])
        self.assertIsNotNone(SW.note_for("cccccccccccccccc"))

    def test_two_bad_answers_never_publish(self):
        mkdb([("dddddddddddddddd", "M6.8 earthquake Banda Sea Indonesia", 7)])
        SW.scan(); self.run_all(self.api(good(urls=(U1, "https://invented.example/x")), "not json"))
        self.assertIsNone(SW.note_for("dddddddddddddddd"))
        k = SW.db(); r = k.execute("SELECT status, err FROM jobs").fetchone(); k.close()
        self.assertEqual(r["status"], "failed")

    def test_validate_rules(self):
        corpus = TEXT1 + TEXT2
        o = json.loads(good()); o["dek"] = ""; o["story"]["dek"] = "BREAKING: verified first."
        _, probs = SW.validate(o, 6, [U1, U2], corpus)
        self.assertTrue(any("banned" in p for p in probs))
        o = json.loads(good()); o["story"]["sections"]["analysis"] += ' The agency called it "a once in a century disaster for the region".'
        _, probs = SW.validate(o, 6, [U1, U2], corpus)
        self.assertTrue(any("quote" in p for p in probs))
        _, probs = SW.validate(json.loads(good()), 6, [U1, U2], corpus + " 2026 11 21 Nov")
        self.assertEqual(probs, [])

    def test_desk_brief_wins(self):
        mkdb([("eeeeeeeeeeeeeeee", "M6.8 earthquake Banda Sea Indonesia", 8)])
        json.dump({"notes": {"eeeeeeeeeeeeeeee": {"what_happened": "Desk text.", "sources": [U1], "desk": True}}}, open(os.environ["BN_STORY_REPORTS"], "w")); SW._NC["t"] = 0
        SW.scan(); self.assertEqual(self.run_all(self.api()), 0)
        import story_v3 as V3; self.assertEqual(V3.note_for("eeeeeeeeeeeeeeee")["what_happened"], "Desk text.")

    def test_near_duplicate_aliases_desk_brief(self):
        mkdb([("1111111111111111", "Flood warning Edgewater Volusia County Florida rivers", 7),
              ("2222222222222222", "Flood warning Edgewater Volusia County Florida rivers update", 7)])
        json.dump({"notes": {"1111111111111111": {"what_happened": "Desk flood text.", "sources": [U1], "desk": True}}}, open(os.environ["BN_STORY_REPORTS"], "w")); SW._NC["t"] = 0
        SW.scan(); self.assertEqual(self.run_all(self.api()), 0)
        self.assertEqual(SW.note_for("2222222222222222")["what_happened"], "Desk flood text.")

    def test_daily_cap_defers(self):
        os.environ["BN_WRITER_DAILY_USD"] = "0.000001"
        try:
            mkdb([("ffffffffffffffff", "M6.8 earthquake Banda Sea Indonesia", 7)])
            k = SW.db(); SW._add_spend(k, 1, 1, 0.01); k.commit(); k.close()
            SW.scan(); self.run_all(self.api())
            k = SW.db(); r = k.execute("SELECT status, err FROM jobs").fetchone(); k.close()
            self.assertEqual(r["status"], "deferred"); self.assertIn("daily cap", r["err"]); self.assertEqual(self.calls, [])
        finally: os.environ.pop("BN_WRITER_DAILY_USD")

    def test_api_error_falls_back(self):
        mkdb([("abababababababab", "M6.8 earthquake Banda Sea Indonesia", 7)])
        def boom(msgs, max_tokens=6000): raise SW.APIError("HTTP 503")
        SW.scan(); self.run_all(boom)
        self.assertIsNone(SW.note_for("abababababababab"))
        k = SW.db(); self.assertEqual(k.execute("SELECT status FROM jobs").fetchone()[0], "deferred"); k.close()

    def test_no_source_text_defers(self):
        mkdb([("cdcdcdcdcdcdcdcd", "M6.8 earthquake Banda Sea Indonesia", 7)])
        SW.fetch_all = lambda urls: ([], [{"err": "HTTP 403"}])
        SW.scan(); self.run_all(self.api())
        self.assertEqual(self.calls, [])

    def test_private_hosts_refused(self):
        for u in ("http://127.0.0.1/x", "http://169.254.169.254/latest", "file:///etc/passwd", "http://localhost:10000/"):
            self.assertFalse(SW._public_host(u), u)

    def test_thread_name_passes_web_node_guard(self):
        n = SW._writer_worker.__name__.lower()
        self.assertFalse(any(w in n for w in ("loop", "harvest", "indexer")))

    def test_defaults_are_cheap_no_rewrite(self):
        c = SW.cfg()
        self.assertEqual(c["model"], "grok-4.20-0309-non-reasoning")
        self.assertEqual(c["daily_usd"], 0.25)
        self.assertEqual(c["min_rank"], 5)
        self.assertFalse(SW.rewrite_allowed())

    def test_old_spend_does_not_eat_new_cap(self):
        k = SW.db()
        k.execute("INSERT INTO spend(day, usd, tokens_in, tokens_out, calls) VALUES(?,?,?,?,?)", (SW.et_day(), 1.0, 100, 100, 10))
        k.commit()
        self.assertGreaterEqual(SW.spent_all_today(k)["usd"], 1.0)
        self.assertEqual(SW.spent_today(k)["usd"], 0.0)
        self.assertIsNone(SW.blocked_reason(k))
        k.close()

    def test_no_rewrite_when_new_sources_arrive(self):
        mkdb([("abababababababab", "M6.8 earthquake struck the Banda Sea off Indonesia", 7)])
        SW.scan(); self.run_all(self.api(good()))
        self.assertIsNotNone(SW.note_for("abababababababab"))
        # pretend two new sources and a later update
        k = SW.db()
        k.execute("UPDATE briefs SET written_at=?, src_urls=? WHERE cid=?",
                  (SW.iso(NOW - timedelta(hours=3)), "[]", "abababababababab"))
        k.commit(); k.close()
        src = sqlite3.connect(os.environ["BN_WRITER_SOURCE_DB"])
        src.execute("UPDATE clusters SET updated=? WHERE cluster_id=?", (SW.iso(NOW), "abababababababab"))
        src.commit(); src.close()
        SW.STATE["initial_done"] = True
        SW.scan()
        k = SW.db()
        n = k.execute("SELECT COUNT(*) FROM jobs WHERE reason LIKE 'refresh%'").fetchone()[0]
        k.close()
        self.assertEqual(n, 0)

    def test_template_is_upgraded_once_not_rewritten(self):
        mkdb([("acacacacacacacac", "M6.8 earthquake struck the Banda Sea off Indonesia", 7)])
        r, al = SW.cluster("acacacacacacacac")
        note = SW.build_template(r, al)
        k = SW.db()
        k.execute("INSERT OR REPLACE INTO briefs(cid, note, written_at, model, src_urls, alias_of, tokens_in, tokens_out, usd, rank, title) VALUES(?,?,?,?,?,NULL,0,0,0,?,?)",
                  ("acacacacacacacac", __import__("json").dumps(note), SW.iso(), "template", "[]", 7, r["title"]))
        k.commit(); k.close(); SW._NC["t"] = 0
        SW.scan()
        k = SW.db(); job = k.execute("SELECT reason FROM jobs WHERE cid=?", ("acacacacacacacac",)).fetchone(); k.close()
        self.assertIsNotNone(job); self.assertEqual(job["reason"], "upgrade")
        self.run_all(self.api(good()))
        n = SW.note_for("acacacacacacacac")
        self.assertIsNotNone(n)
        self.assertNotEqual(n.get("file"), "story_writer_template")
        self.assertTrue(SW.has_paid_article("acacacacacacacac"))
        # a second scan must not queue a rewrite
        SW.scan()
        k = SW.db()
        q = k.execute("SELECT COUNT(*) FROM jobs WHERE cid=? AND status='queued'", ("acacacacacacacac",)).fetchone()[0]
        k.close()
        self.assertEqual(q, 0)


    def test_requeue_skips_refresh_when_rewrites_disabled(self):
        mkdb([("adadadadadadadad", "M6.8 earthquake struck the Banda Sea off Indonesia", 6)])
        k = SW.db()
        past = SW.iso(NOW - timedelta(hours=2))
        k.execute("INSERT INTO jobs(cid, reason, status, arrived_at, finished, err, rank, title) VALUES(?,?,?,?,?,?,?,?)",
                  ("adadadadadadadad", "refresh: new sources", "deferred", past, past, "no readable source text yet", 6, "quake"))
        k.execute("INSERT INTO jobs(cid, reason, status, arrived_at, finished, err, rank, title) VALUES(?,?,?,?,?,?,?,?)",
                  ("aeaeaeaeaeaeaeae", "new", "deferred", past, past, "no readable source text yet", 6, "other"))
        k.commit()
        self.assertFalse(SW.rewrite_allowed())
        SW._requeue_deferred(k); k.commit()
        rows = {r["cid"]: (r["status"], r["err"] or "") for r in k.execute("SELECT cid, status, err FROM jobs")}
        k.close()
        self.assertEqual(rows["adadadadadadadad"][0], "skipped")
        self.assertIn("rewrites disabled", rows["adadadadadadadad"][1])
        self.assertEqual(rows["aeaeaeaeaeaeaeae"][0], "queued")

if __name__ == "__main__":
    unittest.main()
