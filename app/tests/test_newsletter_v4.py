import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import newsletter_v4 as V4

class V4Tests(unittest.TestCase):
    def test_flag(self):
        os.environ.pop("BN_NL_V4", None); self.assertTrue(V4.on({}))
        os.environ["BN_NL_V4"] = "0"; self.assertFalse(V4.on({})); os.environ.pop("BN_NL_V4", None)
        self.assertFalse(V4.on({"template": "v2"}))
    def test_rank_colours(self):
        self.assertEqual(V4.rank_col(7), V4.RED); self.assertEqual(V4.rank_col(10), V4.RED)
        self.assertNotEqual(V4.rank_col(6), V4.RED)
    def test_pool_rotates_without_repeats(self):
        P = V4.pool(); self.assertTrue(P.get("war"))
        from datetime import datetime, timezone
        seen = []
        for n in range(len(P["war"])):
            iss = {"end": datetime(2026, 11, 17, 23, tzinfo=timezone.utc), "slot": "evening"}
            seen.append(P["war"][(V4.issue_no(iss) + n) % len(P["war"])]["name"])
        self.assertEqual(len(set(seen)), len(P["war"]))
        for ims in P.values():
            for im in ims: self.assertTrue(os.path.exists(os.path.join(os.path.dirname(V4.__file__), "theme_static", "media", im["name"] + ".b64")))

    def test_headline_and_right_now_link_to_story(self):
        h = V4._headline("Kuwait drone strike", url="https://blackout.network/wire/abc")
        self.assertIn('data-bn-h="1"', h)
        self.assertIn('href="https://blackout.network/wire/abc"', h)
        self.assertIn("text-decoration:none", h)
        self.assertIn("Kuwait drone strike", h)
        self.assertNotIn("<a ", V4._headline("Kuwait drone strike"))

        class FakeN:
            def card_headline(self, it): return it["title"]
            def wire_url(self, cid, c=None): return f"https://blackout.network/wire/{cid}"
        orig = V4._N
        try:
            V4._N = lambda: FakeN()
            html = V4._top_list([
                {"cluster_id": "aaa", "title": "First story"},
                {"cluster_id": "bbb", "title": "Second story"},
                {"title": "No page"},
            ], {"base_url": "https://blackout.network"})
            one = V4._top_list([{"cluster_id": "aaa", "title": "Only one"}], {"base_url": "https://blackout.network"})
        finally:
            V4._N = orig
        self.assertIn("RIGHT NOW", html)
        self.assertIn('href="https://blackout.network/wire/aaa"', html)
        self.assertIn('href="https://blackout.network/wire/bbb"', html)
        self.assertIn("1. First story", html)
        self.assertIn("2. Second story", html)
        self.assertNotIn("No page", html)
        self.assertIn("text-decoration:none", html)
        self.assertEqual(html.count("<a href="), 2)
        self.assertEqual(one, "")

    def test_divider_image_links_to_first_story(self):
        from datetime import datetime, timezone
        iss = {"end": datetime(2026, 11, 27, 12, tzinfo=timezone.utc), "slot": "morning"}
        html = V4._divider("war", iss, {"base_url": "https://blackout.network"}, url="https://blackout.network/wire/abc")
        self.assertIn("<img ", html)
        self.assertIn('href="https://blackout.network/wire/abc"', html)
        self.assertIn("WAR &amp; CONFLICT", html)

if __name__ == "__main__": unittest.main()
