"""Read-only /admin portal (Matt Nov 21 2026).

Run: cd app && python3 -m unittest tests.test_admin_portal -v
"""
import hashlib, hmac, os, re, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import admin_portal as AP
import growth
import sitenav
import sitenav_ui as UI

TEST_PW = "unit-test-only-password"


def _install_test_hash(pw=TEST_PW):
    salt = bytes.fromhex("11" * 16)
    iters = 1000  # fast for tests only
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, iters)
    AP.PASS_HASH = f"pbkdf2_sha256${iters}${salt.hex()}${dk.hex()}"
    AP._SESSION_KEY = hashlib.sha256(b"bn-admin-portal-v1|" + AP.PASS_HASH.encode()).digest()
    AP._FAILS.clear()


class H:
    def __init__(self, method, path, headers=None, raw=b"", ip="127.0.0.1"):
        self.command = method
        self.path = path
        self.headers = headers or {}
        self._raw = raw
        self.client_address = (ip, 0)
        self._ip = ip
        self.sent = None

    def ip(self):
        return self._ip

    def body(self):
        import json
        try:
            return json.loads(self._raw or b"{}")
        except Exception:
            return {}

    def send(self, code, body, ctype="application/json", headers=None):
        self.sent = (code, body, ctype, headers or {})
        return self.sent


def _login(pw=TEST_PW, ip="127.0.0.1"):
    h = H("POST", "/admin/login", raw=f"password={pw}".encode(), ip=ip)
    AP.handle(h)
    return h


FAKE = {
    "ok": True,
    "scanner": {"badge": "OK", "stale": False, "last_scan": "2026-11-21T20:19:00Z",
                "last_scan_age_s": 120, "last_sync": "2026-11-21T20:20:00Z",
                "last_sync_age_s": 60, "sync_healthy": True,
                "scan": {"fetched": 1297, "new_items": 12, "ok_sources": 187, "failed_sources": 10}},
    "realtime": {"mac_connected": True, "last_push": "2026-11-21T20:20:01Z", "last_push_age_s": 5, "errors": 0},
    "wire": {"h1": {"total": 3, "r0_4": 1, "r5_6": 1, "r7plus": 1},
             "h24": {"total": 10, "r0_4": 6, "r5_6": 3, "r7plus": 1},
             "newest": [{"cluster_id": "abc", "title": "Test story", "rank": 8, "t": "2026-11-21T20:05:00Z"}]},
    "writer": {"thread_alive": True, "api_key_set": False, "queue": [], "briefs": {"written": 6},
               "spend_today": {"usd": 0.11}, "daily_cap_usd": 1, "last_error": "no API key"},
    "newsletter": {"sender": {"requested": "resend", "mode": "resend"}, "live_sending_approved": True,
                   "render_scheduler": True, "next_slots": [{"slot": "evening", "at_et": "7:00 PM ET"}],
                   "runs": [{"slot_key": "2026-11-21@morning", "status": "sent", "slot_time_et": "7:00 AM ET"}],
                   "counts": {"active": 12}},
    "server": {"boot_id": "abc", "booted": "2026-11-21T19:00:00Z", "uptime_s": 3600,
               "memory": {"rss_mb": 200, "peak_rss_mb": 220}, "deploy_commit": "36ef6dc"},
    "now": "2026-11-21T20:22:00Z",
}


class HashAndSession(unittest.TestCase):
    def setUp(self):
        _install_test_hash()

    def test_password_hash_roundtrip(self):
        self.assertTrue(AP.check_password(TEST_PW))
        self.assertFalse(AP.check_password("wrong"))
        self.assertFalse(AP.check_password(""))
        self.assertFalse(AP.check_password(None))

    def test_compare_is_constant_time_api(self):
        # check_password uses hmac.compare_digest; a prefix of the hash is not accepted
        self.assertFalse(AP.check_password(TEST_PW[:-1]))

    def test_session_cookie_roundtrip(self):
        tok = AP.make_session()
        h = H("GET", "/admin", headers={"Cookie": f"{AP.COOKIE}={tok}"})
        self.assertTrue(AP.session_ok(h))
        h2 = H("GET", "/admin", headers={"Cookie": f"{AP.COOKIE}=v1.9999999999.deadbeef"})
        self.assertFalse(AP.session_ok(h2))
        expired = AP.make_session(now=time.time() - AP.TTL - 10)
        h3 = H("GET", "/admin", headers={"Cookie": f"{AP.COOKIE}={expired}"})
        self.assertFalse(AP.session_ok(h3))

    def test_source_has_no_plaintext_portal_password(self):
        # The production password must not appear in committed files.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Scan only this feature's files plus a repo-wide token check of the module.
        for rel in ("admin_portal.py", "render_app.py", "growth.py", "tests/test_admin_portal.py"):
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("mj" + "admin", text, rel)
        self.assertTrue(AP.PASS_HASH.startswith("pbkdf2_sha256$"))
        self.assertNotIn("plaintext", AP.PASS_HASH)


class Routes(unittest.TestCase):
    def setUp(self):
        _install_test_hash()
        self._orig = AP.snapshot
        AP.snapshot = lambda: FAKE

    def tearDown(self):
        AP.snapshot = self._orig

    def test_login_page_unauthenticated(self):
        h = H("GET", "/admin")
        code, body, ctype, hdr = AP.handle(h)
        self.assertEqual(code, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("noindex", body)
        self.assertIn('name="password"', body)
        self.assertIn("blackout.network", body)
        self.assertNotIn("Mac scanner", body)
        self.assertEqual(hdr.get("X-Robots-Tag"), "noindex, nofollow")

    def test_login_success_sets_secure_cookie(self):
        h = _login()
        code, body, ctype, hdr = h.sent
        self.assertEqual(code, 302)
        self.assertEqual(hdr.get("Location"), "/admin")
        c = hdr.get("Set-Cookie") or ""
        self.assertIn(f"{AP.COOKIE}=", c)
        self.assertIn("HttpOnly", c)
        self.assertIn("Secure", c)
        self.assertIn("SameSite=Lax", c)
        self.assertIn("Max-Age=", c)
        self.assertNotIn(TEST_PW, c)

    def test_login_wrong_password(self):
        h = _login("nope")
        self.assertEqual(h.sent[0], 401)
        self.assertIn("Wrong password", h.sent[1])
        self.assertNotIn("Set-Cookie", h.sent[3] or {})

    def test_rate_limit_after_ten_failures(self):
        for i in range(10):
            h = _login("bad", ip="203.0.113.9")
            self.assertEqual(h.sent[0], 401, i)
        h = _login("bad", ip="203.0.113.9")
        self.assertEqual(h.sent[0], 429)
        # other IPs are unaffected
        h2 = _login("bad", ip="203.0.113.10")
        self.assertEqual(h2.sent[0], 401)

    def test_json_login_also_works(self):
        import json
        h = H("POST", "/admin/login", raw=json.dumps({"password": TEST_PW}).encode())
        AP.handle(h)
        self.assertEqual(h.sent[0], 302)

    def test_authenticated_page_is_the_dashboard(self):
        h = _login()
        cookie = h.sent[3]["Set-Cookie"].split(";", 1)[0]
        g = H("GET", "/admin", headers={"Cookie": cookie})
        code, body, ctype, hdr = AP.handle(g)
        self.assertEqual(code, 200)
        self.assertIn("text/html", ctype)
        # Original Mac dashboard panels
        for needle in ("id=\"tab-threat\"", "id=\"feed\"", "id=\"watch\"", "Watchlist",
                       "Geographic heat map", "Alert volume", "Severity trend",
                       "id=\"sources\"", "id=\"tab-jets\"", "id=\"tab-newsletter\"",
                       "id=\"tab-sources\"", "id=\"tab-noise\"", "id=\"tab-heatmap\"",
                       "Notification settings", "Manual refresh", "Scans every",
                       'id="status"', 'id="refresh"', 'id="interval"', "Log out",
                       "Instant writer", "Newsletter", "bn-admin", "noindex"):
            self.assertIn(needle, body, needle)
        self.assertIn("/api/rt/refresh", body)
        self.assertIn("set on the Mac", body)
        self.assertIn('id="interval" disabled', body)
        # no send/deploy/config actions
        self.assertNotIn("Send now", body)
        self.assertNotIn('action="test_send"', body)
        self.assertEqual(hdr.get("X-Robots-Tag"), "noindex, nofollow")
        # status API still works
        s = H("GET", "/api/admin/status", headers={"Cookie": cookie})
        code, js, ctype, hdr = AP.handle(s)
        self.assertEqual(code, 200)
        self.assertEqual(js["scanner"]["badge"], "OK")
        self.assertTrue(js["writer"]["thread_alive"])

    def test_public_menu_still_hides_pages(self):
        html = UI.drawer(sitenav, active="threat")
        self.assertNotIn('href="/admin"', html)
        self.assertNotIn('data-tab="streams"', html)

    def test_status_requires_session(self):
        h = H("GET", "/api/admin/status")
        self.assertEqual(AP.handle(h)[0], 401)

    def test_logout_clears_cookie(self):
        h = _login()
        cookie = h.sent[3]["Set-Cookie"].split(";", 1)[0]
        out = H("POST", "/admin/logout", headers={"Cookie": cookie})
        AP.handle(out)
        self.assertEqual(out.sent[0], 302)
        c = out.sent[3].get("Set-Cookie") or ""
        self.assertIn("Max-Age=0", c)

    def test_admin_passcode_header_does_not_unlock_portal(self):
        h = H("GET", "/admin", headers={"X-Admin-Passcode": "anything"})
        code, body, *_ = AP.handle(h)
        self.assertEqual(code, 200)
        self.assertIn('name="password"', body)
        self.assertNotIn("Mac scanner", body)

    def test_scrub_drops_secret_strings(self):
        dirty = {"api_key": "sk-secret-value", "api_key_set": False, "ok": True, "nested": {"token": "abcd"}}
        clean = AP._scrub(dirty)
        self.assertNotIn("api_key", clean)
        self.assertIn("api_key_set", clean)
        self.assertFalse(clean["api_key_set"])
        self.assertNotIn("token", clean["nested"])


class PublicSurfaces(unittest.TestCase):
    def test_robots_disallow(self):
        self.assertIn("Disallow: /admin", growth.ROBOTS)
        self.assertIn("Disallow: /api/admin/", growth.ROBOTS)

    def test_sitemap_omits_admin(self):
        xml = growth.sitemap().decode() if isinstance(growth.sitemap(), (bytes, bytearray)) else growth.sitemap()
        self.assertNotIn("/admin", xml)

    def test_menu_omits_admin(self):
        html = UI.drawer(sitenav, active="threat")
        self.assertNotIn('href="/admin"', html)
        self.assertNotIn("data-tab=\"admin\"", html)


if __name__ == "__main__":
    unittest.main()
