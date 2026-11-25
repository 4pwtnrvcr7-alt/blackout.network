import io, sys, unittest
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
        self.assertFalse(any("…" in l or l.endswith("...") for l in lines))

    def test_long_headlines_fit_without_ellipsis(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        titles = [
            "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz",
            "Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine, including 48 anti-ballistic missiles. Ukraine also expects missiles for F-16s and NASAMS systems.",
            "Ethiopia launches polio vaccination campaign to protect more than 11 million children: WHO deployed 28 staff",
            "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using…",
        ]
        for raw in titles:
            t = S._card_headline(raw)
            self.assertNotIn("NASAMS", t)
            for maxw in (640, 700):
                f, size, lines = S._story_head(d, t, maxw)
                joined = " ".join(lines)
                self.assertLessEqual(len(lines), 3, raw)
                self.assertGreaterEqual(size, S.HEAD_MIN, (raw, size))
                self.assertFalse(any("…" in l or l.endswith("...") for l in lines), raw)
                self.assertNotIn("…", joined)
                self.assertNotIn("NASAMS", joined)
                if "Strait of Hormuz" in S._clean_head(raw):
                    self.assertIn("Strait of Hormuz", joined)

    def test_no_photo_falls_back_to_map_not_black(self):
        it = dict(kind="story", id="t1", title="Magnitude 6.5 earthquake recorded in Vanuatu region", rank=5, color=S.AMBER, kicker="NATURAL DISASTER", loc="Vanuatu region",
                  art=("story", 172.3, -13.5, None), photo=None, stats=[], tags=[])
        im = S._lay_story(it)
        self.assertEqual(im.size, (1200, 675))
        px = im.resize((60, 34)).getdata()
        self.assertGreater(sum(sum(p) for p in px) / (3 * len(px)), 8)

    def test_named_people_from_title_without_profiles(self):
        names = P._named_people("x", "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers", "")
        self.assertIn("Scott Bessent", names)

    def test_bare_surname_headline_uses_full_name(self):
        names = P._named_people("x", "Burnham launches inquiry into nuclear bomb test veterans’ records", "")
        self.assertIn("Andy Burnham", names)
        names = P._named_people("x", "Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package", "")
        self.assertIn("Volodymyr Zelensky", names)

    def test_quoted_landmark_not_possessive(self):
        title = "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days"
        terms = P._landmark_terms(title)
        self.assertEqual(terms[0], "PIF Tower")
        self.assertIn("Public Investment Fund Tower", terms)

    def test_persist_choice_and_card_across_empty_disk(self, tmp=None):
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            png = b"\x89PNG\r\n\x1a\n" + b"x" * 3000
            jpg = b"\xff\xd8" + b"j" * 3000
            cand = dict(src="https://upload.wikimedia.org/x.jpg", credit="US Treasury", license="Public domain",
                        caption="Scott Bessent, 2025. File photo; not taken at this event.", kind="person", label="lab", link="")
            P.db_put("e2ca47e325c5b8e1", cand, jpg=jpg)
            P.put_card("e2ca47e325c5b8e1", png, cand["src"])
            self.assertTrue(P.resolved("e2ca47e325c5b8e1"))
            self.assertTrue(P.has_photo("e2ca47e325c5b8e1"))
            got = P.pick("e2ca47e325c5b8e1", "Scott Bessent Unleashes", "Tehran", "")
            self.assertEqual(got["src"], cand["src"])
            self.assertEqual(got["license"], "Public domain")
            self.assertEqual(P.get_card("e2ca47e325c5b8e1"), png)
            path = P.cached(cand["src"])
            self.assertTrue(path and path.is_file() and path.stat().st_size > 2000)
            self.assertIn("e2ca47e325c5b8e1", P.card_cids(10))
        finally:
            os.environ.pop("BN_CARDS_DB", None)

    def test_none_lookup_is_not_resolved(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            P.db_put("deadbeefdeadbeef", None, none=True)
            self.assertFalse(P.has_photo("deadbeefdeadbeef"))
            self.assertFalse(P.resolved("deadbeefdeadbeef"))
        finally:
            os.environ.pop("BN_CARDS_DB", None)

    def test_multiline_credit_does_not_crash_for_live_stories(self):
        """Commons Artist metadata often has newlines; Pillow textlength raises ValueError on them (live 2:57 AM ET crash)."""
        import os, tempfile
        from PIL import Image
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
        orig = P.cached
        P.cached = lambda src: jpg
        try:
            for cid, title, rank, loc, credit in stories:
                col = S.RED if rank >= 7 else S.AMBER if rank >= 4 else S.GREEN
                ph = dict(src="https://upload.wikimedia.org/x.jpg", credit=credit, license="Public domain", kind="person",
                          label="File photo; not taken at this event.")
                it = dict(kind="story", id=cid, title=S._clean_head(title), rank=rank, color=col, kicker="NEWS", loc=loc,
                          art=("story", None, None, ph["src"]), photo=ph, stats=[], tags=[])
                im = S._lay_story(it)
                self.assertEqual(im.size, (1200, 675), cid)
                # drawn headline must not end with an ellipsis for these titles
                # (spot-check via relayout of the title itself)
                from PIL import ImageDraw
                _, _, lines = S._story_head(ImageDraw.Draw(im), it["title"], 640)
                self.assertFalse(any(l.endswith("…") or l.endswith("...") for l in lines), cid)
        finally:
            P.cached = orig

    def test_card_headline_first_sentence_only(self):
        h = S._card_headline("— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine, including 48 anti-ballistic missiles. Ukraine also expects missiles for F-16s and NASAMS systems.")
        self.assertTrue(h.startswith("Zelensky says"))
        self.assertFalse(h.startswith("—") or h.startswith("-") or h.startswith("–"))
        self.assertNotIn("NASAMS", h)
        self.assertNotIn("F-16s", h)
        self.assertIn("new arms package", h)

    def test_card_headline_strips_leading_trailing_dashes(self):
        cases = [
            "— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine",
            "– Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine",
            "― Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine",
            "... Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine ...",
            '"Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine."',
        ]
        for raw in cases:
            h = S._card_headline(raw)
            self.assertTrue(h.startswith("Zelensky says"), repr(h))
            self.assertFalse(h[0] in "-–—―•.,;:'\"" + "\u201c\u201d", repr(h))
            self.assertFalse(h.endswith(("...", "…", "-", "–", "—", ".")), repr(h))

    def test_quoted_landmark_curly_and_expand(self):
        straight = "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days"
        curly = "Riyadh’s landmark ‘PIF Tower’ struck in aerial attack for second time in five days"
        self.assertEqual(P._landmark_terms(straight)[0], "PIF Tower")
        self.assertIn("Public Investment Fund Tower", P._landmark_terms(straight))
        self.assertEqual(P._landmark_terms(curly)[0], "PIF Tower")
        self.assertTrue(P.landmark_in(straight) and P.landmark_in(curly))
        # possessive must not be captured
        self.assertNotIn("s landmark", " ".join(P._landmark_terms(straight)))

    def test_put_card_does_not_replace_photo_with_map(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            mapp = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            newer = b"\x89PNG\r\n\x1a\n" + b"N" * 4000
            src = "https://upload.wikimedia.org/zelensky.jpg"
            P.put_card("9f5bc9d66d783d25", photo, src)
            self.assertTrue(P.card_has_photo("9f5bc9d66d783d25"))
            self.assertEqual(P.get_card("9f5bc9d66d783d25"), photo)
            # a later map build must not clobber the photo card (the live Zelensky loss)
            P.put_card("9f5bc9d66d783d25", mapp, "")
            self.assertEqual(P.get_card("9f5bc9d66d783d25"), photo)
            self.assertTrue(P.card_has_photo("9f5bc9d66d783d25"))
            # a later photo card may replace it
            P.put_card("9f5bc9d66d783d25", newer, src)
            self.assertEqual(P.get_card("9f5bc9d66d783d25"), newer)
        finally:
            os.environ.pop("BN_CARDS_DB", None)



    def test_fast_path_queues_when_jpeg_exists_but_card_is_map(self):
        import os, tempfile
        from unittest import mock
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            png = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            jpg = b"\xff\xd8" + b"j" * 3000
            cand = dict(src="https://upload.wikimedia.org/x.jpg", credit="US Treasury", license="Public domain",
                        caption="Scott Bessent, 2025.", kind="person", label="lab", link="")
            P.db_put("e2ca47e325c5b8e1", cand, jpg=jpg)
            P.put_card("e2ca47e325c5b8e1", png, "")  # map card, jpeg already stored
            self.assertTrue(P.has_photo("e2ca47e325c5b8e1"))
            self.assertFalse(P.card_has_photo("e2ca47e325c5b8e1"))
            # JPEG already stored: rebuild the photo card immediately (no network), do not leave a map in place.
            built = []
            def fake_build(cid, fetch=False):
                built.append((cid, fetch))
                photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
                P.put_card(cid, photo, cand["src"])
                return photo
            S._SC.clear()
            with mock.patch.object(S, "_story_build", side_effect=fake_build):
                out = S.story_png_fast("e2ca47e325c5b8e1")
            self.assertTrue(built and built[0][0]=="e2ca47e325c5b8e1" and built[0][1] is False, built)
            self.assertTrue(P.card_has_photo("e2ca47e325c5b8e1"))
            self.assertEqual(out, b"\x89PNG\r\n\x1a\n" + b"P" * 4000)
        finally:
            os.environ.pop("BN_CARDS_DB", None)

    def test_urgent_lookups_jump_backfill(self):
        # Record the worker's pull order: a later urgent cid must run before a queued backfill cid.
        import time
        order = []
        done = []
        def fake(cid, fetch=False):
            order.append(cid)
            time.sleep(0.05)
            return cid
        old = S._story_build
        S._SC.clear()
        try:
            S._story_build = fake
            # drain any leftover worker state
            with S._FLOCK:
                S._FHIGH.clear(); S._FLOW.clear(); S._FWAIT.clear()
            S.submit("backfillcid000001", fetch=True, urgent=False)
            time.sleep(0.01)  # let the worker pick up backfill or not
            S.submit("newstorycid000002", fetch=True, urgent=True)
            S.submit("hitcid0000000003", fetch=True, urgent=True)
            # wait for them
            deadline = time.time() + 3
            while time.time() < deadline and len(order) < 3:
                time.sleep(0.05)
            # The two urgent cids must appear before any remaining backfill if backfill hadn't started,
            # or immediately after the in-flight backfill. Newest urgent (hit) is front of the urgent lane.
            self.assertIn("hitcid0000000003", order)
            self.assertIn("newstorycid000002", order)
            # hit was submitted last with urgent, so it is at the front of the high queue (unless already running)
            hi = [c for c in order if c in ("newstorycid000002", "hitcid0000000003")]
            self.assertEqual(hi[0], "hitcid0000000003", order)
        finally:
            S._story_build = old



    def test_photo_card_survives_version_bump(self):
        """A stored licensed JPEG+credit is reused after og.VERSION changes; a map rebuild must not replace it."""
        import os, tempfile
        from unittest import mock
        import og
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        prev = og.VERSION
        try:
            P._dir = lambda: Path(d)
            jpg = b"\xff\xd8" + b"j" * 3000
            photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            mapp = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            newer = b"\x89PNG\r\n\x1a\n" + b"N" * 4000
            cand = dict(src="https://upload.wikimedia.org/zelensky.jpg", credit="Press Service", license="CC BY 4.0",
                        caption="Volodymyr Zelenskyy, 2025. File photo; not taken at this event.", kind="person", label="lab", link="")
            cid = "9f5bc9d66d783d25"
            P.db_put(cid, cand, jpg=jpg)
            P.put_card(cid, photo, cand["src"])
            self.assertTrue(P.has_photo(cid) and P.card_has_photo(cid))
            og.VERSION = "99"
            self.assertTrue(P.card_stale(P.card_meta(cid)))
            P.put_card(cid, mapp, "")
            self.assertTrue(P.card_has_photo(cid))
            self.assertEqual(P.get_card(cid), photo)
            def fake_build(c, fetch=False):
                P.put_card(c, newer, cand["src"])
                return newer
            S._SC.clear()
            with mock.patch.object(S, "_story_build", side_effect=fake_build):
                out = S.ensure_current_card(cid)
            self.assertEqual(out, newer)
            self.assertTrue(P.card_has_photo(cid))
            self.assertEqual(P.card_meta(cid)["src"], cand["src"])
            self.assertEqual(P.card_meta(cid)["v"], "99")
            self.assertTrue(S._card_headline("— Zelensky says hello").startswith("Zelensky"))
        finally:
            og.VERSION = prev
            os.environ.pop("BN_CARDS_DB", None)

    def test_lookup_timeout_does_not_block_queue(self):
        import time
        order = []
        def fake(cid, fetch=False):
            if cid == "stuckcid00000001":
                time.sleep(8)
            order.append(cid)
            return cid
        old, old_t = S._story_build, S.LOOKUP_TIMEOUT
        S._SC.clear()
        try:
            S._story_build = fake
            S.LOOKUP_TIMEOUT = 0.25
            with S._FLOCK:
                S._FHIGH.clear(); S._FLOW.clear(); S._FWAIT.clear()
            S.submit("stuckcid00000001", fetch=True, urgent=True)
            time.sleep(0.05)
            S.submit("quickcid00000002", fetch=True, urgent=True)
            deadline = time.time() + 3
            while time.time() < deadline and "quickcid00000002" not in order:
                time.sleep(0.05)
            self.assertIn("quickcid00000002", order, order)
        finally:
            S._story_build = old
            S.LOOKUP_TIMEOUT = old_t



    def test_photo_worker_starts_under_render_thread_guard(self):
        """Dockerfile CMD is `python3 render_app.py` (no gunicorn). render_app patches Thread.start
        to silently skip targets whose name contains "loop". The #228/#229 `_floop` worker logged
        "worker started" but never ran. The serving-process worker must start under that exact guard."""
        import os, time, threading
        # Load the exact guard from render_app.py without importing the module (it chdirs to /workspace/blackout).
        src = (Path(__file__).resolve().parents[1] / "render_app.py").read_text()
        start = src.index("BLOCK_THREAD_NAMES =")
        end = src.index("threading.Thread.start = _guarded_start")
        ns = {"threading": threading}
        exec(src[start:end] + "threading.Thread.start = _guarded_start\n", ns)
        orig = threading.Thread.start
        try:
            S._FWORKER = None
            S._FWORKER_PID = None
            S._WORKER_LOGGED = False
            blocked = []
            def _floop():
                blocked.append("ran")
            th = threading.Thread(target=_floop, name="story-photo-old", daemon=True)
            th.start()
            time.sleep(0.05)
            self.assertFalse(th.is_alive(), "legacy _floop target should be blocked by the render_app guard")
            self.assertEqual(blocked, [])
            self.assertTrue(S._ensure_fworker())
            st = S.photo_status()
            self.assertTrue(st["worker"], st)
            self.assertEqual(st.get("pid"), os.getpid())
            self.assertTrue(S._FWORKER and S._FWORKER.is_alive())
        finally:
            threading.Thread.start = orig
            if not (S._FWORKER and S._FWORKER.is_alive()):
                S._FWORKER = None
                S._FWORKER_PID = None
                S._ensure_fworker()

if __name__ == "__main__":
    unittest.main()
