"""pt1755u: opt-in network outage report in the brief. Offline: temp databases, no network, no send."""
import os, sys, json, sqlite3, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
TMP = tempfile.mkdtemp(prefix="nlnet_")
open(os.path.join(TMP, "nl.env"), "w").write("NEWSLETTER_SENDER=preview\n")
os.environ.update({"NEWSLETTER_NO_WORKER": "1", "NEWSLETTER_ENV": os.path.join(TMP, "nl.env"), "NEWSLETTER_DB": os.path.join(TMP, "nl.db"),
                   "NEWSLETTER_SRC_DB": os.path.join(TMP, "src.db"), "NEWSLETTER_OUTBOX": os.path.join(TMP, "outbox"),
                   "NEWSLETTER_CONFIG": os.path.join(TMP, "newsletter_config.json"), "NEWSLETTER_ANALYSIS_JSON": os.path.join(TMP, "none.json"),
                   "NEWSLETTER_PASSFILE": os.path.join(TMP, "pass.txt"), "BN_STORY_REPORTS": os.path.join(TMP, "none_reports.json"), "BN_NL_WEATHER": "0"})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import newsletter as N
import newsletter_net as NET
UTC = timezone.utc
AT = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
LINKS = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter", "categories": "https://blackout.network/newsletter",
         "sources": "https://blackout.network/sources", "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}

def snap(bad=True):
    nets = [dict(id="x%d" % i, name="Net %d" % i, level=0, status="All Systems Operational", status_url="https://status.example.com/%d" % i) for i in range(10)]
    nets.append(dict(id="fedres", name="Federal Reserve", level=-1, link_only=True, status="see page", status_url="https://www.frbservices.org/service-status/"))
    if bad:
        nets[0].update(level=3, name="Example Cloud", incidents=[{"t": "Elevated errors in us-east-1"}])
        nets[1].update(level=2, name="Example Pay", status="Partial outage")
    return {"generated": "2026-11-23T11:55:00Z", "summary": {"networks": 10, "ok": 8 if bad else 10, "power_customers": 25000},
            "nets": nets, "outages": {"countries": [{"name": "Nigeria", "cur": True, "major": False}, {"name": "Peru", "cur": False}]}}

def _src():
    k = sqlite3.connect(N.P["src"])
    k.executescript("""CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE TABLE IF NOT EXISTS clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER, eff_families INTEGER, rank INTEGER, pushed_at TEXT);
    CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, started TEXT, finished TEXT, trigger TEXT, fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);""")
    k.commit(); k.close()

SUB = {"id": None, "frequency": "twice", "interests": '["all"]'}

class NetworkSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls): _src()
    def setUp(self): NET._C.clear()

    def _render(self, sub, data):
        with mock.patch.object(NET, "_snapshot", lambda c=None: data):
            issue = N.build_issue(sub, at=AT, slot="morning")
            subj, html, text = N.render(issue, LINKS)
        return issue, subj, html, text

    def test_opt_in_renders_and_passes_qa_gate(self):
        for bad in (True, False):
            issue, subj, html, text = self._render(dict(SUB, net_brief=1), snap(bad))
            self.assertTrue(issue.get("network"))
            self.assertIn("NETWORK STATUS", html); self.assertIn("NETWORK STATUS", text)
            self.assertIn("https://blackout.network/network", html); self.assertIn("Open the outage map", html)
            if bad:
                self.assertIn("2 of 10 tracked networks disrupted", html); self.assertIn("Example Cloud", html); self.assertIn("Elevated errors", text)
                self.assertLess(html.find("Example Cloud"), html.find("Example Pay"))
            else:
                self.assertIn("No major U.S. network outages right now", html)
            self.assertNotIn("Federal Reserve", html)        # link-only rows are never reported as status
            self.assertIn("25,000 U.S. power customers out", text); self.assertIn("Nigeria", text); self.assertNotIn("Peru", text)
            r = N.qa_gate(issue, subj, html, text, N.cfg())
            self.assertTrue(r is None or r["ok"], r and r["blockers"])

    def test_opted_out_or_unavailable_means_no_section(self):
        for sub, data in ((dict(SUB, net_brief=0), snap()), (dict(SUB), snap()), (dict(SUB, net_brief=1), None), (dict(SUB, net_brief=1), {"nets": "bad"})):
            issue, subj, html, text = self._render(sub, data)
            self.assertFalse(issue.get("network")); self.assertNotIn("NETWORK STATUS", html); self.assertNotIn("NETWORK STATUS", text)
            r = N.qa_gate(issue, subj, html, text, N.cfg())
            self.assertTrue(r is None or r["ok"], r and r["blockers"])

    def test_kill_switches(self):
        os.environ["BN_NL_NETWORK"] = "0"
        try: self.assertIsNone(NET.for_sub({"net_brief": 1}))
        finally: os.environ.pop("BN_NL_NETWORK", None)
        self.assertIsNone(NET.for_sub({"net_brief": 1}, {"network_section": False}))

    def test_snapshot_failure_is_none_not_raise(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            NET._C.clear(); self.assertIsNone(NET.for_sub({"net_brief": 1}, {"base_url": "https://blackout.invalid"}))

class OptInStorage(unittest.TestCase):
    def test_form_and_prefs_have_toggle(self):
        with mock.patch.object(N, "csrf_token", lambda: "t"): self.assertIn('name="net_brief"', N.form_html())
        js = open(os.path.join(os.path.dirname(N.__file__), "newsletter_static", "app.js")).read()
        self.assertEqual(js.count("net_brief:fd.get(\"net_brief\")?1:0"), 2)

    def test_signup_and_manage_store_choice(self):
        sent = []
        with mock.patch.object(N, "csrf_ok", lambda *a, **k: True), mock.patch.object(N, "send_transactional", lambda row, kind: sent.append(kind)), \
             mock.patch.object(N, "validate_email", lambda e: (str(e).lower(), None)):
            code, _ = N.subscribe({"email": "net-opt@example.org", "frequency": "twice", "interests": ["all"], "net_brief": 1}, ip="203.0.113.9")
            self.assertEqual(code, 200)
            code, _ = N.subscribe({"email": "net-no@example.org", "frequency": "twice", "interests": ["all"]}, ip="203.0.113.10")
        k = N.db()
        rows = {r["email"]: r for r in k.execute("SELECT * FROM subscribers")}
        self.assertEqual(rows["net-opt@example.org"]["net_brief"], 1); self.assertEqual(rows["net-no@example.org"]["net_brief"], 0)
        k.execute("UPDATE subscribers SET status='active', confirmed_at=? WHERE email='net-opt@example.org'", (N.iso(N.now()),)); k.commit()
        r = k.execute("SELECT * FROM subscribers WHERE email='net-opt@example.org'").fetchone(); k.close()
        with mock.patch.object(N, "token_sub", lambda tok, kind: ("ok", r)):
            self.assertEqual(N.manage("t", {"frequency": "twice", "net_present": 1})[0], 200)
        k = N.db(); self.assertEqual(k.execute("SELECT net_brief FROM subscribers WHERE email='net-opt@example.org'").fetchone()[0], 0)
        r = k.execute("SELECT * FROM subscribers WHERE email='net-opt@example.org'").fetchone(); k.close()
        with mock.patch.object(N, "token_sub", lambda tok, kind: ("ok", r)):
            N.manage("t", {"frequency": "twice", "net_present": 1, "net_brief": 1})
            r2 = r
        k = N.db(); self.assertEqual(k.execute("SELECT net_brief FROM subscribers WHERE email='net-opt@example.org'").fetchone()[0], 1)
        r = k.execute("SELECT * FROM subscribers WHERE email='net-opt@example.org'").fetchone(); k.close()
        with mock.patch.object(N, "token_sub", lambda tok, kind: ("ok", r)):
            N.manage("t", {"frequency": "twice"})          # an older form without the field keeps the saved choice
        k = N.db(); self.assertEqual(k.execute("SELECT net_brief FROM subscribers WHERE email='net-opt@example.org'").fetchone()[0], 1); k.close()
        self.assertTrue(all(x == "confirm" for x in sent))

if __name__ == "__main__": unittest.main()
