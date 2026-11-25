"""Per-page Open Graph / Twitter share images (og.py)."""
import io, os, re, sys, tempfile, unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from PIL import Image

import og

MAIN = ["home", "live", "wire", "map", "crime", "streams", "solar", "weather",
        "network", "sources", "credits"]


def _img(data):
    im = Image.open(io.BytesIO(data))
    return im.convert("RGB")


def _yellow_count(im, step=15):
    n = 0
    pix = im.load()
    w, h = im.size
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = pix[x, y]
            if r > 180 and g > 140 and b < 90:
                n += 1
    return n


def _red_count(im, step=8):
    n = 0
    pix = im.load()
    w, h = im.size
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = pix[x, y]
            if r > 160 and g < 70 and b < 90:
                n += 1
    return n


class OgImages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="bn-og-test-")
        os.environ["BN_OG_CACHE"] = cls._tmp.name
        og._MEM.clear()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_main_pages_are_1200x630(self):
        for key in MAIN:
            with self.subTest(key=key):
                im = _img(og.png_for(key))
                self.assertEqual(im.size, (1200, 630), key)
                self.assertEqual(im.mode, "RGB")

    def test_handle_get_png(self):
        code, body, ctype = og.handle_get("/og/crime.png")
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "image/png")
        self.assertEqual(_img(body).size, (1200, 630))
        code, body, ctype = og.handle_get("/og/wire/6727e7f2ac056676.png")
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "image/png")
        self.assertEqual(_img(body).size, (1200, 630))

    def test_image_url_version_and_aliases(self):
        self.assertEqual(og.image_url("crime"), "https://blackout.network/og/crime.png?v=9")
        self.assertEqual(og.image_url("heatmap"), "https://blackout.network/og/map.png?v=9")
        self.assertEqual(og.image_url("tv-radio"), "https://blackout.network/og/streams.png?v=9")
        u = og.image_url("wire", story_id="6727e7f2ac056676", title="Hello", rank=8)
        self.assertTrue(u.startswith("https://blackout.network/og/wire/6727e7f2ac056676.png?v=9-"))
        u2 = og.image_url("wire", story_id="6727e7f2ac056676", title="Hello changed", rank=8)
        self.assertNotEqual(u, u2)

    def test_tags_include_required_fields(self):
        h = og.tags(title="Crime map | BLACKOUT.NETWORK", desc="Look up crime.",
                    url="https://blackout.network/crime", key="crime")
        self.assertIn('property="og:image" content="https://blackout.network/og/crime.png?v=9"', h)
        self.assertIn('property="og:title" content="Crime map | BLACKOUT.NETWORK"', h)
        self.assertIn('property="og:url" content="https://blackout.network/crime"', h)
        self.assertIn('property="og:description" content="Look up crime."', h)
        self.assertIn('name="twitter:card" content="summary_large_image"', h)
        self.assertIn('name="twitter:image" content="https://blackout.network/og/crime.png?v=9"', h)
        self.assertIn("og:image:width", h)
        self.assertNotIn("icon-og-v2-1200x630", h)

    def test_page_cards_have_no_yellow(self):
        # Design chrome is monochrome; real NASA stills may have warm highlights, so we
        # only fail on the saturated yellow of the old rank-bar / map dots.
        for key in MAIN:
            with self.subTest(key=key):
                self.assertEqual(_yellow_count(_img(og.png_for(key))), 0, key)

    def test_rank_red_only_at_seven_plus(self):
        lo = _img(og.png_bytes(og.render("A lower-rank story headline", rank=3, tagline=True)))
        hi = _img(og.png_bytes(og.render("A high-rank story headline", rank=8, tagline=True)))
        self.assertEqual(_red_count(lo), 0)
        self.assertGreater(_red_count(hi), 0)

    def test_card_titles_have_no_emoji(self):
        for key, spec in og.PAGES.items():
            self.assertEqual(og._strip_emoji(spec["card"]), spec["card"], key)
            self.assertNotIn("Signal over noise", spec["card"])
            self.assertNotIn("Signal over noise", spec["title"])

    def test_sitenav_and_theme_and_credits_use_new_images(self):
        import sitenav
        crime = sitenav.head_html("crime")
        self.assertIn("https://blackout.network/og/crime.png?v=", crime)
        self.assertIn('og:url" content="https://blackout.network/crime"', crime)
        self.assertNotIn("icon-og-v2", crime)
        sources = sitenav.head_html("sources")
        self.assertIn("/og/sources.png?v=", sources)
        import theme
        home = theme.home_page()
        self.assertIn("https://blackout.network/og/home.png?v=", home)
        self.assertNotIn("icon-og-v2-1200x630", home)
        cred = theme.credits_page()
        self.assertIn("https://blackout.network/og/credits.png?v=", cred)
        self.assertIn('og:url" content="https://blackout.network/credits"', cred)

    def test_map_and_wire_shell_have_og_image(self):
        import signal_map, wire_v2
        html = signal_map.page2({}) if hasattr(signal_map, "page2") else signal_map.page({})
        self.assertIn("https://blackout.network/og/map.png?v=", html)
        self.assertIn('og:url" content="https://blackout.network/map"', html)
        shell = wire_v2.shell("The Wire: live threat feed | BLACKOUT.NETWORK", "Live threats.", "<p>x</p>", "/wire")
        self.assertIn("https://blackout.network/og/wire.png?v=", shell)
        story = wire_v2.shell("A headline | BLACKOUT.NETWORK", "Dek.", "<p>x</p>", "/wire/6727e7f2ac056676", rank=8)
        self.assertIn("/og/wire/6727e7f2ac056676.png?v=9-", story)
        self.assertIn('og:type" content="article"', story)

    def test_crawler_share_page(self):
        self.assertTrue(og.is_crawler("Twitterbot/1.0"))
        self.assertTrue(og.is_crawler("facebookexternalhit/1.1"))
        self.assertFalse(og.is_crawler("Mozilla/5.0 (iPad; CPU OS 18_0)"))
        html = og.share_page("solar").decode()
        self.assertIn("/og/solar.png?v=9", html)
        self.assertIn('og:url" content="https://blackout.network/solar"', html)
        self.assertIn("Solar &amp; Seismic", html)
        self.assertNotIn('http-equiv="refresh"', html.lower())
        self.assertIn("location.replace('/live#solar')", html)

    def test_addons_route(self):
        import addons
        self.assertEqual(addons.ROUTES.get("/og"), "og")

    def test_cache_returns_same_bytes(self):
        a = og.png_for("live")
        b = og.png_for("live")
        self.assertEqual(a, b)
        self.assertGreater(len(a), 8000)


    def test_ampersand_escaped_once(self):
        # Raw '&' and a pre-escaped '&amp;' must both become a single '&amp;'
        # so crawlers decode the card title as "Live TV & Radio".
        for incoming in ("Live TV & Radio", "Live TV &amp; Radio", "Solar &amp; Seismic"):
            h = og.tags(title=incoming, desc="A & B and already &amp; C",
                        url="https://blackout.network/streams", key="streams")
            self.assertNotIn("&amp;amp;", h)
            self.assertIn('property="og:title" content="Live TV &amp; Radio"' if "TV" in incoming
                          else 'property="og:title" content="Solar &amp; Seismic"', h)
            self.assertIn('property="og:description" content="A &amp; B and already &amp; C"', h)
            self.assertIn('name="twitter:title" content="', h)
            self.assertIn('name="twitter:description" content="A &amp; B and already &amp; C"', h)
            # decoded values read as '&'
            import html as _html, re as _re
            raw = _re.search(r'property="og:title" content="([^"]+)"', h).group(1)
            self.assertNotIn("&amp;", _html.unescape(raw))
            self.assertIn("&", _html.unescape(raw))
            self.assertEqual(raw.count("&amp;"), 1)

    def test_unknown_og_path_still_png_or_404(self):
        code, body, *rest = og.handle_get("/og/not-a-real-page.png")
        self.assertIn(code, (200, 404))
        if code == 200:
            self.assertEqual(_img(body).size, (1200, 630))
        code2, _, *__ = og.handle_get("/og/")
        self.assertEqual(code2, 404)


if __name__ == "__main__":
    unittest.main()
