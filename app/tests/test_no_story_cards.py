"""Wire story photo cards are off by default (Matt, 11:44 AM ET Nov 27 2026).

Newsletter images, /bnt/media dividers, and /newsletter/img are not gated here.

Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_no_story_cards -v
"""
from __future__ import annotations

import os
import unittest

import og
import wire_check as WC


class StoryCardsOff(unittest.TestCase):
    def test_flag_defaults_off(self):
        old = os.environ.get("BN_STORY_CARDS")
        try:
            os.environ.pop("BN_STORY_CARDS", None)
            self.assertFalse(WC.story_cards_on())
            os.environ["BN_STORY_CARDS"] = "1"
            self.assertTrue(WC.story_cards_on())
            os.environ["BN_STORY_CARDS"] = "0"
            self.assertFalse(WC.story_cards_on())
        finally:
            if old is None:
                os.environ.pop("BN_STORY_CARDS", None)
            else:
                os.environ["BN_STORY_CARDS"] = old

    def test_check_ignores_missing_and_bad_photos(self):
        it = {"h": "A long enough headline about a real event", "d": "body", "k": "conflict",
              "loc": "Kyiv, Ukraine", "lat": 50.45, "lon": 30.52}
        v = WC.check(it, raw_tags=["#Ukraine", "#Kyiv", "#Conflict"], loc_tags=["#Ukraine", "#Kyiv"],
                     choice=None, has_photo=None)
        self.assertNotIn("photo-check-error", v["reasons"])
        self.assertNotIn("no-photo-card", v["reasons"])
        self.assertTrue(v["ok"] or "tags" not in "".join(v["reasons"]), v)
        v2 = WC.check(it, raw_tags=["#Ukraine", "#Kyiv", "#Conflict"], loc_tags=["#Ukraine", "#Kyiv"],
                      choice={"kind": "place", "src": "x"}, has_photo=False)
        self.assertNotIn("no-photo-card", v2["reasons"])
        self.assertFalse(any(r.startswith("photo-") for r in v2["reasons"]))

    def test_thin_headline_and_tags_still_hold(self):
        it = {"h": "Fire", "d": "", "k": "wreck", "loc": "", "lat": None, "lon": None}
        v = WC.check(it, raw_tags=["#A"], loc_tags=(), has_photo=True)
        self.assertIn("thin-headline", v["reasons"])
        self.assertTrue(any(r.startswith("tags") for r in v["reasons"]))
        self.assertFalse(v["ok"])

    def test_story_tags_are_summary_without_images(self):
        cid = "e2ca47e325c5b8e1"
        html = og.tags(title="A headline", desc="d", url="https://blackout.network/wire/" + cid,
                       story_id=cid, rank=7, og_type="article")
        self.assertIn('name="twitter:card" content="summary"', html)
        self.assertNotIn("summary_large_image", html)
        self.assertNotIn("og:image", html)
        self.assertNotIn("twitter:image", html)
        self.assertNotIn("/og/wire/", html)

    def test_non_story_pages_keep_og_image(self):
        h = og.tags(title="Crime map | BLACKOUT.NETWORK", desc="Look up crime.",
                    url="https://blackout.network/crime", key="crime")
        self.assertIn("og:image", h)
        self.assertIn("twitter:image", h)
        self.assertIn("summary_large_image", h)
        self.assertIn("/og/crime.png", h)

    def test_story_og_endpoint_is_404(self):
        code, body, ct = og.handle_get("/og/wire/" + "a" * 16 + ".png")
        self.assertEqual(code, 404)
        self.assertFalse(body)

    def test_newsletter_image_modules_untouched(self):
        # Guardrail: this change must not import-break or wrap newsletter image paths.
        import newsletter_v2 as V2
        import newsletter_v4 as V4
        import newsletter_img as NI
        self.assertTrue(callable(V2.lead_image))
        self.assertTrue(callable(V4._divider))
        self.assertTrue(callable(NI.handle_get))
        self.assertTrue(callable(NI.card))


if __name__ == "__main__":
    unittest.main()
