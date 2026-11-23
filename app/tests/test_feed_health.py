"""Feed freshness for The Wire and the homepage Updated line (Nov 23 2026).

Offline: collect() is a pure function. No database, no network, no secrets.
"""
import os, sys, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import feed_health as FH

SCAN_ISO = "2026-11-23T16:31:08Z"  # 11:31:08 AM ET


def ts(iso):
    return FH._ts(iso)


class FeedHealth(unittest.TestCase):
    def setUp(self):
        self.scan = ts(SCAN_ISO)
        self.assertIsNotNone(self.scan)
        # Confirm the public copy: 11:31 AM ET
        self.assertEqual(FH._et(self.scan), "11:31 AM ET")

    def test_notice_text(self):
        self.assertEqual(FH.notice_text("11:31 AM ET"), "Live updates delayed since 11:31 AM ET")
        self.assertEqual(FH.notice_text(""), "Live updates delayed")

    def test_fresh_scan_during_boot_grace_with_no_push_is_not_stale(self):
        now = self.scan + 5 * 60
        r = FH.collect(now=now, booted=now - 30, last_scan=SCAN_ISO, last_push=None, mac_connected=False, grace_s=300)
        self.assertFalse(r["stale"])
        self.assertFalse(r["severe"])
        self.assertEqual(r["notice"], "")
        self.assertTrue(r["boot_grace"])
        self.assertEqual(r["last_scan"], SCAN_ISO)
        self.assertEqual(r["last_scan_et"], "11:31 AM ET")
        self.assertIsNone(r["last_push"])

    def test_fresh_scan_after_grace_with_no_push_is_not_stale(self):
        now = self.scan + 8 * 60
        r = FH.collect(now=now, booted=now - 600, last_scan=SCAN_ISO, last_push=None, mac_connected=False, grace_s=300)
        self.assertFalse(r["stale"])
        self.assertFalse(r["boot_grace"])
        self.assertEqual(r["notice"], "")

    def test_scan_older_than_20_minutes_is_stale_but_not_severe(self):
        now = self.scan + 25 * 60
        r = FH.collect(now=now, booted=now - 600, last_scan=SCAN_ISO, last_push=None, mac_connected=False, grace_s=300)
        self.assertTrue(r["stale"])
        self.assertFalse(r["severe"])
        self.assertEqual(r["notice"], "Live updates delayed since 11:31 AM ET")
        self.assertEqual(r["since"], SCAN_ISO)
        self.assertEqual(r["since_et"], "11:31 AM ET")
        self.assertEqual(r["last_scan_age_s"], 25 * 60)
        self.assertFalse(r["mac_connected"])

    def test_already_stale_scan_still_shows_during_boot_grace(self):
        # Honest: the feed really is stale. Grace only hides a missing last_push.
        now = self.scan + 40 * 60
        r = FH.collect(now=now, booted=now - 20, last_scan=SCAN_ISO, last_push=None, mac_connected=False, grace_s=300)
        self.assertTrue(r["stale"])
        self.assertTrue(r["boot_grace"])
        self.assertEqual(r["notice"], "Live updates delayed since 11:31 AM ET")

    def test_stale_more_than_two_hours_is_severe(self):
        now = self.scan + 2 * 3600 + 60
        r = FH.collect(now=now, booted=now - 600, last_scan=SCAN_ISO, last_push=None, grace_s=300)
        self.assertTrue(r["stale"])
        self.assertTrue(r["severe"])
        self.assertEqual(r["notice"], "Live updates delayed since 11:31 AM ET")

    def test_fresh_scan_wins_over_an_old_push(self):
        now = self.scan + 8 * 60
        old_push = self.scan - 30 * 60
        r = FH.collect(now=now, booted=now - 600, last_scan=SCAN_ISO, last_push=old_push, mac_connected=True, grace_s=300)
        self.assertFalse(r["stale"])
        self.assertTrue(r["mac_connected"])

    def test_no_scan_and_no_push_during_grace_is_not_stale(self):
        now = 1_795_455_000
        r = FH.collect(now=now, booted=now - 10, last_scan=None, last_push=None, grace_s=300)
        self.assertFalse(r["stale"])
        self.assertTrue(r["boot_grace"])
        self.assertEqual(r["notice"], "")

    def test_no_scan_and_no_push_after_grace_is_stale(self):
        now = 1_795_455_000
        r = FH.collect(now=now, booted=now - 600, last_scan=None, last_push=None, grace_s=300)
        self.assertTrue(r["stale"])
        self.assertFalse(r["boot_grace"])
        self.assertEqual(r["notice"], "Live updates delayed")
        self.assertIsNone(r["since"])

    def test_recovered_when_a_new_scan_arrives(self):
        now = self.scan + 40 * 60
        stale = FH.collect(now=now, booted=now - 600, last_scan=SCAN_ISO, grace_s=300)
        self.assertTrue(stale["stale"])
        fresh_iso = "2026-11-23T17:20:00Z"
        live = FH.collect(now=ts(fresh_iso) + 60, booted=now - 600, last_scan=fresh_iso, last_push=ts(fresh_iso), mac_connected=True, grace_s=300)
        self.assertFalse(live["stale"])
        self.assertEqual(live["notice"], "")

    def test_handle_get_route(self):
        code, body = FH.handle_get("/api/signal/feed-health", {})
        self.assertEqual(code, 200)
        self.assertIn("stale", body)
        self.assertIn("mac_connected", body)
        self.assertIn("since", body)
        self.assertIn("notice", body)
        code, body = FH.handle_get("/api/feed-health", {})
        self.assertEqual(code, 200)
        self.assertEqual(FH.handle_get("/api/signal/heat", {})[0], 404)


if __name__ == "__main__":
    unittest.main()
