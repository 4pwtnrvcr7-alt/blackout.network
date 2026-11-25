"""Publish gate + free template write-ups (story_writer.py, Nov 25 2026). No network, no xAI.
Run: cd app && python3 -m unittest tests.test_publish_gate tests.test_story_writer -v
"""
import json, os, sqlite3, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

TMP = tempfile.mkdtemp()
_KEYS = ("BN_WRITER_DB", "BN_WRITER_SOURCE_DB", "BN_STORY_REPORTS", "BN_STORY_V3_BRIEFS", "XAI_API_KEY", "BN_WRITER", "BN_TEMPLATES", "BN_PUBLISH_GATE")
_ORIG = {k: os.environ.get(k) for k in _KEYS}
os.environ["BN_WRITER_DB"] = os.path.join(TMP, "sw.db")
os.environ["BN_WRITER_SOURCE_DB"] = os.path.join(TMP, "blackout.db")
os.environ["BN_STORY_REPORTS"] = os.path.join(TMP, "story_reports.json")
os.environ["BN_STORY_V3_BRIEFS"] = os.path.join(TMP, "nov3.json")
os.environ["XAI_API_KEY"] = "test-not-a-key"
os.environ["BN_WRITER"] = "0"
import story_writer as SW

def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
NOW = datetime.now(timezone.utc)
U1 = "https://earthquake.usgs.gov/earthquakes/eventpage/us6000test"

def mkdb(rows, first_seen=None):
    p = os.environ["BN_WRITER_SOURCE_DB"]
    if os.path.exists(p): os.unlink(p)
    k = sqlite3.connect(p)
    k.executescript("""CREATE TABLE alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL,
      location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT);
      CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT,
      score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT,
      rising INTEGER DEFAULT 0, mentions_3h INTEGER DEFAULT 0, eff_families INTEGER DEFAULT 0, rank INTEGER DEFAULT 0, pushed_at TEXT);""")
    for i, row in enumerate(rows):
        cid, title, rank = row[0], row[1], row[2]
        t = first_seen or iso(NOW - timedelta(minutes=30 + i))
        brief = "WHAT: " + title + " WHERE: Indonesia WHEN: Nov 21, 2026 CONFIDENCE: High"
        links = json.dumps([{"source": "USGS", "url": U1}])
        k.execute("INSERT INTO clusters(cluster_id,title,category,location,first_seen,updated,score,n_items,n_families,families,links,watchlist,brief,rank,eff_families) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,2)", (cid, title, "natural disaster", "Indonesia", t, t, 80, 2, 2, json.dumps(["USGS","News"]), links, brief, rank))
        k.execute("INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid + "a", "USGS", "USGS", title, "natural disaster", U1, t, -5, 130, "Indonesia", 0, 1, "", t, t, cid))
    k.commit(); k.close()

class Gate(unittest.TestCase):
    def setUp(self):
        os.environ["BN_WRITER_DB"] = os.path.join(TMP, "sw.db")
        os.environ["BN_WRITER_SOURCE_DB"] = os.path.join(TMP, "blackout.db")
        os.environ["BN_STORY_REPORTS"] = os.path.join(TMP, "story_reports.json")
        os.environ["BN_STORY_V3_BRIEFS"] = os.path.join(TMP, "nov3.json")
        os.environ["BN_WRITER"] = "0"
        os.environ["BN_TEMPLATES"] = "1"
        os.environ["BN_PUBLISH_GATE"] = "1"
        for p in (os.environ["BN_WRITER_DB"], os.environ["BN_STORY_REPORTS"], os.environ["BN_STORY_V3_BRIEFS"]):
            if os.path.exists(p): os.unlink(p)
        import story_report as SR
        self._sr = SR.REPORTS; SR.REPORTS = os.environ["BN_STORY_REPORTS"]; SR._RC.update(mt=None, v={})
        import story_v3 as V3; V3._BR.update(mt=None, v={})
        SW.STATE["initial_done"] = False; SW.STATE["gate_on"] = False; SW.STATE["gate_booted"] = False
        SW.STATE["held_alerts"] = 0; SW._NC["t"] = 0; SW._LEGACY_C.update(t=0, v=set()); SW._DEFER.clear()
        self._build_card = SW.build_card
        SW.build_card = lambda cid: True
    def tearDown(self):
        import story_report as SR; SR.REPORTS = self._sr; SR._RC.update(mt=None, v={})
        SW.build_card = self._build_card
        for k, v in _ORIG.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def test_template_from_db_no_api(self):
        mkdb([("aaaaaaaaaaaaaaaa", "M6.8 earthquake struck the Banda Sea off Indonesia", 3)])
        r, al = SW.cluster("aaaaaaaaaaaaaaaa")
        note = SW.build_template(r, al)
        self.assertTrue(note["what_happened"])
        self.assertIn("Indonesia", note["what_happened"] + (note.get("place") or ""))
        self.assertEqual(note["writer"]["model"], "template")
        self.assertIn(U1, note["sources"])
        self.assertIn("happened", note["story"]["sections"])
        self.assertNotIn("412", json.dumps(note))  # no invented casualty figure
        body = note["story"]["sections"]["happened"]
        self.assertIn("What we know", body)
        self.assertIn("What we do not know", body)
        self.assertIn("USGS", body)

    def test_package_makes_ready_without_api(self):
        mkdb([("bbbbbbbbbbbbbbbb", "M6.8 earthquake struck the Banda Sea off Indonesia", 2)])
        self.assertTrue(SW.package_one("bbbbbbbbbbbbbbbb"))
        self.assertTrue(SW.is_packaged("bbbbbbbbbbbbbbbb"))
        n = SW.note_for("bbbbbbbbbbbbbbbb")
        self.assertEqual(n["file"], "story_writer_template")
        self.assertTrue(n["what_happened"])

    def test_new_item_held_until_packaged(self):
        mkdb([("cccccccccccccccc", "Flood warning in Jakarta Indonesia", 4)])
        SW.boot_gate()  # snapshots this cid as legacy
        self.assertTrue(SW.gate_on())
        # a brand-new cluster, not in the snapshot
        k = sqlite3.connect(os.environ["BN_WRITER_SOURCE_DB"])
        t = iso(NOW)
        k.execute("INSERT INTO clusters(cluster_id,title,category,location,first_seen,updated,score,n_items,n_families,families,links,watchlist,brief,rank,eff_families) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,1)",
                  ("dddddddddddddddd", "Wildfire alert in Sumatra Indonesia", "natural disaster", "Sumatra, Indonesia", t, t, 40, 1, 1, "[]", "[]",
                   "WHAT: Wildfire alert in Sumatra WHERE: Sumatra, Indonesia", 1))
        k.commit(); k.close()
        self.assertTrue(SW.allow("cccccccccccccccc"))   # grandfathered
        self.assertFalse(SW.allow("dddddddddddddddd"))  # held
        self.assertTrue(SW.package_one("dddddddddddddddd"))
        self.assertTrue(SW.allow("dddddddddddddddd"))

    def test_start_runs_when_paid_writer_is_off(self):
        self.assertFalse(SW.api_enabled())
        self.assertTrue(SW.templates_on())
        self.assertTrue(SW.templates_on() or SW.api_enabled())
        # worker must still boot the gate and package templates when the paid writer is off
        self.assertFalse((not SW.templates_on()) and (not SW.api_enabled()))
        os.environ["BN_TEMPLATES"] = "0"; os.environ["BN_WRITER"] = "0"
        # only when BOTH are off should the worker idle
        import story_writer as SW2
        # re-read env through helpers
        self.assertFalse(SW.templates_on())
        self.assertTrue((not SW.templates_on()) and (not SW.api_enabled()))

    def test_held_alert_after_15_min(self):
        mkdb([("eeeeeeeeeeeeeeee", "Storm in Jakarta Indonesia", 1)])
        SW.boot_gate()
        k = sqlite3.connect(os.environ["BN_WRITER_SOURCE_DB"])
        t = iso(NOW)
        k.execute("INSERT INTO clusters(cluster_id,title,category,location,first_seen,updated,score,n_items,n_families,families,links,watchlist,brief,rank,eff_families) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,1)",
                  ("ffffffffffffffff", "Landslide reported near Bandung Indonesia", "natural disaster", "Bandung, Indonesia", t, t, 20, 1, 1, "[]", "[]", "WHAT: Landslide", 1))
        k.commit(); k.close()
        SW.build_card = lambda cid: False
        self.assertFalse(SW.package_one("ffffffffffffffff"))
        with SW._LK:
            db = SW.db()
            old = iso(NOW - timedelta(minutes=16))
            db.execute("UPDATE held SET since=? WHERE cid=?", (old, "ffffffffffffffff"))
            db.commit(); db.close()
        SW.check_held_alerts()
        st = SW.held_status()
        self.assertGreaterEqual(st["alerts"], 1)
        self.assertFalse(SW.allow("ffffffffffffffff"))

    def test_desk_brief_still_wins_over_template(self):
        mkdb([("1111111111111111", "M6.8 earthquake struck the Banda Sea off Indonesia", 8)])
        json.dump({"notes": {"1111111111111111": {"what_happened": "Desk text.", "sources": [U1], "desk": True, "headline": "Desk"}}},
                  open(os.environ["BN_STORY_REPORTS"], "w"))
        SW._NC["t"] = 0
        import story_report as SR; SR._RC.update(mt=None, v={})
        self.assertTrue(SW.package_one("1111111111111111"))
        import story_v3 as V3; V3._BR.update(mt=None, v={})
        self.assertEqual(V3.note_for("1111111111111111")["what_happened"], "Desk text.")

    def test_gate_filters_wire_timeline_helper(self):
        mkdb([("2222222222222222", "Flooding in Jakarta Indonesia", 2)])
        SW.STATE["gate_on"] = True
        SW.STATE["gate_booted"] = True
        self.assertFalse(SW.allow("2222222222222222"))
        SW.package_one("2222222222222222")
        self.assertTrue(SW.allow("2222222222222222"))

    def test_filter_rows(self):
        mkdb([("3333333333333333", "Flooding in Jakarta Indonesia", 2)])
        SW.STATE["gate_on"] = True; SW.STATE["gate_booted"] = True
        rows = [{"cluster_id": "3333333333333333", "title": "x"}, {"cluster_id": "0000000000000000", "title": "y"}]
        self.assertEqual(SW.filter_rows(rows), [])
        SW.package_one("3333333333333333")
        got = SW.filter_rows(rows)
        self.assertEqual([r["cluster_id"] for r in got], ["3333333333333333"])

if __name__ == "__main__":
    unittest.main()
