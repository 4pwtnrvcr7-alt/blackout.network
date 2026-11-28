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
        self.assertEqual(code, 404)  # story cards off (BN_STORY_CARDS default 0)
        self.assertFalse(body)

    def test_image_url_version_and_aliases(self):
        self.assertEqual(og.image_url("crime"), f"https://blackout.network/og/crime.png?v={og.VERSION}")
        self.assertEqual(og.image_url("heatmap"), f"https://blackout.network/og/map.png?v={og.VERSION}")
        self.assertEqual(og.image_url("tv-radio"), f"https://blackout.network/og/streams.png?v={og.VERSION}")
        u = og.image_url("wire", story_id="6727e7f2ac056676", title="Hello", rank=8)
        self.assertTrue(u.startswith(f"https://blackout.network/og/wire/6727e7f2ac056676.png?v={og.VERSION}-"))
        u2 = og.image_url("wire", story_id="6727e7f2ac056676", title="Hello changed", rank=8)
        self.assertNotEqual(u, u2)

    def test_tags_include_required_fields(self):
        h = og.tags(title="Crime map | BLACKOUT.NETWORK", desc="Look up crime.",
                    url="https://blackout.network/crime", key="crime")
        self.assertIn(f'property="og:image" content="{og.STORY_SHARE_IMAGE}"', h)
        self.assertIn('property="og:title" content="Crime map | BLACKOUT.NETWORK"', h)
        self.assertIn('property="og:url" content="https://blackout.network/crime"', h)
        self.assertIn('property="og:description" content="Look up crime."', h)
        self.assertIn('name="twitter:card" content="summary"', h)
        self.assertNotIn("summary_large_image", h)
        self.assertIn(f'name="twitter:image" content="{og.STORY_SHARE_IMAGE}"', h)
        self.assertNotIn("/og/crime.png", h)
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

    def test_white_b_mark_sits_left_of_the_wordmark(self):
        """Share cards place the white B mark to the left of blackout.network (Matt, Nov 25)."""
        im = og.render("A share-card headline for the lockup test", tagline=True)
        self.assertEqual(im.size, (1200, 630))
        left, y, mark, gap = 72, 56, 36, 10
        font = og.inter(22, bold=True)
        end = og.draw_wordmark(im.copy(), __import__("PIL").ImageDraw.Draw(im.copy()),
                               left, y, font, og.WORD, tracking=3.2, mark=mark, gap=gap)
        self.assertGreater(end, left + mark + gap + 80)
        # The mark box is not a flat black square: the white serif B is bright.
        box = im.crop((left, 49, left + mark, 49 + mark))
        px = list(box.getdata())
        bright = sum(1 for r, g, b in px if max(r, g, b) > 80)
        self.assertGreater(bright, 40, "white B mark should be visible in the top-left lockup")
        # Wordmark text starts to the right of the mark (light pixels in the text band).
        text = im.crop((left + mark + gap, 54, left + mark + gap + 180, 82))
        tbright = sum(1 for r, g, b in text.getdata() if max(r, g, b) > 160)
        self.assertGreater(tbright, 20)

    def test_card_titles_have_no_emoji(self):
        for key, spec in og.PAGES.items():
            self.assertEqual(og._strip_emoji(spec["card"]), spec["card"], key)
            self.assertNotIn("Signal over noise", spec["card"])
            self.assertNotIn("Signal over noise", spec["title"])

    def test_sitenav_and_theme_and_credits_use_new_images(self):
        import sitenav
        logo = "https://blackout.network/img/share-logo-1200.png"
        crime = sitenav.head_html("crime")
        self.assertIn(logo, crime)
        self.assertIn('og:url" content="https://blackout.network/crime"', crime)
        self.assertNotIn("icon-og-v2", crime)
        self.assertNotIn("/og/crime.png", crime)
        sources = sitenav.head_html("sources")
        self.assertIn(logo, sources)
        self.assertNotIn("/og/sources.png", sources)
        import theme
        home = theme.home_page()
        self.assertIn(logo, home)
        self.assertNotIn("icon-og-v2-1200x630", home)
        self.assertNotIn("/og/home.png", home)
        cred = theme.credits_page()
        self.assertIn(logo, cred)
        self.assertNotIn("/og/credits.png", cred)
        self.assertIn('og:url" content="https://blackout.network/credits"', cred)

    def test_map_and_wire_shell_have_og_image(self):
        import signal_map, wire_v2
        logo = "https://blackout.network/img/share-logo-1200.png"
        html = signal_map.page2({}) if hasattr(signal_map, "page2") else signal_map.page({})
        self.assertIn(logo, html)
        self.assertNotIn("/og/map.png", html)
        self.assertIn('og:url" content="https://blackout.network/map"', html)
        shell = wire_v2.shell("The Wire: live threat feed | BLACKOUT.NETWORK", "Live threats.", "<p>x</p>", "/wire")
        self.assertIn(logo, shell)
        self.assertNotIn("/og/wire.png", shell)
        story = wire_v2.shell("A headline | BLACKOUT.NETWORK", "Dek.", "<p>x</p>", "/wire/6727e7f2ac056676", rank=8)
        self.assertNotIn("/og/wire/6727e7f2ac056676.png", story)
        red = "https://blackout.network/img/share-logo-1200-red.png"
        self.assertIn(f'property="og:image" content="{red}"', story)
        self.assertIn(f'name="twitter:image" content="{red}"', story)
        self.assertIn('name="twitter:card" content="summary"', story)
        self.assertNotIn("summary_large_image", story)
        self.assertIn('og:type" content="article"', story)

    def test_crawler_share_page(self):
        self.assertTrue(og.is_crawler("Twitterbot/1.0"))
        self.assertTrue(og.is_crawler("facebookexternalhit/1.1"))
        self.assertFalse(og.is_crawler("Mozilla/5.0 (iPad; CPU OS 18_0)"))
        html = og.share_page("solar").decode()
        self.assertIn("https://blackout.network/img/share-logo-1200.png", html)
        self.assertNotIn("/og/solar.png", html)
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
