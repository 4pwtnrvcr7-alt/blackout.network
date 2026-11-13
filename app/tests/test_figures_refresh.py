"""Key Figures refresh: bypass 10-min / Google News caches, newest headlines first,
and the top-bar Refresh data button re-fetches on /#figures.
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_figures_refresh -v
"""
import os, sys, time, unittest
from unittest import mock

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

import figures


def reset_cache():
    figures._C["t"] = 0
    figures._C["v"] = None


class QueryFlag(unittest.TestCase):
    def test_parse_qs_list_and_plain_string(self):
        self.assertTrue(figures._qflag({"refresh": ["1"]}, "refresh", "force"))
        self.assertTrue(figures._qflag({"force": "true"}, "refresh", "force"))
        self.assertTrue(figures._qflag({"refresh": "YES"}, "refresh"))
        self.assertFalse(figures._qflag({"refresh": ["0"]}, "refresh"))
        self.assertFalse(figures._qflag({}, "refresh"))
        self.assertFalse(figures._qflag(None, "refresh"))


class CacheAndForce(unittest.TestCase):
    def setUp(self):
        reset_cache()

    def tearDown(self):
        reset_cache()

    def test_summary_returns_cache_within_10_min_unless_forced(self):
        figures._C.update(t=time.time(), v={"updated": "old", "people": []})
        with mock.patch.object(figures, "build", return_value={"updated": "new", "people": []}) as b:
            self.assertEqual(figures.summary()["updated"], "old")
            b.assert_not_called()
            out = figures.summary(force=True)
            self.assertEqual(out["updated"], "new")
            b.assert_called_once_with(force=True)
            self.assertEqual(figures._C["v"]["updated"], "new")

    def test_expired_cache_rebuilds(self):
        figures._C.update(t=time.time() - 601, v={"updated": "old", "people": []})
        with mock.patch.object(figures, "build", return_value={"updated": "fresh", "people": []}) as b:
            self.assertEqual(figures.summary()["updated"], "fresh")
            b.assert_called_once_with(force=False)

    def test_api_refresh_query_forces_rebuild(self):
        figures._C.update(t=time.time(), v={"updated": "old", "people": []})
        with mock.patch.object(figures, "build", return_value={"updated": "forced", "people": []}):
            code, body = figures.handle_get("/api/figures", {"refresh": ["1"]})
            self.assertEqual(code, 200)
            self.assertEqual(body["updated"], "forced")
        reset_cache()
        figures._C.update(t=time.time(), v={"updated": "old", "people": []})
        with mock.patch.object(figures, "build", return_value={"updated": "forced", "people": []}):
            code, body = figures.handle_get("/api/figures", {})
            self.assertEqual(code, 200)
            self.assertEqual(body["updated"], "old")

    def test_gnews_passes_force_through_to_cached(self):
        with mock.patch.object(figures.B, "cached", return_value={"items": []}) as cached:
            figures._gnews("Donald Trump", force=True)
            args, kwargs = cached.call_args
            self.assertEqual(args[1], "gn:Donald Trump")
            self.assertTrue(kwargs.get("force") or (len(args) > 4 and args[4] is True))


class HeadlineOrder(unittest.TestCase):
    def test_newest_event_time_is_listed_first(self):
        # Live streams keep a fresh `updated` but an old event time — those used to appear first.
        hits = {"trump": [
            {"title": "old live", "time": "2026-11-08T01:00:00Z", "updated": "2026-11-13T18:19:55Z", "via": "scanner", "cid": "a", "list": "The Wire"},
            {"title": "newer story", "time": "2026-11-13T11:00:00Z", "updated": "2026-11-13T11:05:00Z", "via": "scanner", "cid": "b", "list": "The Wire"},
            {"title": "mid", "time": "2026-11-10T01:41:13Z", "updated": "2026-11-13T17:00:00Z", "via": "scanner", "cid": "c", "list": "The Wire"},
        ]}
        counts = {"trump": 3}
        gn = [
            {"title": "gn later", "time": "2026-11-13T17:00:00Z", "via": "Google News", "url": "https://example.com/x", "source": "ex"},
        ]
        with mock.patch.object(figures, "_alerts", return_value=(hits, counts, {"trump": {}}, None)), \
             mock.patch.object(figures, "_gnews", return_value=gn), \
             mock.patch.object(figures, "_photo", return_value=None):
            d = figures.build(force=True)
        trump = next(p for p in d["people"] if p["key"] == "trump")
        titles = [h["title"] for h in trump["headlines"]]
        self.assertEqual(titles[0], "newer story")
        self.assertLess(titles.index("newer story"), titles.index("mid"))
        self.assertLess(titles.index("mid"), titles.index("old live"))
        # Google News items are merged and also sorted by event time (17:00 is after 11:00).
        self.assertEqual(titles[0], "newer story")
        if "gn later" in titles:
            self.assertLess(titles.index("newer story"), titles.index("gn later"))
            self.assertLess(titles.index("gn later"), titles.index("mid"))


class ClientHook(unittest.TestCase):
    def test_figures_js_registers_refresh_hook_and_cache_busts(self):
        with open(os.path.join(APP, "figures_static", "app.js"), encoding="utf-8") as f: js = f.read()
        self.assertIn("window.bnRefreshPage", js)
        self.assertIn("refresh=1", js)
        self.assertIn("cache:\"no-store\"", js)
        self.assertIn("kf-spin", js)
        self.assertIn("etHM", js)
        self.assertIn("Updated ", js)
        with open(os.path.join(APP, "figures_static", "app.css"), encoding="utf-8") as f: css = f.read()
        self.assertIn("kf-spin", css)
        self.assertIn("kf-stamp", css)
        self.assertIn("16px", css)
