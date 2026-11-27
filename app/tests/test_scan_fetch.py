"""Fetch-phase concurrency, timeouts, ETag cache, and slow-source partition.

Does not run a live scan or touch scoring. Run:
  cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_scan_fetch -v
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scanner as S
import wire_timeline as WT


class PoolFetch(unittest.TestCase):
    def test_concurrent_wall_time_is_max_not_sum(self):
        def _fn_factory(delay):
            def fn():
                time.sleep(delay)
                return [{"id": delay}], {}
            fn.__name__ = "f_fast"
            return fn
        pairs = [(f"s{i}", "http://example.test/%d" % i, _fn_factory(0.35)) for i in range(4)]
        t0 = time.monotonic()
        out = S._pool_fetch(pairs, workers=4)
        elapsed = time.monotonic() - t0
        self.assertEqual(len(out), 4)
        self.assertTrue(all(r["ok"] for r in out))
        self.assertLess(elapsed, 1.0, "sequential would be ~1.4s; got %.2fs" % elapsed)

    def test_partition_puts_gdelt_and_telegram_on_the_slow_loop(self):
        def f_usgs():
            return []
        def f_gdelt():
            return []
        def f_telegram():
            return []
        def f_nws():
            return []
        src = [
            ("USGS", "http://u", f_usgs),
            ("NWS", "http://n", f_nws),
            ("GDELT DOC 2.0", "http://g", f_gdelt),
            ("Telegram public previews", "http://t", f_telegram),
        ]
        fast, slow = S._partition_sources(src)
        self.assertEqual([n for n, _, _ in fast], ["USGS", "NWS"])
        self.assertEqual([n for n, _, _ in slow], ["GDELT DOC 2.0", "Telegram public previews"])


class GetCache(unittest.TestCase):
    def setUp(self):
        S._HTTP_CACHE.clear()

    def test_304_returns_cached_body(self):
        S._HTTP_CACHE["http://x"] = {"etag": '"abc"', "last_mod": "", "body": b'{"ok":1}', "headers": {"ETag": '"abc"'}}
        fake = mock.Mock()
        fake.status_code = 304
        fake.headers = {"ETag": '"abc"'}
        fake.content = b""
        with mock.patch("scanner.requests.get", return_value=fake) as g:
            r = S.get("http://x")
        self.assertEqual(r.json(), {"ok": 1})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(g.called)
        headers = g.call_args.kwargs.get("headers") or g.call_args[1].get("headers")
        self.assertEqual(headers.get("If-None-Match"), '"abc"')

    def test_default_timeout_is_tight(self):
        self.assertLessEqual(S.FETCH_TIMEOUT, 10)
        fake = mock.Mock()
        fake.status_code = 200
        fake.headers = {}
        fake.content = b"x"
        fake.raise_for_status = lambda: None
        with mock.patch("scanner.requests.get", return_value=fake) as g:
            S.get("http://y")
        self.assertEqual(g.call_args.kwargs.get("timeout") or g.call_args[1].get("timeout"), S.FETCH_TIMEOUT)


class ValidatorHoldsList(unittest.TestCase):
    def test_lists_tag_holds_with_headlines(self):
        old = dict(WT._VR)
        try:
            WT._VR.clear()
            WT._VR["aaa"] = {"ok": False, "why": ["tags"], "h": "Witkoff meets Putin in Moscow", "k": "other", "loc": ""}
            WT._VR["bbb"] = {"ok": True, "why": [], "h": "public already", "k": "quake", "loc": ""}
            WT._VR["ccc"] = {"ok": False, "why": ["thin-headline"], "h": "Update", "k": "other", "loc": ""}
            out = WT.qa_endpoint({"validator_holds": True, "reason": "tags"})
            ids = [r["id"] for r in out["validator_holds"]]
            self.assertIn("aaa", ids)
            self.assertNotIn("bbb", ids)
            self.assertNotIn("ccc", ids)
            self.assertEqual(out["validator_holds"][0]["h"], "Witkoff meets Putin in Moscow")
        finally:
            WT._VR.clear(); WT._VR.update(old)


if __name__ == "__main__":
    unittest.main()
