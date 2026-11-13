"""Breaking-alert brief hold (Matt, Nov 13): a breaking alert goes out only once its /wire/<id> page shows a full brief, the same rule
as the newsletter's require_story_brief. No network, no email sent (live sending is not approved here, so a run writes one outbox preview).
Run: cd app && python3 -m unittest tests.test_breaking_brief_hold -v
"""
import json, os, socket, sqlite3, sys, tempfile, unittest
from datetime import datetime, timezone, timedelta
TMP = tempfile.mkdtemp(prefix="brkhold_")
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
import story_report as SR

A, B, C, D = "a1" * 8, "b2" * 8, "c3" * 8, "d4" * 8
NOTE = {"what_happened": "Officials said X happened on Thursday.", "headline": "X happened", "sources": [{"url": "https://example.org/x"}]}
AT = datetime(2026, 11, 13, 16, 0, tzinfo=timezone.utc)   # 11 AM ET, outside quiet hours
ROW = lambda cid, rank=8: {"cluster_id": cid, "rank": rank, "eff_families": 3, "title": f"story {cid[:2]}", "brief": ""}

OWN = {"src": "src.db", "db": "nl.db", "cfg": "nl_config.json", "outbox": "outbox", "log": "nl.log"}   # this module's own files, even when
                                                                                                    # another test module imported newsletter first
def seed_src():
    p = os.path.join(TMP, "src.db")
    if os.path.exists(p): os.remove(p)
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT,
                 first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT,
                 watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER, eff_families INTEGER, rank INTEGER, pushed_at TEXT)""")
    c.execute("CREATE TABLE alerts(id TEXT, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT)")
    t = (AT - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for cid, title in ((A, "Missile strike kills 12 in city A, officials say"), (B, "Explosion at port B kills 9, officials say")):
        c.execute("INSERT INTO clusters VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, title, "war/conflict", "X", None, None, t, t, t, 80, "High", 4, 3, json.dumps(["AP", "BBC", "Reuters"]), "[]", 0, "", t, 0, 0, 3, 8, None))
        c.execute("INSERT INTO alerts(id,source,family,title,category,source_url,event_time,base,official,extra,first_seen,last_seen,cluster_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid + "x", "AP", "AP", title, "war/conflict", "https://example.org/" + cid, t, 60, 1, "{}", t, t, cid))
    c.commit(); c.close()

class Gate(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(TMP, "story_reports.json")
        self._old = SR.REPORTS; SR.REPORTS = self.path; SR._RC.update(mt=None, v={}); NL._BRK_HELD["ids"] = None
    def tearDown(self):
        SR.REPORTS = self._old; SR._RC.update(mt=None, v={})
        if os.path.exists(self.path): os.remove(self.path)
    def write(self, d):
        with open(self.path, "w") as f: json.dump(d, f)
        SR._RC.update(mt=None, v={})

    def test_default_on(self):
        self.assertTrue(NL.DEFAULTS["breaking"]["require_story_brief"])
        self.assertTrue(NL.cfg()["breaking"]["require_story_brief"])   # nested default survives a config file without the key

    def test_holds_unbriefed_and_desk_hold_keeps_briefed_and_alias(self):
        self.write({"notes": {A: NOTE, "f" * 16: NOTE, C: NOTE}, "alias": {D: "f" * 16}, "newsletter_hold": [C]})
        kept, held = NL._breaking_brief_hold([(ROW(A), "B2", 1), (ROW(B), "B2", 1), (ROW(C), "B2", 1), (ROW(D), "B1", 1)], dict(NL.DEFAULTS))
        self.assertEqual([x[0]["cluster_id"] for x in kept], [A, D])
        self.assertEqual(dict(held), {B: "no brief on its story page yet", C: "desk hold list"})

    def test_empty_what_happened_is_not_a_brief(self):
        self.write({"notes": {A: dict(NOTE, what_happened="  ")}})
        kept, held = NL._breaking_brief_hold([(ROW(A), "B2", 1)], dict(NL.DEFAULTS))
        self.assertEqual(kept, []); self.assertEqual(held[0][0], A)

    def test_missing_reports_fails_closed(self):
        kept, held = NL._breaking_brief_hold([(ROW(A), "B2", 1)], dict(NL.DEFAULTS))
        self.assertEqual(kept, []); self.assertIn("unavailable", held[0][1])

    def test_flag_off_passes_everything(self):
        c = json.loads(json.dumps(NL.DEFAULTS)); c["breaking"]["require_story_brief"] = False
        kept, held = NL._breaking_brief_hold([(ROW(A), "B2", 1)], c)
        self.assertEqual(len(kept), 1); self.assertEqual(held, [])

class RunBreaking(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(TMP, "story_reports.json")
        self._old = SR.REPORTS; SR.REPORTS = self.path; SR._RC.update(mt=None, v={}); NL._BRK_HELD["ids"] = None
        self._P = dict(NL.P); NL.P.update({k: os.path.join(TMP, v) for k, v in OWN.items() if k in NL.P})
        seed_src()
        if os.path.exists(NL.P["db"]): os.remove(NL.P["db"])
        NL._INIT.clear(); NL.db().close()
    def tearDown(self):
        NL.P.clear(); NL.P.update(self._P); NL._INIT.clear()
        SR.REPORTS = self._old; SR._RC.update(mt=None, v={})
        if os.path.exists(self.path): os.remove(self.path)
    def write(self, d):
        with open(self.path, "w") as f: json.dump(d, f)
        SR._RC.update(mt=None, v={})
    def seen(self):
        k = NL.db(); s = {r["cluster_id"] for r in k.execute("SELECT cluster_id FROM breaking_seen")}; k.close(); return s

    def test_candidates_still_found(self):
        self.assertEqual({r["cluster_id"] for r, _, _ in NL.breaking_candidates(AT)}, {A, B})

    def test_dry_run_only_briefed(self):
        self.write({"notes": {A: NOTE}})
        res = NL.run_breaking(AT, dry_run=True)
        self.assertEqual([k for k, _ in res], [f"breaking:dry:{A}"])

    def test_nothing_briefed_sends_nothing_and_marks_nothing_seen(self):
        self.write({"notes": {}})
        self.assertEqual(NL.run_breaking(AT), [])
        self.assertEqual(self.seen(), set())

    def test_held_story_alerts_later_once_briefed(self):
        self.write({"notes": {A: NOTE}})
        res = NL.run_breaking(AT)
        self.assertEqual(len(res), 1); self.assertEqual(self.seen(), {A})          # B held, not marked seen
        self.write({"notes": {A: NOTE, B: NOTE}})
        res2 = NL.run_breaking(AT + timedelta(hours=3), dry_run=True)               # past min_gap_hours; brief for B is now live
        self.assertEqual([k for k, _ in res2], [f"breaking:dry:{B}"])

if __name__ == "__main__":
    unittest.main()
