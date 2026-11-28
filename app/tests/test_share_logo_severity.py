"""Story share logos: background behind the B follows rank (Matt, Nov 27 8:47 PM ET).

Yellow / orange / red are the exact Refresh-button fill stops from PR #293.
Unscored stories keep the existing black logo. og.VERSION is not bumped;
per-severity filenames bust the X cache instead.

Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_share_logo_severity -v
"""
from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image

import og
import install_white_b_icons as inst
import site_page


def _rel_luma(rgb):
    def lin(c):
        x = c / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(a, b):
    l1, l2 = _rel_luma(a), _rel_luma(b)
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


class ShareLogoSeverity(unittest.TestCase):
    def test_og_version_unchanged(self):
        self.assertEqual(og.VERSION, "25")

    def test_tier_mapping(self):
        # Unscored stays black
        for v in (None, "", "unranked", "na", object()):
            self.assertEqual(og.story_share_tier(v), "black", v)
        # Lower band (existing 0-3) -> yellow
        for r in (0, 1, 2, 3, "0", "3"):
            self.assertEqual(og.story_share_tier(r), "yellow", r)
        # Mid band (4-6) -> orange
        for r in (4, 5, 6, "5"):
            self.assertEqual(og.story_share_tier(r), "orange", r)
        # Highest (7-10, and anything above) -> red
        for r in (7, 8, 9, 10, 11, "8"):
            self.assertEqual(og.story_share_tier(r), "red", r)
        self.assertEqual(og.story_share_tier(-1), "black")

    def test_share_image_urls(self):
        self.assertEqual(og.story_share_image(None), og.STORY_SHARE_IMAGE)
        self.assertEqual(
            og.story_share_image(2),
            "https://blackout.network/img/share-logo-1200-yellow.png",
        )
        self.assertEqual(
            og.story_share_image(5),
            "https://blackout.network/img/share-logo-1200-orange.png",
        )
        self.assertEqual(
            og.story_share_image(9),
            "https://blackout.network/img/share-logo-1200-red.png",
        )
        # No ?v= query — the filename itself is the cache buster
        for r in (None, 0, 4, 7):
            self.assertNotIn("?v=", og.story_share_image(r))

    def test_tags_use_tier_url(self):
        cid = "e2ca47e325c5b8e1"
        cases = {
            None: og.STORY_SHARE_IMAGE,
            1: "https://blackout.network/img/share-logo-1200-yellow.png",
            6: "https://blackout.network/img/share-logo-1200-orange.png",
            7: "https://blackout.network/img/share-logo-1200-red.png",
        }
        for rank, url in cases.items():
            html = og.tags(
                title="A headline",
                desc="d",
                url="https://blackout.network/wire/" + cid,
                story_id=cid,
                rank=rank,
                og_type="article",
            )
            self.assertIn(f'property="og:image" content="{url}"', html)
            self.assertIn(f'name="twitter:image" content="{url}"', html)
            self.assertIn('name="twitter:card" content="summary"', html)
            self.assertNotIn("summary_large_image", html)
            self.assertNotIn("/og/wire/", html)
            self.assertIn('property="og:image:width" content="1200"', html)
            self.assertIn('property="og:image:height" content="1200"', html)

    def test_site_page_passes_rank(self):
        black = "https://blackout.network/img/share-logo-1200.png"
        html = site_page.page("A headline", "d", "<p>x</p>", "/wire/e2ca47e325c5b8e1").decode()
        self.assertIn(f'property="og:image" content="{black}"', html)
        orange = "https://blackout.network/img/share-logo-1200-orange.png"
        html = site_page.page(
            "A headline", "d", "<p>x</p>", "/wire/e2ca47e325c5b8e1", rank=4
        ).decode()
        self.assertIn(f'property="og:image" content="{orange}"', html)
        self.assertIn(f'name="twitter:image" content="{orange}"', html)

    def test_refresh_stops_match_pr293(self):
        self.assertEqual(inst.SHARE_YELLOW, (255, 229, 102))
        self.assertEqual(inst.SHARE_ORANGE, (255, 154, 26))
        self.assertEqual(inst.SHARE_RED, (255, 90, 60))
        self.assertEqual(inst.SHARE_INK, (11, 13, 16))
        self.assertEqual(og.SHARE_YELLOW, inst.SHARE_YELLOW)
        self.assertEqual(og.SHARE_ORANGE, inst.SHARE_ORANGE)
        self.assertEqual(og.SHARE_RED, inst.SHARE_RED)
        self.assertEqual(og.SHARE_INK, inst.SHARE_INK)

    def test_ink_contrast_passes_wcag_aa(self):
        # Same figures as PR #293 (dark #0B0D10 on the three fill stops).
        self.assertGreaterEqual(_contrast(inst.SHARE_INK, inst.SHARE_YELLOW), 4.5)
        self.assertGreaterEqual(_contrast(inst.SHARE_INK, inst.SHARE_ORANGE), 4.5)
        self.assertGreaterEqual(_contrast(inst.SHARE_INK, inst.SHARE_RED), 4.5)
        self.assertAlmostEqual(_contrast(inst.SHARE_INK, inst.SHARE_YELLOW), 15.43, places=1)
        self.assertAlmostEqual(_contrast(inst.SHARE_INK, inst.SHARE_ORANGE), 9.16, places=1)
        self.assertAlmostEqual(_contrast(inst.SHARE_INK, inst.SHARE_RED), 6.28, places=1)
        # White on yellow and orange fails AA, which is why the B is dark there.
        self.assertLess(_contrast((255, 255, 255), inst.SHARE_YELLOW), 4.5)
        self.assertLess(_contrast((255, 255, 255), inst.SHARE_ORANGE), 4.5)

    def test_severity_pngs_are_square_with_solid_fill_and_ink(self):
        written = inst.write_severity_share_logos()
        # Also materialize the black master so we can compare the B shape.
        raw = __import__("base64").b64decode("".join(inst.SHARE_B64.read_text().split()))
        black_path = inst.IMG / "share-logo-1200.png"
        if not black_path.is_file():
            black_path.write_bytes(raw)
        black = Image.open(black_path).convert("RGB")
        mask = inst.share_letter_mask(black)
        self.assertEqual(mask.size, (1200, 1200))
        # Letter body and field must be identical across all four images.
        import static_files

        for name, bg in inst.SHARE_SEVERITY.items():
            path = written[name]
            self.assertTrue(path.is_file(), name)
            im = Image.open(path)
            self.assertEqual(im.size, (1200, 1200), name)
            self.assertEqual(im.format, "PNG", name)
            self.assertFalse(im.info.get("exif"), name)
            rgb = im.convert("RGB")
            self.assertEqual(rgb.getpixel((0, 0)), bg, name)
            self.assertEqual(rgb.getpixel((1199, 1199)), bg, name)
            # A known letter-body pixel (center of the existing mark is in the spine)
            self.assertEqual(rgb.getpixel((600, 600)), inst.SHARE_INK, name)
            # Served at the public path
            code, body, ct = static_files.handle_get(f"/img/share-logo-1200-{name}.png", {})
            self.assertEqual(code, 200, name)
            self.assertEqual(ct, "image/png", name)
            self.assertLess(len(body), 1_000_000, name)
            served = Image.open(BytesIO(body))
            self.assertEqual(served.size, (1200, 1200), name)
            # Mask of the generated image must match the master (shape unchanged)
            # Recreate: ink pixels where mask is 255, bg where mask is 0.
            mx = mask.load()
            px = rgb.load()
            # Spot-check a grid rather than every pixel (1200^2 is slow in pure Python)
            for y in range(0, 1200, 17):
                for x in range(0, 1200, 17):
                    m = mx[x, y]
                    if m == 255:
                        self.assertEqual(px[x, y], inst.SHARE_INK, (name, x, y))
                    elif m == 0:
                        self.assertEqual(px[x, y], bg, (name, x, y))


if __name__ == "__main__":
    unittest.main()
