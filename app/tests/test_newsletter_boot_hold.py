"""Nov 16: after a Render restart the scheduler must never auto-send a missed slot as a catch-up (owner approves via send_now),
but on-time slots and slots after a clean deploy handoff run normally. No network, no email sent.
Run: cd app && python3 -m unittest tests.test_newsletter_boot_hold -v"""
import json, os, socket, sys, tempfile, unittest
from datetime import datetime, timedelta
TMP = tempfile.mkdtemp(prefix="nlboot_")
for k, v in {"NEWSLETTER_DB": "nl.db", "NEWSLETTER_SRC_DB": "src.db", "NEWSLETTER_CONFIG": "nl_config.json",
             "NEWSLETTER_OUTBOX": "outbox", "NEWSLETTER_ENV": "creds/newsletter.env", "NEWSLETTER_PASSFILE": "PASS.txt",
             "NEWSLETTER_LOG": "nl.log", "NEWSLETTER_BO_CONFIG": "bo.json"}.items():
    os.environ[k] = os.path.join(TMP, v)
os.environ["NEWSLETTER_NO_WORKER"] = "1"
os.makedirs(os.path.join(TMP, "creds"), exist_ok=True)
open(os.path.join(TMP, "PASS.txt"), "w").write("x\n"); open(os.path.join(TMP, "bo.json"), "w").write("{}")
open(os.path.join(TMP, "nl_config.json"), "w").write(json.dumps({"live_sending_approved": False, "base_url": "https://blackout.network"}))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _blocked(*a, **k): raise RuntimeError("network access attempted during tests")
socket.socket.connect = _blocked; socket.create_connection = _blocked
import newsletter as NL

class BootHold(unittest.TestCase):
    def setUp(self):
        self.calls = []; self._rs = NL.run_slot; self._rb = NL.run_breaking; self._rc = NL.run_crime_alerts
        NL.run_slot = lambda key, s, at, c: (self.calls.append(key), ("sent", {}))[1]
        NL.run_breaking = lambda at, c: []; NL.run_crime_alerts = lambda at, c: []
        k = NL.db(); k.execute("DELETE FROM slot_runs"); k.execute("INSERT INTO slot_runs(slot_key,slot_time,status,started,note) VALUES('x','x','done','x','seed')"); k.commit(); k.close()
        NL.HELD.clear()
    def tearDown(self): NL.run_slot = self._rs; NL.run_breaking = self._rb; NL.run_crime_alerts = self._rc
    def t(self, h, m): return datetime(2026, 11, 16, h, m, tzinfo=NL.ET)
    def test_restart_after_slot_holds(self):
        NL.run_due(at=self.t(7, 20), hold_before=self.t(7, 15))
        self.assertNotIn("2026-11-16@morning", self.calls); self.assertIn("2026-11-16@morning", NL.HELD)
        k = NL.db(); r = k.execute("SELECT * FROM slot_runs WHERE slot_key='2026-11-16@morning'").fetchone(); k.close()
        self.assertIsNone(r)   # no row: owner send_now still possible, normal 'skipped' lands after the window
    def test_up_before_slot_runs_on_time(self):
        NL.run_due(at=self.t(7, 0) + timedelta(seconds=40), hold_before=self.t(6, 50))
        self.assertIn("2026-11-16@morning", self.calls)
    def test_no_hold_after_handoff(self):
        NL.run_due(at=self.t(7, 20), hold_before=None)
        self.assertIn("2026-11-16@morning", self.calls)
    def test_after_window_skipped(self):
        NL.run_due(at=self.t(9, 30), hold_before=self.t(9, 20))
        self.assertNotIn("2026-11-16@morning", self.calls)
        k = NL.db(); r = k.execute("SELECT status FROM slot_runs WHERE slot_key='2026-11-16@morning'").fetchone(); k.close()
        self.assertEqual(r["status"], "skipped")
if __name__ == "__main__": unittest.main()
