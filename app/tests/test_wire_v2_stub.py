import os, time, unittest
os.environ["BN_XTAGS"] = "0"

import wire_v2 as W
import og

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1"
CID = "a" * 16
PATH = "/wire/" + CID


class NoStubForHumans(unittest.TestCase):
    def setUp(self):
        W.ON = True
        W._C.clear(); W._NEG.clear(); W._INFL.clear()
        self._srv = __import__("theme")._srv
        __import__("theme")._srv = lambda: type("S", (), {"api_state": staticmethod(lambda: time.sleep(8) or {})})()
        self._rs = getattr(W, "render_story", None)
        W.render_story = lambda st, cid: "<html>FULL BOARD</html>"

    def tearDown(self):
        __import__("theme")._srv = self._srv
        if self._rs is not None:
            W.render_story = self._rs
        W._C.clear(); W._NEG.clear(); W._INFL.clear()

    def test_iphone_safari_is_not_a_crawler(self):
        self.assertFalse(og.is_crawler(IPHONE))
        self.assertTrue(og.is_crawler("Twitterbot/1.0"))
        self.assertTrue(og.is_crawler("facebookexternalhit/1.1"))

    def test_human_returns_none_immediately_never_stub(self):
        called = {"n": 0}
        def boom():
            called["n"] += 1
            time.sleep(8)
            return {}
        __import__("theme")._srv = lambda: type("S", (), {"api_state": staticmethod(boom)})()
        t = time.time()
        r = W.handle(PATH, headers={"user-agent": IPHONE})
        self.assertIsNone(r)
        self.assertEqual(called["n"], 0)  # must not start api_state on the human path
        self.assertLess(time.time() - t, 0.3)

    def test_no_ua_treated_as_human(self):
        t = time.time()
        self.assertIsNone(W.handle(PATH))
        self.assertLess(time.time() - t, 0.3)

    def test_crawler_gets_stub_with_og_and_hard_fallback(self):
        import story
        old = story.load
        story.load = lambda cid: ({"title": "Riyadh tower fire", "rank": 7, "brief": "WHAT: A fire."}, [])
        try:
            t = time.time()
            r = W.handle(PATH, headers={"user-agent": "Twitterbot/1.0"})
            dt = time.time() - t
            self.assertIsNotNone(r)
            self.assertEqual(r[0], 200)
            body = r[1]
            self.assertIn("og:image", body)
            self.assertIn("Loading the full story", body)
            self.assertIn(f"/wire/{CID}?full=1", body)
            self.assertIn("content=\"3;url=", body)
            self.assertLess(dt, W._BUDGET + 1.0)
        finally:
            story.load = old

    def test_full_query_returns_none_even_for_crawler(self):
        t = time.time()
        r = W.handle(PATH, qs={"full": ["1"]}, headers={"user-agent": "Twitterbot/1.0"})
        self.assertIsNone(r)
        self.assertLess(time.time() - t, 0.3)

    def test_cached_board_page_served_to_human(self):
        W._C[CID] = (time.time(), "<html>CACHED FULL</html>")
        r = W.handle(PATH, headers={"user-agent": IPHONE})
        self.assertEqual(r[1], "<html>CACHED FULL</html>")


class CardAndShare(unittest.TestCase):
    def test_og_image_and_twitter_image_have_version_buster(self):
        cid = "e2ca47e325c5b8e1"
        html = og.tags(title="Bessent Iran sanctions", desc="d", url="https://blackout.network/wire/"+cid,
                       story_id=cid, rank=7, og_type="article")
        self.assertIn("twitter:image", html)
        self.assertIn("og:image", html)
        self.assertIn("/og/wire/%s.png?v=" % cid, html)
        self.assertIn("?v=17", html)
        self.assertNotIn("?v=5-", html)

    def test_share_url_has_s_param(self):
        import x_share as X
        it = {"cluster_id": "e2ca47e325c5b8e1", "title": "Scott Bessent Unleashes Fresh Iran Sanctions",
              "brief": "", "rank": 7, "location": "", "category": "", "watchlist": 0, "hidden": False}
        url = X.story_url(it)
        self.assertTrue(url.endswith("?s=x"))
        href = X.intent_url(it)
        self.assertIn("s%3Dx", href)  # url-encoded ?s=x in the intent url param
        self.assertLessEqual(X.weighted_len(X.share_text(it), url), 280)

    def test_card_endpoint_always_png(self):
        code, body, ct = og.handle_get("/og/wire/" + "f"*16 + ".png")
        self.assertEqual(code, 200)
        self.assertEqual(ct, "image/png")
        self.assertTrue(body[:8] == b"\x89PNG\r\n\x1a\n")
        self.assertGreater(len(body), 1000)
