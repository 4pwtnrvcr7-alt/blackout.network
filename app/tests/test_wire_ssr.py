"""/wire greets a visitor with live rows in its HTML (no loader, no hero, no animation). Run: cd app && python3 -m unittest tests.test_wire_ssr -v"""
import json, os, re, sys, time, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import wire_timeline as W

STATIC = os.path.join(os.path.dirname(W.__file__), "wire_timeline_static")
STD = W._pkey(None, None, 100, "", False, None, None, None, None, None, None, None)


def row(i, t, **k):
    d = {"id": "id%03d" % i, "t": t, "h": "Headline %d <b>&</b>" % i, "s": "Dek %d" % i, "k": "weather", "g": "na", "r": 3, "a": False}
    d.update(k); return d


def put(items, age=0.0, nxt=None, end=True):
    W._pstore(STD, {"items": items, "next": nxt, "end": end, "dir": "older", "limit": 100})
    W._PC["t"][STD] = time.time() - age


class Ssr(unittest.TestCase):
    def setUp(self):
        W._reset_caches(); W._SSR.update(src=None, html="", boot="")
        self._sw = W.start_warm; W.start_warm = lambda: None

    def tearDown(self):
        W.start_warm = self._sw; W._reset_caches()

    def test_rows_are_in_the_html(self):
        put([row(1, "2026-11-28T05:10:00Z", r=8), row(2, "2026-11-28T04:00:00Z", **{"do": True}), row(3, "2026-11-20T04:00:00Z", a=True)])
        h = W.page_html()
        self.assertIn('id="tl_ssr"', h)
        self.assertIn("Headline 1 &lt;b&gt;&amp;&lt;/b&gt;", h)             # escaped
        self.assertIn('class="tl-it major"', h)                              # rank 8
        self.assertIn('<b class="tl-ar">Archive</b>', h)
        self.assertIn("Dated by day only", h)
        self.assertEqual(h.count('class="tl-day"'), 3)                       # Nov 28, Nov 27 (11 PM ET) and Nov 20
        self.assertIn("window.BN_TL_BOOT=", h)
        self.assertLess(h.index('id="tl_ssr"'), h.index('id="tl_foot"'))
        for gone in ("tl_ld", "loader.js", "tl-hero", "scan-bg", "/api/wire_tl/pulse"):
            self.assertNotIn(gone, h)

    def test_boot_json_matches_the_api_shape_and_cannot_break_out_of_the_script(self):
        put([row(1, "2026-11-28T05:10:00Z", h="</script><script>alert(1)</script>")], nxt="2026-11-27T00:00:00Z|zz", end=False)
        h = W.page_html()
        m = re.search(r"window\.BN_TL_BOOT=(\{.*?\});</script>", h, re.S)
        self.assertNotIn("</script><script>alert", h)
        j = json.loads(m.group(1))
        self.assertEqual(j["page"]["items"][0]["id"], "id001")
        self.assertEqual(j["page"]["next"], "2026-11-27T00:00:00Z|zz"); self.assertFalse(j["page"]["end"])
        self.assertLess(j["age"], 5000)

    def test_only_the_first_rows_are_embedded_and_the_cursor_continues_from_the_last(self):
        put([row(i, "2026-11-28T05:%02d:00Z" % (59 - i)) for i in range(60)], nxt="X|Y", end=False)
        h = W.page_html()
        j = json.loads(re.search(r"window\.BN_TL_BOOT=(\{.*?\});</script>", h, re.S).group(1))["page"]
        self.assertEqual(len(j["items"]), W._SSR_N)
        last = j["items"][-1]
        self.assertEqual(j["next"], last["t"] + "|" + last["id"]); self.assertFalse(j["end"])
        self.assertEqual(h.count('class="tl-it'), W._SSR_N)

    def test_never_builds_or_waits_and_never_shows_a_stale_copy(self):
        calls = []
        real = W._page_build; W._page_build = lambda *a, **k: calls.append(a) or real(*a, **k)
        try:
            h = W.page_html()                                               # nothing in memory: status readout, client loads
            self.assertNotIn("tl_ssr", h); self.assertNotIn("BN_TL_BOOT", h)
            self.assertIn('id="tl_boot"', h); self.assertIn("BN_TL_FIRST", h)
            put([row(1, "2026-11-28T05:10:00Z")], age=W._SSR_MAX_AGE + 5)   # too old: not shown
            self.assertNotIn("tl_ssr", W.page_html())
            put([row(1, "2026-11-28T05:10:00Z")], age=45)                   # background-refreshed copy: shown
            self.assertIn("tl_ssr", W.page_html())
        finally:
            W._page_build = real
        self.assertEqual(calls, [])

    def test_fragment_is_reused_until_the_page_changes(self):
        put([row(1, "2026-11-28T05:10:00Z")])
        W.page_html(); a = W._SSR["html"]; src = W._SSR["src"]
        W.page_html(); self.assertIs(W._SSR["src"], src)
        put([row(2, "2026-11-28T05:11:00Z")]); W.page_html()
        self.assertIsNot(W._SSR["src"], src); self.assertNotEqual(W._SSR["html"], a)


    def test_ssr_path_omits_the_status_and_does_not_read_the_scan(self):
        put([row(1, "2026-11-28T05:10:00Z")])
        calls = []
        real = W.scan_stats
        W.scan_stats = lambda: calls.append(1) or real()
        try:
            h = W.page_html()
        finally:
            W.scan_stats = real
        self.assertIn("tl_ssr", h)
        self.assertNotIn('id="tl_boot"', h)
        self.assertNotIn("BN_TL_FIRST", h)
        self.assertNotIn("/api/wire_tl/scan", h)
        self.assertEqual(calls, [])

    def test_cold_status_shows_real_scan_figures_or_dashes(self):
        real = W.scan_stats
        W.scan_stats = lambda: {"last_scan": "2026-11-28T05:04:00Z", "sources": 1343, "ok_sources": 1287,
                                "failed_sources": 56, "fetched": 4102, "new_items": 12, "in_review": 18}
        try:
            h = W.page_html()
            self.assertIn('id="tl_boot"', h)
            self.assertIn("The Wire", h)
            self.assertIn("1,287 of 1,343", h)
            self.assertIn("56 failed", h)
            self.assertIn("4,102", h)
            self.assertIn("12:04 AM ET", h)
            self.assertIn("BN_TL_FIRST", h)
            self.assertIn('class="tb-retry"', h)
            self.assertNotIn("tl_ssr", h)
            W.scan_stats = lambda: {"last_scan": None, "sources": 0, "ok_sources": 0, "failed_sources": 0,
                                    "fetched": 0, "new_items": 0, "in_review": 0}
            h = W.page_html()
            self.assertIn("&mdash;", h)
            self.assertNotIn("0 of 0", h)
        finally:
            W.scan_stats = real

    def test_scan_endpoint_is_the_real_scan_stats(self):
        real = W.scan_stats
        W.scan_stats = lambda: {"last_scan": "2026-11-28T05:04:00Z", "sources": 2, "ok_sources": 2,
                                "failed_sources": 0, "fetched": 9, "new_items": 1, "in_review": 0}
        try:
            code, body, *rest = W.handle_get("/api/wire_tl/scan", {})
        finally:
            W.scan_stats = real
        self.assertEqual(code, 200)
        self.assertEqual(body["fetched"], 9)
        self.assertEqual(body["sources"], 2)

    def test_empty_page_renders_no_block(self):
        put([])
        self.assertNotIn("tl_ssr", W.page_html())


class Client(unittest.TestCase):
    js = open(os.path.join(STATIC, "app.js")).read()
    css = open(os.path.join(STATIC, "app.css")).read()

    def test_no_loader_left(self):
        for gone in ("loaderGate", "tlReady", "tl-ld", "BN_TL_READY"):
            self.assertNotIn(gone, self.js)
        self.assertNotIn("#tl_ld", self.css)
        self.assertFalse(os.path.exists(os.path.join(STATIC, "loader.js")))
        self.assertNotIn("loader.js", W.FILES)

    def test_boot_adopts_the_embedded_page_and_fetches_updates_in_place(self):
        self.assertIn("W.BN_TL_BOOT", self.js)
        body = self.js[self.js.index("function adoptBoot"):self.js.index("function loadNewer")]
        self.assertIn('add(j.items,"bot")', body)        # add() marks every adopted row as already shown, so none can be New
        self.assertIn("pollNewer(false)", body)
        self.assertNotIn("NEW[", body)

    def test_ssr_rows_use_flow_layout_with_the_same_row_css(self):
        self.assertRegex(self.css, r"\.tl-ssr \.tl-it,\.tl-ssr \.tl-day\{position:relative")
        self.assertNotRegex(self.css, r"animation:[^;}]*\bld")

    def test_cold_status_is_only_started_when_ssr_is_missing(self):
        self.assertIn("function startBootStatus", self.js)
        self.assertIn("BN_TL_FIRST", self.js)
        self.assertIn("startBootStatus();loadOlder()", self.js)
        body = self.js[self.js.index("function adoptBoot"):self.js.index("function dropSsr")]
        self.assertNotIn("startBootStatus", body)

    def test_retry_is_a_pill_and_the_status_has_no_yellow(self):
        self.assertRegex(self.css, r"\.tb-retry\{[^}]*border-radius:999px")
        for blob in (self.css, self.js):
            self.assertNotRegex(blob, r"yellow|#ff0\\b|#FF0|#fc0|#FC0|gold")



if __name__ == "__main__":
    unittest.main()
