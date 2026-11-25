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
        import os, tempfile, time
        from unittest import mock
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            png = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            jpg = b"\xff\xd8" + b"j" * 3000
            cand = dict(src="https://upload.wikimedia.org/x.jpg", credit="US Treasury", license="Public domain",
                        caption="Scott Bessent, 2025.", kind="person", label="lab", link="")
            P.put_card("e2ca47e325c5b8e1", png, "")  # map card first
            P.db_put("e2ca47e325c5b8e1", cand, jpg=jpg)  # JPEG arrives later; put_card would refuse a map over it
            self.assertTrue(P.has_photo("e2ca47e325c5b8e1"))
            self.assertFalse(P.card_has_photo("e2ca47e325c5b8e1"))
            # Serve the stored map immediately; typography/photo rebuild runs in the background.
            built = []
            def fake_build(cid, fetch=False):
                built.append((cid, fetch))
                photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
                P.put_card(cid, photo, cand["src"])
                return photo
            S._SC.clear()
            with mock.patch.object(S, "_story_build", side_effect=fake_build):
                t0 = time.perf_counter()
                out = S.story_png_fast("e2ca47e325c5b8e1")
                self.assertLess(time.perf_counter() - t0, 2.0)
                self.assertEqual(out, png)
                deadline = time.time() + 3
                while time.time() < deadline and not P.card_has_photo("e2ca47e325c5b8e1"):
                    time.sleep(0.05)
            self.assertTrue(P.card_has_photo("e2ca47e325c5b8e1"))
            self.assertTrue(built and built[0][1] is False, built)
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
                t0 = __import__("time").perf_counter()
                out = S.story_png_fast(cid)
                self.assertLess(__import__("time").perf_counter() - t0, 2.0)
                # Stored photo is served immediately; typography rebuild is background.
                self.assertEqual(out, photo)
                deadline = __import__("time").time() + 3
                while __import__("time").time() < deadline and P.get_card(cid) != newer:
                    __import__("time").sleep(0.05)
            self.assertEqual(P.get_card(cid), newer)
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
        def fake_pre(cid):
            if cid == "stuckcid00000001":
                time.sleep(8)
        def fake_build(cid, fetch=False):
            order.append(cid)
            return cid
        old_pre, old_b, old_t = S._network_prefetch, S._story_build, S.LOOKUP_TIMEOUT
        S._SC.clear()
        try:
            S._network_prefetch = fake_pre
            S._story_build = fake_build
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
            S._network_prefetch = old_pre
            S._story_build = old_b
            S.LOOKUP_TIMEOUT = old_t

    def test_successful_prefetch_does_not_log_timeout(self):
        """A photo=1 prefetch that finishes in time must not then log err=timeout while typography renders."""
        import time
        def fake_pre(cid):
            print(f"story_photo: prefetch {cid} photo=1 license=Public domain kind=person", flush=True)
            time.sleep(0.05)
        def fake_build(cid, fetch=False):
            time.sleep(0.3)
            return cid
        old_pre, old_b, old_t = S._network_prefetch, S._story_build, S.LOOKUP_TIMEOUT
        S._SC.clear()
        try:
            S._network_prefetch = fake_pre
            S._story_build = fake_build
            S.LOOKUP_TIMEOUT = 0.2
            with S._FLOCK:
                S._FHIGH.clear(); S._FLOW.clear(); S._FWAIT.clear()
            fut = S.submit("okcid000000000001", fetch=True, urgent=True)
            fut.result(timeout=3)
            st = S.photo_status()
            self.assertIn("okcid000000000001", st.get("last") or "")
            self.assertNotIn("timeout", st.get("last") or "")
        finally:
            S._network_prefetch = old_pre
            S._story_build = old_b
            S.LOOKUP_TIMEOUT = old_t

    def test_twitterbot_path_never_blocks_over_2s(self):
        """A stored card is returned immediately even if the typography rebuild is slow."""
        import os, tempfile, time
        from unittest import mock
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            cand = dict(src="https://upload.wikimedia.org/zelensky.jpg", credit="Press Service", license="CC BY 4.0",
                        caption="Volodymyr Zelenskyy, 2025.", kind="person", label="lab", link="")
            cid = "9f5bc9d66d783d25"
            P.db_put(cid, cand, jpg=b"\xff\xd8" + b"j" * 3000)
            P.put_card(cid, photo, cand["src"])
            def fake_build(c, fetch=False):
                time.sleep(3)
                return c
            S._SC.clear()
            with mock.patch.object(S, "_story_build", side_effect=fake_build):
                t0 = time.perf_counter()
                out = S.story_png_fast(cid)
                elapsed = time.perf_counter() - t0
            self.assertLess(elapsed, 2.0, elapsed)
            self.assertEqual(out, photo)
        finally:
            os.environ.pop("BN_CARDS_DB", None)



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


    def test_main_subject_huang_not_trump(self):
        """'X wanted Huang back as CEO of Nvidia' is about Huang, not the first named person."""
        title = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        self.assertEqual(P.main_subject(title), "Jensen Huang")
        self.assertFalse(P.is_politician("Jensen Huang"))
        self.assertTrue(P.is_politician("Donald Trump"))
        # Even if the body mentions Trump more, the object-of-wanted role still wins.
        body = "Donald Trump said he would decide later. " + ("Trump " * 4) + "Huang has led Nvidia since 1993."
        self.assertEqual(P.main_subject(title, body), "Jensen Huang")

    def test_main_subject_real_headlines(self):
        self.assertEqual(
            P.main_subject("Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"),
            "Volodymyr Zelensky",
        )
        self.assertEqual(
            P.main_subject("Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz"),
            "Scott Bessent",
        )
        self.assertEqual(
            P.main_subject("Burnham launches inquiry into nuclear bomb test veterans’ records"),
            "Andy Burnham",
        )
        self.assertEqual(
            P.main_subject("Biden nominates Jane Smith as ambassador to France"),
            "Jane Smith",
        )
        # Two principals, no clear role: a coin-flip photo would be likely wrong — use the map.
        self.assertIsNone(P.main_subject("Trump and Zelensky meet in Paris after talks stall"))

    def test_wrong_subject_photo_may_be_replaced(self):
        """The one allowed exception to 'never replace a photo with a map': a wrong-subject photo."""
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "cbdfb48145e55048"
        title = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        P.SUBJECT_HINTS[cid] = (title, "")
        try:
            P._dir = lambda: Path(d)
            trump = b"\x89PNG\r\n\x1a\n" + b"T" * 4000
            huang = b"\x89PNG\r\n\x1a\n" + b"H" * 4000
            mapp = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            trump_src = "https://upload.wikimedia.org/wikipedia/commons/trump.jpg"
            huang_src = "https://upload.wikimedia.org/wikipedia/commons/jensen_huang.jpg"
            P.put_card(cid, trump, trump_src)
            self.assertTrue(P.photo_is_wrong_subject(cid, trump_src, "Donald Trump, 2025"))
            self.assertFalse(P.card_has_photo(cid), "a Trump photo must not count as a usable card for the Huang story")
            # Correct photo may replace the wrong one.
            P.put_card(cid, huang, huang_src)
            self.assertEqual(P.get_card(cid), huang)
            self.assertFalse(P.photo_is_wrong_subject(cid, huang_src, "Jensen Huang, 2025. File photo"))
            # Reset to the wrong photo and allow a map to replace it.
            P.put_card(cid, trump, trump_src)
            P.put_card(cid, mapp, "map")
            self.assertEqual(P.get_card(cid), mapp)
        finally:
            P.SUBJECT_HINTS.pop(cid, None)
            os.environ.pop("BN_CARDS_DB", None)

    def test_correct_photo_still_not_replaced_by_map(self):
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "e2ca47e325c5b8e1"
        title = "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz"
        P.SUBJECT_HINTS[cid] = (title, "")
        try:
            P._dir = lambda: Path(d)
            photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            mapp = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            src = "https://upload.wikimedia.org/wikipedia/commons/bessent.jpg"
            cand = dict(src=src, credit="Example / Wikimedia Commons", license="Public domain",
                        caption="Scott Bessent, 2025. File photo; not taken at this event.",
                        kind="person", label="lab", link="")
            P.db_put(cid, cand, jpg=b"\xff\xd8" + b"j" * 3000)
            P.put_card(cid, photo, src)
            self.assertTrue(P.stored_photo_matches(cid))
            P.put_card(cid, mapp, "map")
            self.assertEqual(P.get_card(cid), photo)
        finally:
            P.SUBJECT_HINTS.pop(cid, None)
            os.environ.pop("BN_CARDS_DB", None)

    def test_rejects_historical_maps_scans_diagrams(self):
        self.assertTrue(P.is_non_photo("File:Map of Altoona Pennsylvania 1939.jpg", "historical map of the city", "Old maps of Pennsylvania", "image/jpeg"))
        self.assertTrue(P.is_non_photo("Scan of a 1910 document", "", "Scanned documents", "application/pdf"))
        self.assertTrue(P.is_non_photo("Org chart of Nvidia", "diagram of reporting lines", "Diagrams", "image/png"))
        self.assertTrue(P.is_non_photo("Press collage of several portraits", "", "Collages", "image/jpeg"))
        self.assertFalse(P.is_non_photo("Jensen huang stanford 2026-04-09 033.jpg", "Portrait of Jensen Huang", "Jen-Hsun Huang in 2026", "image/jpeg"))

    def test_huang_story_gets_portrait_or_designed_map(self):
        """Person-subject stories must not use an irrelevant place photo (the Altoona 1939 map)."""
        import os, tempfile
        from unittest import mock
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "cbdfb48145e55048"
        title = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        loc = "Pennsylvania"
        P.SUBJECT_HINTS[cid] = (title, "")
        portrait = dict(src="https://upload.wikimedia.org/wikipedia/commons/jensen_huang.jpg",
                        credit="Anders Eidesvik / Wikimedia Commons", license="CC BY 4.0",
                        caption="Jensen Huang, 2026. File photo; not taken at this event.",
                        kind="person", alt="Jensen Huang", label="lab", link="")
        altoona = dict(src="https://upload.wikimedia.org/wikipedia/commons/altoona_1939_map.jpg",
                       credit="H.J. Baum / Wikimedia Commons", license="Public domain",
                       caption="Pennsylvania, 1939. File photo; not taken at this event.",
                       kind="place", alt="Pennsylvania", label="lab", link="")
        try:
            P._dir = lambda: Path(d)
            self.assertFalse(P.place_photo_ok(title, ""))
            self.assertTrue(P.is_non_photo("Map of Altoona 1939", "File photo", "Old maps of Pennsylvania", "image/jpeg"))
            # A stored Altoona choice must not be picked for this story.
            P.db_put(cid, altoona, jpg=b"\xff\xd8" + b"m" * 3000)
            self.assertIsNone(P.pick(cid, title, loc, ""))
            # Prefetch must take the Huang portrait, never the place photo.
            with mock.patch.object(P, "_commons_portrait", return_value=portrait), \
                 mock.patch.object(P, "_commons_place", return_value=altoona), \
                 mock.patch.object(P, "store", return_value=Path(d) / "huang.jpg"):
                (Path(d) / "huang.jpg").write_bytes(b"\xff\xd8" + b"h" * 3000)
                got = P.prefetch(cid, title, loc, "")
            self.assertIsNotNone(got)
            self.assertEqual(got["kind"], "person")
            self.assertIn("huang", (got.get("src") or "").lower())
            self.assertNotIn("altoona", (got.get("src") or "").lower())
            # If no licensed portrait exists, fall back to the designed map — not a place photo.
            P.db_put(cid, None, none=True)
            with mock.patch.object(P, "pick", return_value=None), \
                 mock.patch.object(P, "_commons_portrait", return_value=None), \
                 mock.patch.object(P, "_commons_place", return_value=altoona) as place:
                got = P.prefetch(cid, title, loc, "")
            self.assertIsNone(got, "no portrait → designed map, never a place photo")
            place.assert_not_called()
        finally:
            P.SUBJECT_HINTS.pop(cid, None)
            os.environ.pop("BN_CARDS_DB", None)

    def test_title_hash_rebuild_replaces_photo_png(self):
        """A stale-title photo card may be replaced by a typography rebuild of the same JPEG (photo-to-photo)."""
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "9f5bc9d66d783d25"
        raw = "— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"
        clean = S._card_headline(raw)
        self.assertTrue(clean.startswith("Zelensky"))
        self.assertFalse(clean.startswith("—") or clean.startswith("-"))
        stale_key = P.card_title_key(raw)
        fresh_key = P.card_title_key(clean)
        self.assertNotEqual(stale_key, fresh_key)
        try:
            P._dir = lambda: Path(d)
            old = b"\x89PNG\r\n\x1a\n" + b"O" * 4000
            new = b"\x89PNG\r\n\x1a\n" + b"N" * 4000
            src = "https://upload.wikimedia.org/wikipedia/commons/zelensky.jpg"
            P.put_card(cid, old, src, title_hash=stale_key)
            meta = P.card_meta(cid)
            self.assertTrue(P.card_title_stale(meta, fresh_key))
            # Typography rebuild: photo PNG in, photo PNG out, same src, new title hash.
            P.put_card(cid, new, src, title_hash=fresh_key)
            self.assertEqual(P.get_card(cid), new)
            self.assertEqual(P.card_meta(cid)["src"], src)
            self.assertEqual(P.card_meta(cid)["title_hash"], fresh_key)
            self.assertFalse(P.card_title_stale(P.card_meta(cid), fresh_key))
        finally:
            os.environ.pop("BN_CARDS_DB", None)


    def test_strict_match_requires_exact_name_not_topic_words(self):
        """A memorial/drone/vessel photo must not attach to a Libya vessel story."""
        title = "Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel"
        blob = "Ukraine Russia, 2023. File photo. The Goddess Themis stands with Ukraine. memorial candles"
        self.assertFalse(P.exact_subject_in(blob, title, ""))
        memorial = dict(src="https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg",
                        credit="Latvian pagan / Wikimedia Commons", license="CC0",
                        caption="Ukraine Russia, 2023. File photo; not taken at this event.",
                        kind="place", alt="Ukraine", label="lab", link="")
        self.assertFalse(P.photo_strict_match("4c292ccdd9df73f8", src=memorial["src"], meta_blob=" ".join((memorial["caption"], memorial["credit"])),
                                             title=title, kind="place"))
        # Exact landmark still matches.
        pif = "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days"
        self.assertTrue(P.exact_subject_in("File:Public Investment Fund Tower, Riyadh.jpg | Categories: PIF Tower", pif, ""))
        # Exact person in Commons title/categories.
        huang_title = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        self.assertTrue(P.exact_subject_in("File:Jensen huang stanford 2026-04-30 008.jpg | Jen-Hsun Huang in 2026", huang_title, ""))
        self.assertFalse(P.exact_subject_in("File:Map of Altoona Pennsylvania 1939.jpg | Old maps of Pennsylvania", huang_title, ""))

    def test_commons_portrait_queries_use_full_name_and_category(self):
        qs = P.commons_portrait_queries("Jensen Huang")
        self.assertEqual(qs[0], '"Jensen Huang"')
        self.assertEqual(qs[1], "Jensen Huang")
        self.assertIn('deepcategory:"Jensen Huang"', qs)
        self.assertIn('deepcategory:"Jen-Hsun Huang"', qs)
        self.assertIn('incategory:"Jensen Huang"', qs)

    def test_audit_downgrades_mismatch_to_map(self):
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "4c292ccdd9df73f8"
        title = "Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel"
        P.SUBJECT_HINTS[cid] = (title, "")
        try:
            P._dir = lambda: Path(d)
            photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            mapp = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            src = "https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg"
            cand = dict(src=src, credit="Latvian pagan / Wikimedia Commons", license="CC0",
                        caption="Ukraine Russia, 2023. File photo; not taken at this event.",
                        kind="place", label="lab", link="")
            P.db_put(cid, cand, jpg=b"\xff\xd8" + b"j" * 3000)
            P.put_card(cid, photo, src, title_hash="old")
            self.assertFalse(P.stored_photo_matches(cid))
            self.assertFalse(P.card_has_photo(cid))
            # A map downgrade of a wrong photo is allowed.
            P.put_card(cid, mapp, "", title_hash="new")
            self.assertEqual(P.get_card(cid), mapp)
            self.assertFalse(P.card_has_photo(cid))
        finally:
            P.SUBJECT_HINTS.pop(cid, None)
            os.environ.pop("BN_CARDS_DB", None)

    def test_empty_title_hash_is_stale(self):
        meta = {"png": b"x", "v": "17", "src": "https://example.com/z.jpg", "title_hash": ""}
        self.assertTrue(P.card_title_stale(meta, "abc123"))
        self.assertTrue(P.card_title_stale(meta, ""))
        meta["title_hash"] = "abc123"
        self.assertFalse(P.card_title_stale(meta, "abc123"))
        self.assertTrue(P.card_title_stale(meta, "fff999"))


    def test_ensure_current_card_rereads_db_not_stale_memory(self):
        """The in-memory _SC cache must not hide an audit downgrade of the Libya card (or typography of Zelensky)."""
        import os, tempfile
        from pathlib import Path
        import share_card as S
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        libya, zel = "4c292ccdd9df73f8", "9f5bc9d66d783d25"
        P.SUBJECT_HINTS[libya] = ("Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel", "")
        P.SUBJECT_HINTS[zel] = ("Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine", "")
        try:
            P._dir = lambda: Path(d)
            memorial = b"\x89PNG\r\n\x1a\n" + b"U" * 4000
            mapp = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            dashed = b"\x89PNG\r\n\x1a\n" + b"D" * 4000
            cleaned = b"\x89PNG\r\n\x1a\n" + b"C" * 4000
            src_l = "https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg"
            src_z = "https://upload.wikimedia.org/wikipedia/commons/zelensky.jpg"
            P.db_put(libya, dict(src=src_l, credit="Latvian pagan / Wikimedia Commons", license="CC0",
                                 caption="Ukraine Russia, 2023. File photo.", kind="place", label="lab", link=""),
                     jpg=b"\xff\xd8" + b"j" * 3000)
            P.put_card(libya, memorial, src_l, title_hash="old")
            P.db_put(zel, dict(src=src_z, credit="Press Service / Wikimedia Commons", license="CC BY 4.0",
                               caption="Volodymyr Zelensky, 2025. File photo.", kind="person", label="lab", link=""),
                     jpg=b"\xff\xd8" + b"z" * 3000)
            P.put_card(zel, dashed, src_z, title_hash="stale")
            S._SC[libya] = (0, memorial, False)
            S._SC[zel] = (0, dashed, False)
            self.assertFalse(P.stored_photo_matches(libya))
            # Simulate audit persist + typography without depending on resolve/network.
            P.put_card(libya, mapp, "", title_hash="new")
            P.put_card(zel, cleaned, src_z, title_hash=P.card_title_key("Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"))
            # Even if _SC still held the old bytes, ensure_current_card must re-read cards.db.
            self.assertEqual(S.ensure_current_card(libya), mapp)
            self.assertEqual(S.ensure_current_card(zel), cleaned)
            self.assertEqual(S.story_png_fast(libya), mapp)
        finally:
            P.SUBJECT_HINTS.pop(libya, None)
            P.SUBJECT_HINTS.pop(zel, None)
            S._SC.pop(libya, None)
            S._SC.pop(zel, None)
            os.environ.pop("BN_CARDS_DB", None)

    def test_cold_miss_serves_generic_designed_card_under_one_second(self):
        """A cache miss must not wait for a unique locator render (those were 5–7 s). Generic 1200x675, never earth."""
        import os, tempfile, time, struct
        from pathlib import Path
        from unittest import mock
        import share_card as S
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "c0ldc0ldc0ldc0ld"
        try:
            P._dir = lambda: Path(d)
            S._SC.pop(cid, None)
            def slow_build(c, fetch=False):
                time.sleep(2.5)
                return b"\x89PNG\r\n\x1a\n" + b"S" * 4000
            generic = b"\x89PNG\r\n\x1a\n" + bytes([0, 0, 0, 13, 73, 72, 68, 82]) + b"G" * 4000
            # A real PNG IHDR is nicer; generic_story_card is mocked.
            with mock.patch.object(S, "generic_story_card", return_value=b"\x89PNG\r\n\x1a\n" + b"G" * 4000), \
                 mock.patch.object(S, "_story_build", side_effect=slow_build), \
                 mock.patch.object(S, "submit", return_value=None):
                t0 = time.perf_counter()
                out = S.story_png_fast(cid)
                elapsed = time.perf_counter() - t0
                self.assertLess(elapsed, 1.0)
                self.assertTrue(out and out.startswith(b"\x89PNG"))
                self.assertGreater(len(out), 2000)
                # 1200x630 earth is not served here; this is a designed 1200x675 stand-in (body is our generic mock).
                self.assertEqual(out, b"\x89PNG\r\n\x1a\n" + b"G" * 4000)
        finally:
            S._SC.pop(cid, None)
            os.environ.pop("BN_CARDS_DB", None)


if __name__ == "__main__":
    unittest.main()
