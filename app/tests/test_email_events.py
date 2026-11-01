"""Resend webhook receiver (email_events.py). Run: cd app && python3 -m unittest tests.test_email_events -v   (temp files only, no network)"""
import base64, json, os, socket, sqlite3, sys, tempfile, time, unittest
TMP = tempfile.mkdtemp(prefix="emev_")
for k, v in {"NEWSLETTER_DB": "nl.db", "NEWSLETTER_SRC_DB": "src.db", "NEWSLETTER_CONFIG": "nl_config.json", "NEWSLETTER_OUTBOX": "outbox",
             "NEWSLETTER_ENV": "creds/newsletter.env", "NEWSLETTER_PASSFILE": "PASS.txt", "NEWSLETTER_LOG": "nl.log", "NEWSLETTER_BO_CONFIG": "bo.json"}.items():
    os.environ[k] = os.path.join(TMP, v)
os.environ["NEWSLETTER_NO_WORKER"] = "1"
open(os.path.join(TMP, "PASS.txt"), "w").write("x\n"); open(os.path.join(TMP, "bo.json"), "w").write("{}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _blocked(*a, **k): raise RuntimeError("network access attempted during tests")
socket.socket.connect = _blocked; socket.create_connection = _blocked
import email_events as EV, newsletter as NL

SEC = "whsec_" + base64.b64encode(b"test-signing-key-0123456789abcdef").decode()   # test-only value
SITE = "https:" + "//blackout.network"   # built, so the prepublish link gate does not treat test data as a site link
DB = NL.P["db"]   # the first test module imported fixes newsletter paths

def hdrs(body, mid="msg_1", ts=None, sec=SEC):
    ts = str(int(ts if ts is not None else time.time()))
    return {"svix-id": mid, "svix-timestamp": ts, "svix-signature": "v1," + EV.sign(sec, mid, ts, body)}
def ev(typ="email.delivered", rid="re_abc", **data):
    return json.dumps({"type": typ, "created_at": "2026-11-02T12:00:00.000Z", "data": {"email_id": rid, "to": ["someone@mail.test"], "subject": "S", **data}}).encode()
def rows(): k = sqlite3.connect(DB); r = k.execute("SELECT svix_id,resend_id,type,ts,link,subscriber_id FROM email_events ORDER BY rowid").fetchall(); k.close(); return r

class Events(unittest.TestCase):
    def setUp(self):
        os.environ["RESEND_WEBHOOK_SECRET"] = SEC
        k = NL.db(); k.execute("DROP TABLE IF EXISTS email_events"); k.commit(); k.close()
    def test_disabled_without_secret(self):
        os.environ.pop("RESEND_WEBHOOK_SECRET"); b = ev()
        self.assertEqual(EV.handle(hdrs(b), b, DB)[0], 404)
    def test_signature_checks(self):
        b = ev()
        self.assertEqual(EV.handle(hdrs(b), b, DB)[0], 200)
        self.assertEqual(EV.handle(hdrs(b, "m2"), b + b" ", DB)[0], 401)                          # body altered
        self.assertEqual(EV.handle(hdrs(b, "m3", ts=time.time() - 600), b, DB)[0], 401)           # replay outside 5 min
        self.assertEqual(EV.handle(hdrs(b, "m4", sec="whsec_" + base64.b64encode(b"other").decode()), b, DB)[0], 401)
        self.assertEqual(EV.handle({"svix-id": "m5"}, b, DB)[0], 401)
        h = hdrs(b, "m6"); h["svix-signature"] = "v1,AAAA " + h["svix-signature"]                  # key rotation: any v1 matches
        self.assertEqual(EV.handle(h, b, DB)[0], 200)
        self.assertEqual(EV.handle(hdrs(b"x" * (EV.MAX_BODY + 1)), b"x" * (EV.MAX_BODY + 1), DB)[0], 413)
    def test_idempotent_and_minimal_storage(self):
        b = ev("email.clicked", click={"link": SITE + "/newsletter/manage?token=SECRET#x", "ipAddress": "198.51.100.7",
                                        "userAgent": "UA", "timestamp": "2026-11-02T12:00:30Z"})
        for _ in range(3): self.assertEqual(EV.handle(hdrs(b, "dup"), b, DB)[0], 200)
        r = rows(); self.assertEqual(len(r), 1)
        self.assertEqual(r[0][2:5], ("clicked", "2026-11-02T12:00:30Z", SITE + "/newsletter/manage"))   # no token, no fragment
        k = sqlite3.connect(DB); dump = json.dumps(k.execute("SELECT * FROM email_events").fetchall()); k.close()
        for bad in ("198.51.100.7", "someone@mail.test", "SECRET", "UA"): self.assertNotIn(bad, dump)
    def test_types(self):
        for i, t in enumerate(["email.delivered", "email.opened", "email.clicked", "email.bounced", "email.complained", "email.failed", "email.suppressed"]):
            b = ev(t); self.assertEqual(EV.handle(hdrs(b, f"t{i}"), b, DB)[1]["result"], "stored")
        b = ev("email.sent"); self.assertEqual(EV.handle(hdrs(b, "tx"), b, DB)[1]["result"], "ignored")
        self.assertEqual(len(rows()), 7)
    def test_subscriber_lookup_and_unsubscribe_purge(self):
        k = NL.db(); t = NL.iso(NL.now())
        k.execute("INSERT INTO subscribers(email,status,created,updated,confirmed_at) VALUES('p@mail.test','active',?,?,?)", (t, t, t)); sid = k.execute("SELECT id FROM subscribers WHERE email='p@mail.test'").fetchone()[0]
        k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,outbox_file) VALUES(?,?,?,?,?,?)", (t, "issue", sid, "resend", "sent", "resend:re_sub")); k.commit()
        r = k.execute("SELECT * FROM subscribers WHERE id=?", (sid,)).fetchone(); k.close()
        b = ev("email.opened", rid="re_sub"); EV.handle(hdrs(b, "o1"), b, DB)
        self.assertEqual(rows()[0][5], sid)
        self.assertEqual(NL.unsubscribe(NL.sub_token("unsub", r))[0], "ok")
        self.assertEqual(rows(), [])
    def test_bounded(self):
        k = sqlite3.connect(DB); EV.init(k)
        old = time.time() - 400 * 86400
        for i in range(5): EV.store(k, f"old{i}", json.loads(ev()), now=old)
        k.commit(); EV.prune(k); k.commit()
        self.assertEqual(k.execute("SELECT COUNT(*) FROM email_events").fetchone()[0], 0)
        saved = EV.MAX_ROWS; EV.MAX_ROWS = 3
        try:
            for i in range(6): EV.store(k, f"n{i}", json.loads(ev()))
            EV.prune(k); k.commit()
            self.assertEqual([r[0] for r in k.execute("SELECT svix_id FROM email_events ORDER BY rowid")], ["n3", "n4", "n5"])
        finally: EV.MAX_ROWS = saved; k.close()
    def test_render_route_wired(self):
        src = open(os.path.join(os.path.dirname(EV.__file__), "render_app.py")).read()
        self.assertIn('path == "/api/email-events"', src); self.assertIn("EV.handle(self.headers, raw, NL.P[\"db\"])", src)

if __name__ == "__main__": unittest.main()
