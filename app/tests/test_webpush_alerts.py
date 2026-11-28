"""Web Push repair: slim /api/alerts/feed and Alerts panel subscription refresh (Nov 27 2026)."""
import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as fh:
        return fh.read()


class TestAlertsJsRepair(unittest.TestCase):
    def setUp(self):
        self.js = _read("static", "alerts", "alerts.js")

    def test_testpush_refreshes_subscription_first(self):
        self.assertIn("function refreshSubscription", self.js)
        self.assertIn("/api/alerts/resubscribe", self.js)
        # Send a test alert must recreate the endpoint, then request the test push
        i = self.js.find("function testPush")
        self.assertGreater(i, 0)
        chunk = self.js[i:i + 1800]
        self.assertIn("refreshSubscription", chunk)
        self.assertIn("/api/alerts/testpush", chunk)

    def test_restore_missing_sub_not_on_ios_safari_tab(self):
        self.assertIn("function restoreMissingSub", self.js)
        self.assertIn("E.ios && !E.standalone", self.js[self.js.find("function restoreMissingSub"):self.js.find("function restoreMissingSub") + 600])
        self.assertIn("restoreMissingSub().then", self.js)

    def test_no_page_load_subscribe_when_sub_exists(self):
        # Don't POST /api/alerts/subscribe on every load (10 writes/IP/hour cap)
        fn = self.js[self.js.find("function restoreMissingSub"):self.js.find("function init")]
        self.assertIn("if (sub) return;", fn)

    def test_no_peer_to_peer_and_no_emoji(self):
        self.assertNotIn("peer-to-peer", self.js.lower())
        self.assertNotIn("peer to peer", self.js.lower())
        # no emoji codepoints in the new copy
        for ch in self.js:
            o = ord(ch)
            self.assertFalse(0x1F300 <= o <= 0x1FAFF, f"emoji U+{o:X}")

    def test_sw_root_scope_and_shows_notification(self):
        sw = _read("static", "alerts", "sw.js")
        self.assertIn("showNotification", sw)
        self.assertIn("pushsubscriptionchange", sw)
        self.assertNotIn('addEventListener("fetch"', sw)
        self.assertIn("no fetch handler", sw.lower())


class TestAlertsFeed(unittest.TestCase):
    def test_handle_get_routes_feed(self):
        import webpush
        self.assertTrue(hasattr(webpush, "alerts_feed"))
        src = _read("webpush.py")
        self.assertIn('if path == "/api/alerts/feed"', src)

    def test_feed_is_slim_and_skips_hidden_watchlist(self):
        import webpush
        rows = [
            {"cluster_id": "a" * 16, "title": "Bank failure in Indiana", "category": "financial", "location": "Indiana",
             "rank": 8, "score": 90, "eff_families": 5, "high_at": "2026-11-28T03:00:00Z", "updated": "2026-11-28T03:01:00Z",
             "first_seen": "2026-11-28T02:00:00Z", "watchlist": 0, "published": True, "families": [], "links": []},
            {"cluster_id": "b" * 16, "title": "hidden", "category": "other", "location": "", "rank": 7, "score": 80,
             "eff_families": 3, "high_at": "2026-11-28T03:00:00Z", "updated": "2026-11-28T03:01:00Z",
             "first_seen": "2026-11-28T02:00:00Z", "watchlist": 0, "published": True, "hidden": True},
            {"cluster_id": "c" * 16, "title": "watch", "category": "other", "location": "", "rank": 7, "score": 80,
             "eff_families": 3, "high_at": "2026-11-28T03:00:00Z", "updated": "2026-11-28T03:01:00Z",
             "first_seen": "2026-11-28T02:00:00Z", "watchlist": 1, "published": True},
        ]
        fake = mock.Mock()
        fake.scanner.now.return_value = mock.Mock()
        fake.scanner.iso.return_value = "2026-11-28T04:00:00Z"
        fake.et_days.et_window_start.return_value = mock.Mock()
        fake.q.return_value = rows
        fake.clusters_out.side_effect = lambda rs: rs
        with mock.patch.dict(sys.modules, {"server": fake}):
            out = webpush.alerts_feed()
        self.assertEqual([r["cluster_id"] for r in out["main"]], ["a" * 16])
        self.assertEqual(set(out["main"][0].keys()), set(webpush.FEED_KEYS))
        self.assertNotIn("families", out["main"][0])
        self.assertNotIn("links", out["main"][0])
        self.assertNotIn("endpoint", out)
        self.assertNotIn("vapid", str(out).lower())
        self.assertEqual(out["generated"], "2026-11-28T04:00:00Z")


if __name__ == "__main__":
    unittest.main()
