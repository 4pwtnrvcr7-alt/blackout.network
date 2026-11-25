import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_photo as P
import share_card as S


class StoryPhoto(unittest.TestCase):
    def test_license_gate(self):
        for ok in ("Public domain", "Public domain (U.S. government work)", "CC0", "CC BY 3.0", "CC BY 4.0", "OGL 3", "CC BY 2.0"):
            self.assertTrue(P.license_ok(ok), ok)
        for bad in ("", "CC BY-SA 4.0", "CC BY-SA 2.0", "CC BY-NC 4.0", "CC BY-ND 2.0", "All rights reserved", "Fair use"):
            self.assertFalse(P.license_ok(bad), bad)

    def test_headline_whole_in_three_lines(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        t = S._clean_head("Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz: Crud")
        self.assertFalse(t.endswith("Crud"))
        f, size, lines = S._story_head(d, t, 640)
        self.assertLessEqual(len(lines), 3)
        self.assertEqual(" ".join(lines), t)

    def test_no_photo_falls_back_to_map_not_black(self):
        it = dict(kind="story", id="t1", title="Magnitude 6.5 earthquake recorded in Vanuatu region", rank=5, color=S.AMBER, kicker="NATURAL DISASTER", loc="Vanuatu region",
                  art=("story", 172.3, -13.5, None), photo=None, stats=[], tags=[])
        im = S._lay_story(it)
        self.assertEqual(im.size, (1200, 675))
        px = im.resize((60, 34)).getdata()
        self.assertGreater(sum(sum(p) for p in px) / (3 * len(px)), 8)


if __name__ == "__main__":
    unittest.main()

    def test_named_people_from_title_without_profiles(self):
        names = P._named_people("x", "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers", "")
        self.assertIn("Scott Bessent", names)

    def test_quoted_landmark_not_possessive(self):
        title = "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days"
        import re
        m = re.search(r"[\"“”']([A-Z0-9][^\"“”']{1,60})[\"“”']", title)
        self.assertEqual(m.group(1), "PIF Tower")

    def test_persist_choice_and_card_across_empty_disk(self, tmp=None):
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "story_writer.db")
        try:
            P._dir = lambda: Path(d)
            png = b"\x89PNG\r\n\x1a\n" + b"x" * 3000
            jpg = b"\xff\xd8" + b"j" * 3000
            cand = dict(src="https://upload.wikimedia.org/x.jpg", credit="US Treasury", license="Public domain",
                        caption="Scott Bessent, 2025. File photo; not taken at this event.", kind="person", label="lab", link="")
            P.db_put("e2ca47e325c5b8e1", cand, jpg=jpg)
            P.put_card("e2ca47e325c5b8e1", png, cand["src"])
            # no files on disk
            self.assertTrue(P.resolved("e2ca47e325c5b8e1"))
            got = P.pick("e2ca47e325c5b8e1", "Scott Bessent Unleashes", "Tehran", "")
            self.assertEqual(got["src"], cand["src"])
            self.assertEqual(got["license"], "Public domain")
            self.assertEqual(P.get_card("e2ca47e325c5b8e1"), png)
            # cached restores jpeg
            path = P.cached(cand["src"])
            self.assertTrue(path and path.is_file() and path.stat().st_size > 2000)
        finally:
            os.environ.pop("BN_CARDS_DB", None)


    def test_multiline_credit_does_not_crash_for_live_stories(self):
        """Commons Artist metadata often has newlines; Pillow textlength raises ValueError on them (live 2:57 AM ET crash)."""
        import os, tempfile
        from PIL import Image
        import share_card as S
        d = tempfile.mkdtemp()
        jpg = Path(d) / "p.jpg"
        Image.new("RGB", (900, 1200), (20, 30, 40)).save(jpg, "JPEG")
        stories = [
            ("e2ca47e325c5b8e1", "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz", 2, "Tehran",
             "United States Department of the Treasury\nWikimedia Commons"),
            ("6b27e568eb9f503f", "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days", 2, "Riyadh",
             "Kolaiel\nWikimedia Commons"),
            ("dec0cddbd508e929", "Burnham launches inquiry into nuclear bomb test veterans’ records", 6, "United Kingdom",
             "Alecsandra Dragoi\nNo 10 Downing Street\n(Official portrait)"),
            ("9f5bc9d66d783d25", "— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package", 6, "Ukraine",
             "Press Service of the President of Ukraine\nWikimedia Commons"),
            ("e1e85cc0c198878d", "Ethiopia launches polio vaccination campaign to protect more than 11 million children: WHO deployed 28 staff…", 1, "Africa",
             "Author\nline two"),
            ("ef132895dca18576", "Director Liability Italy: Bank Failure Guide 2026", 4, "Italy",
             "Credit\nwith\nnewlines"),
        ]
        import story_photo as SP
        orig = SP.cached
        SP.cached = lambda src: jpg
        try:
            for cid, title, rank, loc, credit in stories:
                col = S.RED if rank >= 7 else S.AMBER if rank >= 4 else S.GREEN
                ph = dict(src="https://upload.wikimedia.org/x.jpg", credit=credit, license="Public domain", kind="person",
                          label="File photo; not taken at this event.")
                it = dict(kind="story", id=cid, title=S._clean_head(title), rank=rank, color=col, kicker="NEWS", loc=loc,
                          art=("story", None, None, ph["src"]), photo=ph, stats=[], tags=[])
                im = S._lay_story(it)
                self.assertEqual(im.size, (1200, 675), cid)
        finally:
            SP.cached = orig
