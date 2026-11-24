"""newsletter.db restore guard (Nov 24, pt1847u): never overwrite a live subscriber list with an older or smaller copy.
Read-only on both files; never mutates subscriber rows. No network.
Run: cd app && python3 -m unittest tests.test_nl_restore_guard -v
"""
import os, sqlite3, tempfile, unittest, shutil
import nl_restore_guard as G

def make_db(path, rows):
    """rows: list of dicts with email, status, and optional timestamps. Creates a minimal subscribers table."""
    if os.path.exists(path): os.unlink(path)
    k = sqlite3.connect(path)
    k.execute("""CREATE TABLE subscribers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, status TEXT, created TEXT, confirmed_at TEXT,
        unsubscribed_at TEXT, updated TEXT, last_sent_at TEXT)""")
    for r in rows:
        k.execute("INSERT INTO subscribers(email,status,created,confirmed_at,unsubscribed_at,updated,last_sent_at) VALUES(?,?,?,?,?,?,?)",
                  (r["email"], r.get("status", "active"), r.get("created"), r.get("confirmed_at"),
                   r.get("unsubscribed_at"), r.get("updated"), r.get("last_sent_at")))
    k.commit(); k.close()

LIVE = [
    {"email": "a@example.invalid", "status": "active", "created": "2026-11-01T12:00:00Z", "confirmed_at": "2026-11-01T12:05:00Z", "updated": "2026-11-24T12:00:42Z", "last_sent_at": "2026-11-24T12:00:42Z"},
    {"email": "b@example.invalid", "status": "active", "created": "2026-11-08T12:00:00Z", "confirmed_at": "2026-11-08T12:05:00Z", "updated": "2026-11-24T12:00:41Z", "last_sent_at": "2026-11-24T12:00:41Z"},
    {"email": "c@example.invalid", "status": "active", "created": "2026-11-10T12:00:00Z", "confirmed_at": "2026-11-10T12:05:00Z", "updated": "2026-11-24T00:00:36Z"},
    {"email": "d@example.invalid", "status": "active", "created": "2026-11-15T12:00:00Z", "confirmed_at": "2026-11-15T12:05:00Z", "updated": "2026-11-23T12:00:00Z"},
    {"email": "e@example.invalid", "status": "active", "created": "2026-11-20T12:00:00Z", "confirmed_at": "2026-11-20T12:05:00Z", "updated": "2026-11-24T12:00:26Z"},
    {"email": "p1@example.invalid", "status": "pending", "created": "2026-11-21T12:00:00Z"},
    {"email": "p2@example.invalid", "status": "pending", "created": "2026-11-22T12:00:00Z"},
]
# Nov 9-era stale mirror: 3 active, 2 pending, newest last_sent 2026-11-09
STALE = [
    {"email": "a@example.invalid", "status": "active", "created": "2026-11-01T12:00:00Z", "confirmed_at": "2026-11-01T12:05:00Z", "updated": "2026-11-09T15:00:00Z", "last_sent_at": "2026-11-09T12:00:14Z"},
    {"email": "b@example.invalid", "status": "active", "created": "2026-11-08T12:00:00Z", "confirmed_at": "2026-11-08T12:05:00Z", "updated": "2026-11-09T15:00:00Z", "last_sent_at": "2026-11-09T12:00:10Z"},
    {"email": "c@example.invalid", "status": "active", "created": "2026-11-02T12:00:00Z", "confirmed_at": "2026-11-02T12:05:00Z", "updated": "2026-11-08T12:00:00Z"},
    {"email": "p1@example.invalid", "status": "pending", "created": "2026-11-08T12:00:00Z"},
    {"email": "p2@example.invalid", "status": "pending", "created": "2026-11-08T20:00:00Z"},
]

class Guard(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="nlguard_")
        self.live = os.path.join(self.td, "live.db")
        self.inc = os.path.join(self.td, "inc.db")
    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_missing_live_installs_copy(self):
        make_db(self.inc, STALE)
        ok, why = G.should_restore(os.path.join(self.td, "nope.db"), self.inc)
        self.assertTrue(ok, why); self.assertIn("no live subscriber list", why)

    def test_empty_live_installs_copy(self):
        make_db(self.live, []); make_db(self.inc, STALE)
        ok, why = G.should_restore(self.live, self.inc)
        self.assertTrue(ok, why); self.assertIn("no live subscriber list", why)

    def test_stale_smaller_older_copy_skipped(self):
        make_db(self.live, LIVE); make_db(self.inc, STALE)
        ok, why = G.should_restore(self.live, self.inc)
        self.assertFalse(ok, why)
        self.assertIn("fewer active", why)
        self.assertIn("fewer subscriber rows", why)
        self.assertIn("older", why)
        # live file was not written to (same row count and emails)
        st = G.stats(self.live)
        self.assertEqual(st["active"], 5); self.assertEqual(st["rows"], 7)
        k = sqlite3.connect(f"file:{self.live}?mode=ro", uri=True)
        emails = [r[0] for r in k.execute("SELECT email FROM subscribers ORDER BY id")]; k.close()
        self.assertEqual(emails, [r["email"] for r in LIVE])

    def test_same_counts_but_older_timestamp_skipped(self):
        make_db(self.live, LIVE)
        older = [dict(r) for r in LIVE]
        for r in older:
            for c in ("updated", "last_sent_at", "confirmed_at", "created"):
                if r.get(c): r[c] = "2026-11-09T12:00:00Z"
        make_db(self.inc, older)
        ok, why = G.should_restore(self.live, self.inc)
        self.assertFalse(ok, why); self.assertIn("older", why)
        self.assertNotIn("fewer active", why)

    def test_handoff_same_or_newer_allowed(self):
        make_db(self.live, LIVE)
        newer = [dict(r) for r in LIVE]
        newer[0]["updated"] = "2026-11-24T18:00:00Z"; newer[0]["last_sent_at"] = "2026-11-24T18:00:00Z"
        make_db(self.inc, newer)
        ok, why = G.should_restore(self.live, self.inc)
        self.assertTrue(ok, why); self.assertIn("not older or smaller", why)

    def test_identical_copy_allowed(self):
        make_db(self.live, LIVE); shutil.copy2(self.live, self.inc)
        ok, why = G.should_restore(self.live, self.inc)
        self.assertTrue(ok, why)

    def test_more_rows_but_fewer_active_skipped(self):
        make_db(self.live, LIVE)
        # 4 active + 5 pending = 9 rows (more rows, fewer active)
        inc = [r for r in LIVE if r["status"] == "active"][:4]
        inc += [{"email": f"x{i}@example.invalid", "status": "pending", "created": "2026-11-24T20:00:00Z"} for i in range(5)]
        make_db(self.inc, inc)
        ok, why = G.should_restore(self.live, self.inc)
        self.assertFalse(ok, why); self.assertIn("fewer active", why)

    def test_unreadable_incoming_against_live_is_skipped(self):
        make_db(self.live, LIVE)
        with open(self.inc, "wb") as f: f.write(b"not a sqlite database")
        ok, why = G.should_restore(self.live, self.inc)
        self.assertFalse(ok, why)

    def test_stats_is_read_only(self):
        make_db(self.live, LIVE)
        before = os.stat(self.live).st_mtime
        G.stats(self.live)
        # reopen and confirm rows unchanged; mode=ro must not create a journal next to it
        k = sqlite3.connect(f"file:{self.live}?mode=ro", uri=True)
        n = k.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]; k.close()
        self.assertEqual(n, 7)
        self.assertFalse(os.path.exists(self.live + "-wal"))
        self.assertFalse(os.path.exists(self.live + "-journal"))
        self.assertEqual(os.stat(self.live).st_mtime, before)

if __name__ == "__main__":
    unittest.main()
