import io, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import share_card as S

SOLAR = {"ok": True, "planets": [{"id": "earth", "pos": [1, 0, 0], "v_km_s": 29.8}, {"id": "jupiter", "pos": [5.2, 0, 0], "v_km_s": 13.0}],
         "craft": [{"id": "voyager1", "name": "Voyager 1", "operator": "NASA / JPL", "launch": "1977-09-05", "status": "Operational. In interstellar space.", "earth_au": 168.0, "v_km_s": 16.9}]}
NET = {"nets": [{"id": "cox", "name": "Cox", "level": 2, "status": "Outage signal on 1 of 1 network", "incidents": [{"t": "routing drop"}], "uptime": 97.8, "days": [0] * 28 + [2, 2], "group": "isp"},
                {"id": "spectrum", "name": "Spectrum", "level": 0, "status": "No outage signal", "incidents": [], "uptime": 99.8, "days": [0] * 30, "group": "isp"}],
       "groups": [{"id": "isp", "name": "Internet providers"}], "cloud": [{"p": "aws", "name": "US East (N. Virginia)", "lon": -77.5, "lat": 39.0, "level": 1}], "outages": {"countries": []}}
LAUNCH = {"launches": [{"id": "abc-1", "name": "Falcon 9 Block 5 | Starlink Group 12-3", "vehicle": "Falcon 9 Block 5", "mission": "Starlink Group 12-3", "net": "2099-01-01T12:00:00Z", "status_name": "Go for Launch",
                        "pad": "Space Launch Complex 40", "location": "Cape Canaveral SFS, FL, USA", "pad_lat": 28.56, "pad_lon": -80.58, "orbit": "LEO", "provider": "SpaceX", "ascent": [[-80.58, 28.56, 0, 0], [-79.0, 29.0, 1000, 10]]}]}


class T(unittest.TestCase):
    def setUp(self):
        S.HOOKS.update(solar=lambda: SOLAR, net=lambda: NET, launches=lambda: LAUNCH)

    def tearDown(self):
        S.HOOKS.clear()

    def png(self, kind, ident):
        b = S.png_for(kind, ident)
        from PIL import Image
        im = Image.open(io.BytesIO(b))
        self.assertEqual(im.size, (1200, 675))
        return b

    def test_each_kind_renders_distinct(self):
        items = [("planet", "jupiter"), ("planet", "moon"), ("craft", "voyager1"), ("sat", "starlink"), ("launch", "abc-1"), ("net", "cox"), ("net", "spectrum"),
                 ("cloud", "aws~us-east-n-virginia"), ("page", "weather"), ("site", "moon~apollo11")]
        seen = set()
        for k, i in items:
            b = self.png(k, i)
            seen.add(hash(b))
        self.assertEqual(len(seen), len(items))

    def test_text_and_tags(self):
        for k, i in [("planet", "jupiter"), ("craft", "voyager1"), ("launch", "abc-1"), ("net", "cox"), ("cloud", "aws~us-east-n-virginia"), ("page", "weather")]:
            it = S.resolve(k, i)
            href, text, tags, url = S.intent(it)
            self.assertTrue(3 <= len(tags) <= 5, (k, tags))
            from x_share import weighted_len
            self.assertLessEqual(weighted_len(text, url), 280, (k, text))
            self.assertTrue(href.startswith("https://x.com/intent/post?text="))
            self.assertTrue(all(t.startswith("#") for t in tags))

    def test_no_yellow_accents(self):
        for c in (S.SPACE_C, S.LAUNCH_C, S.WX_C, S.NET_C, S.GREEN, S.RED):
            self.assertFalse(c[0] > 200 and c[1] > 170 and c[2] < 90)

    def test_adaptor(self):
        it = S.item_for_share("network", "cox", {})
        self.assertEqual(it["title"], "Cox")
        it = S.item_for_share("cloud", "aws-USEastN.Virginia", {})
        self.assertIn("AWS", it["title"])
        it = S.item_for_share("weather", "wx-X", {"n": ["Sanford weather"], "d": ["Clear 72F"]})
        self.assertEqual(it["art"][0], "type")
        self.assertIsNone(S.item_for_share("weather", "wx-X", {}))
        code, body, ctype = S.og_share("/og/share/network/cox.png", {})
        self.assertEqual((code, ctype), (200, "image/png"))

    def test_launches_bytes_payload(self):
        S.HOOKS["launches"] = lambda: json.dumps(LAUNCH).encode()   # netlaunch.launches_cached() returns JSON bytes
        it = S.resolve("launch", "abc-1")
        self.assertTrue(it and it["title"].startswith("Starlink"))
        self.png("launch", "abc-1")

    def test_unknown_is_404(self):
        self.assertIsNone(S.png_for("planet", "pluto"))
        self.assertEqual(S.handle_get("/og/share/zzz/none.png")[0], 404)


if __name__ == "__main__":
    unittest.main()


class QuickFallback(unittest.TestCase):
    def test_png_for_story_fast_fallback_does_not_raise_and_is_unique(self):
        import og, share_card
        old = share_card.story_png_fast
        share_card.story_png_fast = lambda cid, budget=1.0: None
        try:
            import story
            o = story.load
            story.load = lambda cid: ({"title": "Theriva Biologics halted on NYSE American", "rank": 7}, [])
            try:
                a = og.png_for_story_fast("a" * 16)
                self.assertGreater(len(a), 5000)
                from PIL import Image
                import io
                im = Image.open(io.BytesIO(a))
                self.assertEqual(im.size, (1200, 675))  # designed map card, never the 1200x630 earth fallback
                self.assertEqual(a, og.png_for_story_fast("a" * 16))
                code, body, ct = og.handle_get("/og/wire/" + "a" * 16 + ".png")
                self.assertEqual(body, a)
            finally:
                story.load = o
        finally:
            share_card.story_png_fast = old


    def test_story_item_does_not_call_api_state(self):
        called = {"n": 0}
        import theme, story
        old_srv, old_load = theme._srv, story.load
        theme._srv = lambda: type("S", (), {"api_state": staticmethod(lambda: called.__setitem__("n", called["n"] + 1) or {})})()
        story.load = lambda cid: ({"title": "Scott Bessent Unleashes Fresh Iran Sanctions", "brief": "WHAT: sanctions",
                                   "rank": 2, "location": "Iran", "category": "politics", "lat": None, "lon": None,
                                   "families": "a,b", "watchlist": 0, "hidden": 0}, [])
        try:
            got = S._story_item("e2ca47e325c5b8e1")
            self.assertIsNotNone(got)
            self.assertEqual(called["n"], 0)
            self.assertIn("Bessent", got[0]["title"])
            card = S._r_story("e2ca47e325c5b8e1")
            self.assertIsNotNone(card)
            self.assertEqual(called["n"], 0)
        finally:
            theme._srv = old_srv
            story.load = old_load


class CrawlerFirstFetch(unittest.TestCase):
    """X cards (Nov 25 2026): a story is not public until its card is baked, and a crawler never waits on the board."""

    def test_allow_holds_story_until_card_baked(self):
        import story_writer as SW, share_card as S
        from unittest import mock
        S._BAKED.discard("abcdabcdabcdabcd")
        with mock.patch.object(SW, "gate_on", return_value=True), \
             mock.patch.object(SW, "_is_needs_paid", return_value=False), \
             mock.patch.object(SW, "has_writeup", return_value=True), \
             mock.patch.object(S, "card_baked", return_value=False), \
             mock.patch.object(S, "bake_card") as bake:
            self.assertFalse(SW.allow("abcdabcdabcdabcd"))
            bake.assert_called_once_with("abcdabcdabcdabcd")
        with mock.patch.object(SW, "gate_on", return_value=True), \
             mock.patch.object(SW, "_is_needs_paid", return_value=False), \
             mock.patch.object(SW, "has_writeup", return_value=True), \
             mock.patch.object(S, "card_baked", return_value=True):
            self.assertTrue(SW.allow("abcdabcdabcdabcd"))

    def test_crawler_gets_og_stub_without_waiting_for_the_board(self):
        import wire_v2 as W
        from unittest import mock
        from concurrent.futures import Future
        never = Future()   # a board build that never finishes
        W._C.pop("abcdabcdabcdabcd", None); W._INFL.pop("abcdabcdabcdabcd", None); W._NEG.pop("abcdabcdabcdabcd", None)
        stub = '<meta name="twitter:card" content="summary_large_image">'
        class P:
            def submit(self, *a, **k): return never
        with mock.patch.object(W, "_pool", return_value=P()), mock.patch.object(W, "_light_story", return_value=stub):
            import time
            t0 = time.time()
            code, body, _ = W.handle("/wire/abcdabcdabcdabcd", {}, headers={"User-Agent": "Twitterbot/1.0"})
            self.assertLess(time.time() - t0, 0.5)
            self.assertEqual(code, 200)
            self.assertIn("twitter:card", body)
        W._INFL.pop("abcdabcdabcdabcd", None)
