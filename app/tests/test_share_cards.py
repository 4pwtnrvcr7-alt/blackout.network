"""Per-item Post on X: tags, crafted share URLs, cards. Run: python -m unittest tests.test_share_cards"""
import sys, os, re, unittest
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import share_cards as S


class ShareCards(unittest.TestCase):
    def test_tags_3_to_5_every_kind(self):
        for k in S.KINDS:
            t = S.tags_for(k, "Test item", "Florida", "detail")
            self.assertTrue(3 <= len(t) <= 5, (k, t))
            self.assertEqual(len(set(x.lower() for x in t)), len(t))

    def test_intent_has_text_tags_and_share_url(self):
        u = S.intent("launch", "abc", "Soyuz 2.1b lifts off from Vostochny carrying Kosmos. T-minus 04:10:22",
                     "Soyuz 2.1b: Kosmos", "Vostochny Cosmodrome, Russia", "Vostochny Cosmodrome, Russia")
        q = parse_qs(urlparse(u).query)
        self.assertIn("T-minus", q["text"][0])
        self.assertTrue(3 <= len(re.findall(r"#\w+", q["text"][0])) <= 5)
        self.assertTrue(q["url"][0].startswith("https://blackout.network/share/launch/abc"))
        self.assertLessEqual(len(q["text"][0]) + 24, 280)

    def test_long_text_trimmed(self):
        u = S.intent("weather", "x", "word " * 100, "n", "d", "Sanford, FL")
        q = parse_qs(urlparse(u).query)["text"][0]
        self.assertLessEqual(len(q) + 24, 280)
        self.assertGreaterEqual(len(re.findall(r"#\w+", q)), 3)

    def test_page_meta(self):
        h = S.page_html("planet", "jupiter", {}).decode()
        self.assertIn('name="twitter:card" content="summary_large_image"', h)
        self.assertIn("/og/share/planet/jupiter.png", h)
        self.assertIn("location.replace", h)

    def test_card_png_and_bad_input(self):
        code, body, ct = S.handle_get("/og/share/planet/jupiter.png", {})
        self.assertEqual((code, ct), (200, "image/png")); self.assertTrue(body[:4] == b"\x89PNG")
        self.assertEqual(S.handle_get("/og/share/zzz/%3Cscript%3E.png", {})[0], 404)

    def test_no_nc_images_on_cards(self):
        self.assertNotIn("aditya", S.CRAFT_PHOTO); self.assertNotIn("juice", S.CRAFT_PHOTO)

    def test_dest_whitelist(self):
        s = S.spec("page", "x", {"p": ["//evil.com"]}); self.assertEqual(s["dest"], "/")
        s = S.spec("network", "x", {"p": ["/grid/status/spectrum"]}); self.assertEqual(s["dest"], "/grid/status/spectrum")
        s = S.spec("network", "x", {"p": ["https://evil.com"]}); self.assertEqual(s["dest"], "/grid")


if __name__ == "__main__":
    unittest.main()
