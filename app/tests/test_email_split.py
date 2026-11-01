"""Email split (tracked news.* identity vs untracked apex) and open/click consent. Run: cd app && python3 -m unittest tests.test_email_split -v
Temp files only; network blocked."""
import json, os, socket, sys, tempfile, unittest
TMP = tempfile.mkdtemp(prefix="nlsplit_")
for k, v in {"NEWSLETTER_DB": "nl.db", "NEWSLETTER_SRC_DB": "src.db", "NEWSLETTER_CONFIG": "nl_config.json", "NEWSLETTER_OUTBOX": "outbox",
             "NEWSLETTER_ENV": "creds/newsletter.env", "NEWSLETTER_PASSFILE": "PASS.txt", "NEWSLETTER_LOG": "nl.log", "NEWSLETTER_BO_CONFIG": "bo.json"}.items():
    os.environ[k] = os.path.join(TMP, v)
os.environ["NEWSLETTER_NO_WORKER"] = "1"
open(os.path.join(TMP, "PASS.txt"), "w").write("test-passcode\n"); json.dump({}, open(os.path.join(TMP, "bo.json"), "w"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _blocked(*a, **k): raise RuntimeError("network access attempted during tests")
socket.socket.connect = _blocked; socket.create_connection = _blocked
import newsletter as NL
ORIGIN = {"origin": "http://127.0.0.1:8787"}
TRACKED = "hello@news.blackout.network"

def setcfg(**kw):
    with open(NL.P["cfg"], "w") as f: json.dump(kw, f)
def signup(email, cc=None, **extra):
    h = dict(ORIGIN); h.update({"cf-ipcountry": cc} if cc else {})
    code, body = NL.subscribe({"email": email, "frequency": "twice", "csrf": NL.csrf_token(), **extra}, "203.0.113.%d" % (hash(email) % 200), h)
    assert code == 200, body
    k = NL.db(); r = k.execute("SELECT * FROM subscribers WHERE email=?", (email,)).fetchone(); k.close()
    assert NL.confirm(NL.sub_token("confirm", r))[0] == "ok"
    return row(email)
def row(email):
    k = NL.db(); r = k.execute("SELECT * FROM subscribers WHERE email=?", (email,)).fetchone(); k.close(); return r

class Split(unittest.TestCase):
    def setUp(self): setcfg(tracked_from_email=TRACKED)

    def test_us_default_on_eu_default_off(self):
        us, de, unk = signup("us1@mail.test", "US"), signup("de1@mail.test", "DE"), signup("unk1@mail.test")
        self.assertIsNone(us["tracking_consent"]); self.assertTrue(NL.tracking_ok(us))
        self.assertEqual(de["signup_cc"], "DE"); self.assertEqual(de["tracking_consent"], 0); self.assertFalse(NL.tracking_ok(de))
        self.assertIsNone(unk["signup_cc"]); self.assertFalse(NL.tracking_ok(unk))       # unknown country = consent needed
    def test_eu_opt_in_records_consent(self):
        r = signup("gb1@mail.test", "GB", track_consent=1)
        self.assertEqual(r["tracking_consent"], 1); self.assertTrue(r["tracking_consent_at"]); self.assertEqual(r["tracking_consent_version"], "2026-11-02")
        self.assertTrue(NL.tracking_ok(r))
        k = NL.db(); ev = k.execute("SELECT detail FROM events WHERE kind='consent' AND detail LIKE ?", (f"subscriber #{r['id']} %",)).fetchall(); k.close()
        self.assertTrue(any("on (signup)" in e[0] for e in ev))
    def test_shown_box_left_unticked_is_no(self):
        r = signup("us2@mail.test", "US", trk_shown=1); self.assertEqual(r["tracking_consent"], 0); self.assertFalse(NL.tracking_ok(r))
    def test_eu_area_needs_consent(self):
        r = signup("us3@mail.test", "US"); k = NL.db(); k.execute("UPDATE subscribers SET loc_cc='FR' WHERE id=?", (r["id"],)); k.commit(); k.close()
        self.assertFalse(NL.tracking_ok(row("us3@mail.test")))
    def test_no_tracked_identity_means_nobody_tracked(self):
        r = signup("us4@mail.test", "US"); setcfg(); self.assertFalse(NL.tracking_ok(r))
        self.assertNotIn("stop_tracking", NL.links_for(r))
    def test_mime_identity_and_footer(self):
        us, de = signup("us5@mail.test", "US"), signup("de5@mail.test", "DE")
        Lu, Ld = NL.links_for(us), NL.links_for(de)
        self.assertIn("stop_tracking", Lu); self.assertNotIn("stop_tracking", Ld)
        self.assertIn("Stop tracking my opens and clicks", NL.footer_buttons_html(Lu)); self.assertNotIn("Stop tracking", NL.footer_buttons_html(Ld))
        self.assertTrue(any("Stop tracking" in x for x in NL.footer_buttons_text(Lu)))
        m = NL.build_mime(us["email"], "s", "<p>x</p>", "x", Lu["unsubscribe"], "issue", NL.cfg(), tracked="stop_tracking" in Lu)
        self.assertIn(TRACKED, m["From"]); self.assertEqual(m["Reply-To"], "hello@blackout.network"); self.assertIn("@news.blackout.network", m["Message-ID"])
        m2 = NL.build_mime(de["email"], "s", "<p>x</p>", "x", Ld["unsubscribe"], "issue", NL.cfg(), tracked="stop_tracking" in Ld)
        self.assertIn("hello@blackout.network", m2["From"]); self.assertIsNone(m2["X-BN-Tracked"])
        m3 = NL.build_mime(us["email"], "Confirm", "<p>x</p>", "x", None, "confirm", NL.cfg())   # transactional never tracked
        self.assertIn("hello@blackout.network", m3["From"])
    def test_stop_tracking_link_is_scanner_safe(self):
        r = signup("us6@mail.test", "US"); tok = NL.sub_token("manage", r)
        code, html_, _ = NL.handle_get("/newsletter/stop_tracking", {"token": [tok]}); self.assertEqual(code, 200)
        self.assertTrue(NL.tracking_ok(row("us6@mail.test")))                       # GET changed nothing
        code, html_, _ = NL.handle_post("/newsletter/stop_tracking", {"token": tok}, headers=ORIGIN); self.assertEqual(code, 200)
        r2 = row("us6@mail.test"); self.assertEqual(r2["tracking_consent"], 0); self.assertFalse(NL.tracking_ok(r2))
        self.assertEqual(NL.handle_post("/newsletter/stop_tracking", {"token": "bad"}, headers=ORIGIN)[0], 400)
    def test_preferences_toggle(self):
        r = signup("ch7@mail.test", "CH"); tok = NL.sub_token("manage", r)
        self.assertIn('name="track_consent" value="1">', NL.prefs_form(tok, r))       # unticked for EEA/UK/CH by default
        code, body = NL.manage(tok, {"frequency": "twice", "trk_present": 1, "track_consent": 1}); self.assertEqual(code, 200)
        self.assertTrue(NL.tracking_ok(row("ch7@mail.test")))
        NL.manage(tok, {"frequency": "twice", "trk_present": 1}); self.assertFalse(NL.tracking_ok(row("ch7@mail.test")))
        NL.manage(tok, {"frequency": "morning"}); self.assertFalse(NL.tracking_ok(row("ch7@mail.test")))   # old clients without the toggle change nothing
    def test_signup_form_box_is_hidden_and_unticked(self):
        f = NL.form_html("page"); self.assertIn('class="nl-trk" hidden', f); self.assertNotIn('name="track_consent" value="1" checked', f)

if __name__ == "__main__": unittest.main()
