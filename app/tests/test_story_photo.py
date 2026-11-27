import io, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_photo as P
import share_card as S


class StoryPhoto(unittest.TestCase):
    def test_license_gate(self):
        for ok in ("Public domain", "Public domain (U.S. government work)", "CC0", "CC BY 3.0", "CC BY 4.0", "OGL 3", "CC BY 2.0", "CC BY-SA 4.0", "CC BY-SA 3.0"):
            self.assertTrue(P.license_ok(ok), ok)
        for bad in ("", "CC BY-NC 4.0", "CC BY-NC-SA 4.0", "CC BY-ND 2.0", "All rights reserved", "Fair use"):
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
            "Ethiopia launches polio vaccination campaign to protect more than 11 million children: WHO deployed 28 staff",
            "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using…",
        ]
        for raw in titles:
            t = S._card_headline(raw)
            for maxw in (640, 700):
                f, size, lines = S._story_head(d, t, maxw)
                joined = " ".join(lines)
                self.assertLessEqual(len(lines), 3, raw)
                self.assertGreaterEqual(size, S.HEAD_MIN, (raw, size))
                self.assertFalse(any("…" in l or l.endswith("...") for l in lines), raw)
                self.assertNotIn("…", joined)
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

    def test_hegseth_pentagon_headline_is_not_ambiguous(self):
        """Junk bigrams must not hide Pete Hegseth as the subject (live map-card regression)."""
        title = "On Monday, U.S. Secretary of War Pete Hegseth will receive Turkish Minister of National Defense Yaşar Güler at the Pentagon."
        names = P._named_people("e9a491a27092837f", title, "")
        self.assertEqual(names, ["Pete Hegseth"])
        self.assertEqual(P.main_subject(title, ""), "Pete Hegseth")
        self.assertNotIn("Turkish Minister", names)
        self.assertNotIn("National Defense", names)

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
            cand = dict(src="https://upload.wikimedia.org/wikipedia/commons/Scott_Bessent.jpg", credit="US Treasury", license="Public domain",
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

    def test_card_headline_does_not_cut_at_us_abbreviation(self):
        """'U.S.' / 'U.K.' is not the end of the sentence (Hegseth Pentagon card was cut to 'On Monday, U.S')."""
        h = S._card_headline(
            "On Monday, U.S. Secretary of War Pete Hegseth will receive Turkish Minister of National Defense Yaşar Güler at the Pentagon. @IntelSlava"
        )
        self.assertTrue(h.startswith("On Monday, U.S. Secretary of War Pete Hegseth"), h)
        self.assertIn("Pentagon", h)
        self.assertNotEqual(h, "On Monday, U.S")
        self.assertNotIn("@IntelSlava", h)
        two = S._card_headline("The U.K. Prime Minister arrived in Paris. France issued a statement.")
        self.assertEqual(two, "The U.K. Prime Minister arrived in Paris")

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
            src = "https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg"
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
            cand = dict(src="https://upload.wikimedia.org/wikipedia/commons/Scott_Bessent.jpg", credit="US Treasury", license="Public domain",
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
            # The convert worker may scan this map card at the same time; no network lookup in a unit test.
            with mock.patch.object(S, "_story_build", side_effect=fake_build), mock.patch.object(S, "apply_card_photo", return_value=None):
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

    # ---- no map cards (Nov 25 2026, 4:47 PM ET)
    def test_story_bg_never_draws_a_map(self):
        from unittest import mock
        it = dict(kind="story", id="t9", title="IMO: M3.5 earthquake, Iceland", rank=2, color=S.AMBER, kicker="NATURAL DISASTER", loc="Iceland",
                  art=("story", -19.0, 64.9, None), photo=None, stats=[], tags=[])
        with mock.patch.object(S, "_map", side_effect=AssertionError("map drawn")):
            im, portrait, credit, label = S._story_bg(it)
            self.assertEqual(im.size, (1200, 675))
            self.assertEqual((credit, label), ("", ""))
            self.assertEqual(S._lay_story(it).size, (1200, 675))

    def test_fallback_key_hazard_then_category_then_general(self):
        import card_photo as CP
        self.assertEqual(CP.fallback_key("Volcanic ash advisory: Telica ash cloud up to 5,000 ft", "", "natural disaster"), "volcano")
        self.assertEqual(CP.fallback_key("Hackers breach 1Password", "", "cyber"), "cyber")
        self.assertEqual(CP.fallback_key("Reports of 70 missiles prepared in Russia", "", "war/conflict"), "military")
        self.assertEqual(CP.fallback_key("Shares slide as inflation rises", "", "markets"), "economy")
        self.assertEqual(CP.fallback_key("Iran talks stall in Geneva", "", "politics"), "general")      # not the U.S. Capitol
        self.assertEqual(CP.fallback_key("Senate votes on the budget", "", "politics"), "government")
        self.assertEqual(CP.fallback_key("Something happened", "", ""), "general")
        for k in ("military", "aviation", "grid", "economy", "spaceweather", "government", "general"):
            self.assertIn(k, CP.TOPICS)
            self.assertIn(k, CP.FALLBACK_KEYS)

    def test_choose_ends_with_category_photo_not_none(self):
        from unittest import mock
        import card_photo as CP
        seen = []
        def topic(text, seed="", key=None, except_cid=""):
            seen.append((text, key))
            return dict(src="https://x/y.jpg", path="/tmp/none", kind="topic", label="L", license="Public domain", credit="c") if key else None
        with mock.patch.object(CP, "person_photo", return_value=None), mock.patch.object(CP, "place_photo", return_value=None), \
             mock.patch.object(CP, "topic_photo", side_effect=topic), mock.patch.object(CP, "fetch", side_effect=lambda im: "/tmp/none"):
            im = CP.choose("c1", "Something happened", None, "", "war/conflict")
        self.assertIsNotNone(im)
        self.assertEqual(seen[-1][1], "military")

    def test_fallback_topic_photos_are_allowed_by_the_audit(self):
        import card_photo as CP
        for key, (_a, files, _n) in CP.TOPICS.items():
            ft = files[0].replace("File:", "").replace("_", " ")
            ok, why = P._v3_photo_allows("Totally unrelated headline", ft, kind="topic", text="")
            if key in CP.FALLBACK_KEYS:
                self.assertTrue(ok, (key, why))

    def test_us_default_place_is_not_used_for_a_story_with_no_us_word(self):
        from unittest import mock
        import card_photo as CP
        got = {}
        def choose(cid, title, hit=None, text="", category=""):
            got["hit"] = hit
            return None
        us = {"place": "United States", "lat": 38.9, "lon": -77.0, "cc": "US", "precision": "country"}
        with mock.patch.object(S, "story_map_hit", return_value=us), mock.patch.object(CP, "choose", side_effect=choose):
            S.apply_card_photo("c2", "Volcanic ash advisory: Telica ash cloud up to 5,000 ft", "Nicaragua", "", None, None, "natural disaster")
            self.assertIsNone(got["hit"])
            S.apply_card_photo("c3", "Pentagon says drills continue", "", "", None, None, "politics")
            self.assertEqual(got["hit"], us)

    def test_convert_queue_skips_a_card_tried_recently(self):
        from unittest import mock
        rows = [dict(cid="aaaaaaaaaaaaaaaa", v="24M", src="", title_hash=""), dict(cid="bbbbbbbbbbbbbbbb", v="24M", src="", title_hash="")]
        S._CONVERT_TRIED.clear()
        with mock.patch.object(P, "card_heads", return_value=rows):
            self.assertEqual(S._pending_convert_cids(), ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"])
            S._CONVERT_TRIED["aaaaaaaaaaaaaaaa"] = __import__("time").time()
            self.assertEqual(S._pending_convert_cids(), ["bbbbbbbbbbbbbbbb"])
        S._CONVERT_TRIED.clear()

    def test_og_image_url_changes_with_the_stored_card(self):
        from unittest import mock
        import og
        with mock.patch.object(P, "card_tag", return_value="abc12345"):
            u1 = og.image_url(story_id="e9a491a27092837f", title="T", rank=2)
        with mock.patch.object(P, "card_tag", return_value="ffff0000"):
            u2 = og.image_url(story_id="e9a491a27092837f", title="T", rank=2)
        with mock.patch.object(P, "card_tag", return_value=""):
            u3 = og.image_url(story_id="e9a491a27092837f", title="T", rank=2)
        self.assertTrue(u1.endswith("-abc12345"), u1)
        self.assertNotEqual(u1, u2)
        self.assertNotIn("abc12345", u3)

    def test_card_tag_is_metadata_only_and_tracks_src(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            png = b"\x89PNG\r\n\x1a\n" + b"M" * 4000
            self.assertEqual(P.card_tag("0123456789abcdef"), "")
            P.put_card("0123456789abcdef", png, "")
            t1 = P.card_tag("0123456789abcdef")
            P.put_card("0123456789abcdef", png, "https://upload.wikimedia.org/x.jpg")
            t2 = P.card_tag("0123456789abcdef")
            self.assertTrue(t1 and t2 and t1 != t2)
        finally:
            os.environ.pop("BN_CARDS_DB", None)

    def test_pick_keeps_v3_place_and_topic_photos_so_prefetch_does_not_wipe_them(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        try:
            P._dir = lambda: Path(d)
            place = dict(src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Iceland_ESA.jpg/1600px-Iceland_ESA.jpg", credit="European Space Agency / Wikimedia Commons",
                         license="Attribution", caption="Iceland. File photo; not taken at this event.", kind="place", label="Iceland. File photo; not taken at this event.", link="")
            P.db_put("1111111111111111", place, jpg=b"\xff\xd8" + b"j" * 3000)
            c = P.pick("1111111111111111", "Talks open in Iceland on a new North Atlantic trade pact", "Iceland", "")
            self.assertIsNotNone(c)
            self.assertEqual(c["kind"], "place")
            topic = dict(src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/B-2_Spirit_original.jpg/1600px-B-2_Spirit_original.jpg", credit="U.S. Air Force photo / Wikimedia Commons",
                         license="Public domain", caption="Military aircraft (U.S. Air Force). File photo; not taken at this event.", kind="topic",
                         label="Military aircraft (U.S. Air Force). File photo; not taken at this event.", link="")
            P.db_put("2222222222222222", topic, jpg=b"\xff\xd8" + b"j" * 3000)
            c = P.pick("2222222222222222", "Reports of 70 missiles prepared for launch in Russia", "", "")
            self.assertIsNotNone(c)
            self.assertEqual(c["kind"], "topic")
        finally:
            os.environ.pop("BN_CARDS_DB", None)

    def test_topic_and_place_photos_are_never_wrong_subject_even_when_the_headline_names_a_bigram(self):
        t = "BREAKING: Hackers breach 1Password's backend systems after compromising an employee's GitHub account"
        src = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/BalticServers_data_center.jpg/1600px-BalticServers_data_center.jpg"
        self.assertFalse(P.photo_is_wrong_subject("3333333333333333", src, "Server racks", t, "", kind="topic"))
        self.assertFalse(P.photo_is_wrong_subject("3333333333333333", src, "Iceland", "Scott Bessent and Jerome Powell meet", "", kind="place"))
        # a person photo on an ambiguous two-person headline is still wrong
        self.assertTrue(P.photo_is_wrong_subject("3333333333333333", "https://x/Scott_Bessent.jpg", "", "Scott Bessent and Jerome Powell meet", "", kind="person"))

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
            cand = dict(src="https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg", credit="Press Service", license="CC BY 4.0",
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
            self.assertEqual(P.card_meta(cid)["v"], "99MP")
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
            cand = dict(src="https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg", credit="Press Service", license="CC BY 4.0",
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
            src = "https://upload.wikimedia.org/wikipedia/commons/Scott_Bessent.jpg"
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


    def test_is_map_like_rejects_relief_and_satellite_place_photos(self):
        """NASA relief renderings and ESA satellite country views are not ground-level place photos."""
        import card_photo as CP
        self.assertTrue(CP.is_map_like(
            filename="File:New Zealand, NASA.jpg",
            credit="NASA/JPL/NIMA",
            desc="Shaded relief rendering of New Zealand, 2000",
        ))
        self.assertTrue(CP.is_map_like(
            filename="File:Iceland from space.jpg",
            credit="ESA/Envisat",
            desc="Satellite view of Iceland",
        ))
        self.assertTrue(P.is_non_photo(
            "New Zealand, NASA.jpg", "NASA/JPL/NIMA. File photo of New Zealand (2000).", "NASA images", "image/jpeg"))
        self.assertTrue(P.is_non_photo(
            "Iceland Envisat.jpg", "ESA satellite image of Iceland", "Satellite pictures of Iceland", "image/jpeg"))
        self.assertFalse(CP.is_map_like(
            filename="File:Pete Hegseth official portrait.jpg",
            credit="U.S. Department of Defense",
            desc="Official portrait of Pete Hegseth, 2025",
        ))
        self.assertFalse(P.is_non_photo(
            "Jensen huang stanford 2026-04-09 033.jpg", "Portrait of Jensen Huang", "Jen-Hsun Huang in 2026", "image/jpeg"))
        self.assertFalse(CP.is_map_like(desc="Aid workers deliver disaster relief in Auckland"))

    def test_pick_rejects_a_stored_satellite_place_photo(self):
        """A stored v3 place photo that is a satellite/relief view is not kept."""
        import card_photo as CP
        cid = "d9c1418515395db1"
        cand = {
            "src": "https://upload.wikimedia.org/wikipedia/commons/8/8a/New_Zealand_NASA.jpg",
            "credit": "NASA/JPL/NIMA / Wikimedia Commons",
            "license": "Public domain",
            "kind": "place",
            "label": "New Zealand. File photo; not taken at this event.",
            "title": "New Zealand, NASA.jpg",
            "caption": "Shaded relief rendering of New Zealand",
        }
        self.assertTrue(CP.is_map_like(filename=cand["title"], credit=cand["credit"], desc=cand["caption"], src=cand["src"]))
        self.assertTrue(P.is_non_photo_candidate(cand))
        from unittest import mock
        with mock.patch.object(P, "stored_choice", return_value=cand), mock.patch.object(P, "db_choice", return_value=cand):
            self.assertIsNone(P.pick(cid, "M 4.8 - 190 km N of Hicks Bay, New Zealand", "New Zealand", ""))



    def test_skip_place_photo_for_hazard_stories_not_conflict(self):
        import card_photo as CP
        self.assertTrue(CP.skip_place_photo("M 4.8 - 190 km N of Hicks Bay, New Zealand"))
        self.assertTrue(CP.skip_place_photo("IMO: M3.5 earthquake, Iceland"))
        self.assertTrue(CP.skip_place_photo("Volcanic ash advisory: Telica ash cloud up to 5,000 ft"))
        self.assertFalse(CP.skip_place_photo(
            "On Monday, U.S. Secretary of War Pete Hegseth will receive Turkish Minister of National Defense Yaşar Güler",
            "", "conflict"))

    def test_pick_rejects_a_stored_culture_place_photo_on_an_earthquake(self):
        """A haka / culture place photo must not be kept on a disaster card."""
        from unittest import mock
        import story_photo as P
        cid = "d9c1418515395db1"
        title = "M 4.8 - 190 km N of Hicks Bay, New Zealand"
        stored = {
            "kind": "place",
            "src": "https://upload.wikimedia.org/wikipedia/commons/8/8a/Kapa_haka.jpg",
            "title": "File:Kapa haka.jpg",
            "license": "CC BY-SA 4.0",
            "credit": "Raymonst3 / Wikimedia Commons",
            "label": "New Zealand",
            "link": "https://commons.wikimedia.org/wiki/File:Kapa_haka.jpg",
        }
        with mock.patch.object(P, "stored_choice", return_value=stored), \
             mock.patch.object(P, "db_choice", return_value=stored), \
             mock.patch.object(P, "license_ok", return_value=True), \
             mock.patch.object(P, "is_non_photo_candidate", return_value=False), \
             mock.patch.object(P, "photo_is_wrong_subject", return_value=False), \
             mock.patch.object(P, "photo_strict_match", return_value=True), \
             mock.patch.object(P, "place_photo_ok", return_value=True), \
             mock.patch.object(P, "_v3_photo_allows", return_value=(True, "place:New Zealand")), \
             mock.patch.object(P, "main_subject", return_value=None), \
             mock.patch.object(P, "_named_people", return_value=[]):
            self.assertIsNone(P.pick(cid, title, "190 km N of Hicks Bay, New Zealand", ""))

    def test_choose_skips_place_and_uses_topic_on_earthquake(self):
        from unittest import mock
        import card_photo as CP
        place = {"kind": "place", "src": "https://example.com/haka.jpg", "title": "File:Kapa haka.jpg",
                 "label": "New Zealand", "license": "CC BY-SA 4.0"}
        topic = {"kind": "topic", "src": "https://example.com/quake.jpg", "title": "File:1933 Long Beach earthquake damage 1.jpg",
                 "hazard": "quake", "label": "Earthquake damage (USGS).", "license": "CC BY-SA 4.0",
                 "path": "/tmp/quake.jpg"}
        with mock.patch.object(CP, "person_photo", return_value=None), \
             mock.patch.object(CP, "place_photo", return_value=place) as pp, \
             mock.patch.object(CP, "topic_photo", return_value=topic), \
             mock.patch.object(CP, "fetch", side_effect=lambda im: im.get("path") or "/tmp/x.jpg"):
            got = CP.choose("d9c1418515395db1", "M 4.8 - 190 km N of Hicks Bay, New Zealand",
                            hit={"place": "New Zealand", "cc": "NZ"}, text="", category="natural disaster")
        self.assertIsNotNone(got)
        self.assertEqual(got.get("kind"), "topic")
        self.assertEqual(got.get("hazard"), "quake")
        pp.assert_not_called()

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
            src = "https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg"
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

    def test_audit_deletes_mismatch_photo_row(self):
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        cid = "4c292ccdd9df73f8"
        title = "Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel"
        P.SUBJECT_HINTS[cid] = (title, "")
        P.AUDIT.update(checked=0, deleted=0, downgraded=0, typography=0, done=False, error="", deleted_cids=[])
        try:
            P._dir = lambda: Path(d)
            photo = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            src = "https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg"
            cand = dict(src=src, credit="Latvian pagan / Wikimedia Commons", license="CC0",
                        caption="Ukraine Russia, 2023. File photo; not taken at this event.",
                        kind="place", label="lab", link="")
            P.db_put(cid, cand, jpg=b"\xff\xd8" + b"j" * 3000)
            P.put_card(cid, photo, src, title_hash="old")
            self.assertFalse(P.stored_photo_matches(cid))
            # Deleting the photo AND the card is required; a map downgrade leaves the JPEG for the worker.
            self.assertTrue(P.delete_stored_photo(cid))
            self.assertIsNone(P.db_choice(cid))
            self.assertIsNone(P.get_card(cid))
            self.assertIsNone(P.card_meta(cid))
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
            src_z = "https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg"
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


    def test_official_event_src_is_not_any_story_report_image(self):
        """A leftover Commons file bound in story_report images is stored metadata, not a match."""
        cid = "4c292ccdd9df73f8"
        src = "https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg"
        from unittest import mock
        import story_report as SR
        with mock.patch.object(SR, "reports", return_value={"images": {cid: [{"src": src, "license": "CC0"}]}}):
            self.assertFalse(P.official_event_src(cid, src))
        self.assertTrue(P.official_event_src(cid, "https://earthquake.usgs.gov/product/shakemap/us7000/download/intensity.jpg"))

    def test_story_head_strips_leading_emdash(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        raw = "— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"
        f, size, lines = S._story_head(d, raw, 640)
        joined = " ".join(lines)
        self.assertTrue(joined.startswith("Zelensky"), joined)
        self.assertFalse(joined.lstrip().startswith("—"))
        self.assertFalse(joined.lstrip().startswith("-"))

    def test_force_rebuild_rewrites_live_libya_zelensky_huang_rows(self):
        """The 3 exact live cards.db rows. Audit alone can skip them (story_report official-src
        short-circuit, a title_hash that already matches the cleaned headline, a map not in
        photo_cids / has_photo skip). force_rebuild_listed_cards must rewrite all three."""
        import os, tempfile
        from unittest import mock
        from PIL import Image
        import story_report as SR
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        libya, zel, huang = "4c292ccdd9df73f8", "9f5bc9d66d783d25", "cbdfb48145e55048"
        libya_title = "Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel"
        zel_raw = "— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"
        zel_clean = S._card_headline(zel_raw)
        self.assertTrue(zel_clean.startswith("Zelensky"))
        huang_title = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        stories = {
            libya: dict(title=libya_title, brief="", rank=7, location="Libya", category="War/Conflict",
                        lat=None, lon=None, families="", watchlist=0, hidden=0),
            zel: dict(title=zel_raw, brief="", rank=6, location="Ukraine", category="War/Conflict",
                      lat=None, lon=None, families="", watchlist=0, hidden=0),
            huang: dict(title=huang_title, brief="", rank=4, location="Pennsylvania", category="People",
                        lat=None, lon=None, families="", watchlist=0, hidden=0),
        }
        P.SUBJECT_HINTS[libya] = (libya_title, "")
        P.SUBJECT_HINTS[zel] = (zel_raw, "")
        P.SUBJECT_HINTS[huang] = (huang_title, "")
        P.REBUILD.update(done=False, ids=0, error="")
        memorial_src = "https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg"
        zel_src = "https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg"
        huang_src = "https://upload.wikimedia.org/wikipedia/commons/Jensen_Huang.jpg"
        jpg_mem = d + "/mem.jpg"
        jpg_zel = d + "/zel.jpg"
        jpg_huang = d + "/huang.jpg"
        Image.new("RGB", (1200, 800), (80, 120, 40)).save(jpg_mem, "JPEG")
        Image.new("RGB", (900, 1200), (40, 30, 20)).save(jpg_zel, "JPEG")
        Image.new("RGB", (900, 1200), (20, 30, 40)).save(jpg_huang, "JPEG")
        memorial_png = b"\x89PNG\r\n\x1a\n" + b"MEMORIAL" * 500
        dashed_png = b"\x89PNG\r\n\x1a\n" + b"DASHEDZEL" * 500
        map_png = b"\x89PNG\r\n\x1a\n" + b"HUANGMAP" * 500
        portrait = dict(src=huang_src, credit="Author / Wikimedia Commons", license="CC BY 4.0",
                        caption="Jensen Huang, 2024. File photo; not taken at this event.",
                        kind="person", title="File:Jensen huang stanford 2026-04-30 008.jpg",
                        categories="Jen-Hsun Huang", alt="Jensen Huang", label="lab", link="")

        def fake_load(cid):
            r = stories.get(cid)
            return (dict(r), []) if r else (None, [])

        def fake_store(src):
            path = Path(d) / (P._name(src) + ".jpg")
            src_l = (src or "").lower()
            src_path = jpg_huang if "huang" in src_l else jpg_zel if "zelensky" in src_l else jpg_mem
            import shutil
            if not path.exists() or path.stat().st_size < 2000:
                shutil.copyfile(src_path, path)
            return path

        try:
            P._dir = lambda: Path(d)
            P.db_put(libya, dict(src=memorial_src, credit="Latvian pagan / Wikimedia Commons", license="CC0",
                                 caption="Ukraine Russia, 2023. File photo; not taken at this event.",
                                 kind="place", label="lab", link=""),
                     jpg=Path(jpg_mem).read_bytes())
            # title_hash already "current" so typography-only audit would skip Zelensky
            P.put_card(libya, memorial_png, memorial_src, title_hash=P.card_title_key(libya_title))
            P.db_put(zel, dict(src=zel_src, credit="Press Service / Wikimedia Commons", license="CC BY 4.0",
                               caption="Volodymyr Zelensky, 2025. File photo.",
                               kind="person", label="lab", link=""),
                     jpg=Path(jpg_zel).read_bytes())
            P.put_card(zel, dashed_png, zel_src, title_hash=P.card_title_key(zel_clean))
            P.put_card(huang, map_png, "", title_hash=P.card_title_key(huang_title))
            S._SC[libya] = (0, memorial_png, False)
            S._SC[zel] = (0, dashed_png, False)
            S._SC[huang] = (0, map_png, False)

            # story_report binding used to make official_event_src True (the stored-metadata trap).
            with mock.patch("story.load", side_effect=fake_load), \
                 mock.patch.object(SR, "reports", return_value={"images": {libya: [{"src": memorial_src, "license": "CC0"}]}}), \
                 mock.patch.object(P, "_commons_portrait", return_value=portrait), \
                 mock.patch.object(P, "store", side_effect=fake_store):
                # Simulate the live persist miss: audit typography/_story_build does not rewrite
                # the stored PNG (og cache / resolve miss). The generic-map fallback still runs
                # for a rematched mismatch, which is the official_event_src fix.
                def no_persist(cid, fetch=False):
                    return P.get_card(cid)
                with mock.patch.object(S, "_story_build", side_effect=no_persist):
                    downgraded = S.audit_stored_photo_cards()
                self.assertGreaterEqual(downgraded, 1)
                self.assertFalse(P.card_has_photo(libya))
                # Zelensky typography did not persist (same dashed stub).
                self.assertEqual(P.get_card(zel), dashed_png)
                # Huang is a map, not in photo_cids, so the audit does not look up a portrait.
                self.assertEqual(P.get_card(huang), map_png)
                self.assertFalse(P.card_has_photo(huang))

                S.force_rebuild_listed_cards(force=True)

                # Libya: designed map, memorial gone.
                self.assertFalse(P.card_has_photo(libya))
                meta_l = P.card_meta(libya) or {}
                self.assertFalse((meta_l.get("src") or "").startswith("https://"))
                self.assertNotEqual(P.get_card(libya), memorial_png)
                self.assertTrue(P.get_card(libya) and P.get_card(libya).startswith(b"\x89PNG"))

                # Zelensky: typography rebuilt from the JPEG with the cleaned title (no leading dash).
                self.assertTrue(P.card_has_photo(zel))
                self.assertNotEqual(P.get_card(zel), dashed_png)
                self.assertEqual((P.card_meta(zel) or {}).get("title_hash"), P.card_title_key(zel_clean))
                captured = []
                real_head = S._story_head
                def spy_head(d2, title, maxw, max_lines=3, start=54, minsize=S.HEAD_MIN):
                    captured.append(title)
                    return real_head(d2, title, maxw, max_lines, start, minsize)
                with mock.patch.object(S, "_story_head", side_effect=spy_head):
                    S.invalidate_card_layers(zel)
                    fresh = S.render_story_fresh(zel)
                self.assertTrue(fresh and fresh.startswith(b"\x89PNG"))
                self.assertTrue(any(S._card_headline(t or "").startswith("Zelensky") for t in captured) or not captured)
                # The painted headline must not start with an em-dash (spy sees the raw arg; _story_head strips).
                from PIL import Image as _Im, ImageDraw as _Id
                dd = _Id.Draw(_Im.new("RGB", (10, 10)))
                _, _, lines = S._story_head(dd, zel_raw, 640)
                self.assertTrue(" ".join(lines).startswith("Zelensky"))

                # Jensen Huang is in the PEOPLE list; force-rebuild lands the licensed portrait, not a map.
                self.assertTrue(P.card_has_photo(huang))
                self.assertNotEqual(P.get_card(huang), map_png)
                self.assertTrue(P.get_card(huang) and P.get_card(huang).startswith(b"\x89PNG"))
                place, _, _ = S.story_map_place(huang_title, location="Pennsylvania", brief="")
                self.assertTrue(not place or "pennsylvania" not in place.lower(), place)
        finally:
            for k in (libya, zel, huang):
                P.SUBJECT_HINTS.pop(k, None)
                S._SC.pop(k, None)
            P.REBUILD.update(done=False, ids=0, error="")
            os.environ.pop("BN_CARDS_DB", None)


    def test_photo_rule_allows_only_named_person_or_shakemap_or_pif(self):
        """Commons file title must contain the person's full name; topic/place photos are maps."""
        libya = "Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel"
        self.assertEqual(P.photo_rule_allows(libya, commons_title="The Goddess Themis stands with Ukraine.jpg",
                                             src="https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg")[0], False)
        # Caption or story title leaked into metadata must not count.
        self.assertFalse(P.photo_strict_match("4c292ccdd9df73f8",
                                              src="https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg",
                                              meta_blob=libya + " Ukraine Russia, 2023",
                                              title=libya, commons_title="themis ukraine.jpg"))
        gaza = "Gaza's Health Ministry has declared an epidemic alert across the territory over a rapid rise in meningitis"
        self.assertEqual(P.photo_rule_allows(gaza, commons_title="Ilan Meiri 1980 portrait.jpg",
                                             src="https://upload.wikimedia.org/wikipedia/commons/Ilan_Meiri_1980.jpg")[0], False)
        zel = "Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"
        self.assertTrue(P.photo_rule_allows(zel, commons_title="Volodymyr Zelenskyy 2025.jpg",
                                            src="https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg")[0])
        # Surname-only file title is not enough.
        self.assertFalse(P.photo_rule_allows(zel, commons_title="zelensky.jpg",
                                             src="https://upload.wikimedia.org/wikipedia/commons/zelensky.jpg")[0])
        huang = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        # Jensen Huang is in the hashtag PEOPLE list, so a portrait whose file title has the full name is allowed.
        self.assertTrue(P.photo_rule_allows(huang, commons_title="Jensen huang stanford 2026-04-30 008.jpg",
                                            src="https://upload.wikimedia.org/wikipedia/commons/Jensen_Huang.jpg")[0])
        # A different person's photo on the Huang story is still rejected.
        self.assertFalse(P.photo_rule_allows(huang, commons_title="Donald Trump 2025.jpg",
                                             src="https://upload.wikimedia.org/wikipedia/commons/trump.jpg")[0])
        # Org/title words are not people, even when the Commons file title contains the same phrase.
        self.assertFalse(P.photo_rule_allows(
            gaza, commons_title="Gaza Health Ministry briefing 24 November 2025.jpg",
            src="https://upload.wikimedia.org/wikipedia/commons/Health_Ministry.jpg")[0])
        pif = "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days"
        self.assertTrue(P.photo_rule_allows(pif, commons_title="Public Investment Fund Tower, Riyadh.jpg")[0])
        self.assertTrue(P.photo_rule_allows(pif, commons_title="PIF Tower at night.jpg")[0])
        self.assertFalse(P.photo_rule_allows(pif, commons_title="Riyadh skyline 2023.jpg")[0])
        self.assertTrue(P.photo_rule_allows(libya, src="https://earthquake.usgs.gov/product/shakemap/us7000/download/intensity.jpg")[0])

    def test_people_from_entities_not_capitalized_bigrams(self):
        """Person names come from the hashtag PEOPLE extractor; org/title words are rejected."""
        import x_share
        gaza = "Gaza's Health Ministry has declared an epidemic alert across the territory over a rapid rise in meningitis"
        self.assertEqual(x_share.people_from_entities(gaza), [])
        self.assertTrue(x_share.is_org_title_name("Health Ministry"))
        self.assertTrue(x_share.is_org_title_name("Defense Department"))
        zel = "Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"
        names = x_share.people_from_entities(zel)
        self.assertIn("Volodymyr Zelensky", names)
        self.assertIn("Pete Hegseth", names)
        self.assertTrue(P.photo_rule_allows(zel, commons_title="Volodymyr Zelenskyy 2025.jpg")[0])
        bessent = "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers"
        self.assertIn("Scott Bessent", x_share.people_from_entities(bessent))

    def test_story_map_place_ignores_leftover_location(self):
        """Card badge/map use the Wire-map place, not a leftover Ukraine/Pennsylvania location."""
        libya = "Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel"
        place, lat, lon = S.story_map_place(libya, location="Ukraine", brief="not party to the Russian invasion of Ukraine")
        self.assertTrue(place and "libya" in place.lower() and "ukraine" not in place.lower(), place)
        self.assertIsNotNone(lat)
        self.assertIsNotNone(lon)
        # Empty leftover-free result is Libya too
        place2, _, _ = S.story_map_place(libya, location="", brief="")
        self.assertTrue(place2 and "libya" in place2.lower(), place2)
        huang = "Trump wanted Jensen Huang back as the CEO of Nvidia"
        place3, _, _ = S.story_map_place(huang, location="Pennsylvania", brief="Pennsylvania assassination attempt")
        self.assertTrue(not place3 or "pennsylvania" not in place3.lower(), place3)
        gaza = "Gaza's Health Ministry has declared an epidemic alert across the territory over a rapid rise in meningitis"
        place4, _, _ = S.story_map_place(gaza, location="", brief="")
        self.assertTrue(place4 and "gaza" in place4.lower(), place4)

    def test_card_headline_strips_unrenderable_glyphs_then_leading_punct(self):
        """Zelensky tofu: drop characters the card font cannot paint, then leading punctuation."""
        raw = "".join(chr(c) for c in (0x0648, 0x0642, 0x0627, 0x0644)) + " " + chr(0x2014) + " Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package"
        h = S._card_headline(raw)
        self.assertTrue(h.startswith("Zelensky"), h)
        self.assertNotIn(chr(0x0648), h)
        self.assertFalse(h.lstrip()[:1] in (chr(0x2014), "-", chr(0x2013)))
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        _, _, lines = S._story_head(d, raw, 640)
        joined = " ".join(lines)
        self.assertTrue(joined.startswith("Zelensky"), joined)
        cmap = S._card_font_cmap()
        self.assertTrue(cmap, "Latin-ext card font cmap should load")
        self.assertNotIn(0x0648, cmap)
        self.assertIn(ord("Z"), cmap)
        self.assertIn(ord("ş"), cmap)

    def test_card_headline_keeps_turkish_s_cedilla(self):
        """Yaşar must keep ş; the old Montserrat/ASCII fallback printed 'Yaar'."""
        raw = "On Monday, U.S. Secretary of War Pete Hegseth will receive Turkish Minister of National Defense Yaşar Güler at the Pentagon."
        h = S._card_headline(raw)
        self.assertIn("Yaşar", h, h)
        self.assertNotIn("Yaar", h)
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        _, _, lines = S._story_head(d, raw, 700)
        joined = " ".join(lines)
        self.assertIn("Yaşar", joined, joined)

    def test_non_ascii_photo_card_is_font_stale_until_latin_mark(self):
        """Photo cards with Yaşar etc. rebuild once onto the Latin-ext font; ASCII cards do not."""
        import og
        title = "Turkish Minister of National Defense Yaşar Güler at the Pentagon"
        meta_old = {"v": og.VERSION, "src": "https://example.test/x.jpg"}
        meta_new = {"v": og.VERSION + "L", "src": "https://example.test/x.jpg"}
        self.assertTrue(P.card_font_stale(meta_old, title))
        self.assertFalse(P.card_font_stale(meta_new, title))
        self.assertFalse(P.card_font_stale(meta_old, "Pete Hegseth at the Pentagon"))
        self.assertFalse(P.card_stale(meta_old))
        self.assertFalse(P.card_stale(meta_new))

    def test_story_head_hegseth_does_not_dangle_at_the(self):
        """Full first sentence if it fits; otherwise a clause cut with an ellipsis, never 'at the'."""
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        raw = "On Monday, U.S. Secretary of War Pete Hegseth will receive Turkish Minister of National Defense Yaşar Güler at the Pentagon."
        self.assertIn("U.S. Secretary of War Pete Hegseth", S._card_headline(raw))
        self.assertIn("Pentagon", S._card_headline(raw))
        for maxw in (640, 700):
            f, size, lines = S._story_head(d, raw, maxw)
            joined = " ".join(lines)
            self.assertLessEqual(len(lines), 3, joined)
            self.assertGreaterEqual(size, S.HEAD_MIN)
            self.assertIn("Yaşar", joined, joined)
            self.assertIn("U.S.", joined, joined)
            self.assertFalse(joined.rstrip("…").rstrip().endswith("at the"), joined)
            self.assertFalse(joined.rstrip("…").rstrip().endswith(" at"), joined)
            last = joined.rstrip("…").split()[-1].lower().strip(".,;:")
            self.assertNotIn(last, ("the", "a", "an", "of", "and", "at", "in", "on", "to", "for"), joined)
            if "…" in joined:
                self.assertTrue(joined.endswith("…"), joined)
                self.assertNotIn(" at the…", joined)
            else:
                self.assertIn("Pentagon", joined)

    def test_story_head_long_cuts_at_clause_with_ellipsis(self):
        """Zelensky / Doughty-length headlines must not end mid-phrase; an ellipsis is required if they are cut."""
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        cases = [
            "Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine, including 48 anti-ballistic missiles. Ukraine also expects missiles for F-16s and NASAMS systems.",
            "UK Middle East Minister Stephen Doughty says children in Gaza have endured unimaginable suffering as a second group of hostages is expected to be released.",
        ]
        for raw in cases:
            head = S._card_headline(raw)
            self.assertNotIn("NASAMS", head)
            for maxw in (640, 700):
                f, size, lines = S._story_head(d, head, maxw)
                joined = " ".join(lines)
                self.assertLessEqual(len(lines), 3, (raw, joined))
                self.assertGreaterEqual(size, S.HEAD_MIN)
                last = joined.rstrip("…").split()[-1].lower().strip(".,;:")
                self.assertNotIn(last, ("the", "a", "an", "of", "and", "at", "in", "on", "to", "for", "as", "including", "48"), joined)
                if joined.rstrip("…").strip() != head.rstrip("."):
                    self.assertTrue(joined.endswith("…"), joined)

    def test_clipped_headlines_are_typo_stale_until_24M(self):
        """Long clipped headlines rebuild onto 24M; short headlines and already-24M cards do not."""
        import og
        long_h = "On Monday, U.S. Secretary of War Pete Hegseth will receive Turkish Minister of National Defense Yaşar Güler at the Pentagon."
        short_h = "IMO: M3.5 earthquake, Iceland"
        old = {"v": og.VERSION + "L", "src": "https://example.test/x.jpg"}
        new = {"v": og.VERSION + "M", "src": "https://example.test/x.jpg"}
        self.assertTrue(S.card_needs_headline_refit(old, long_h))
        self.assertFalse(S.card_needs_headline_refit(new, long_h))
        self.assertFalse(S.card_needs_headline_refit(old, short_h))
        self.assertFalse(P.card_stale(old))
        self.assertFalse(P.card_stale(new))

    def test_audit_deletes_libya_and_gaza_rows_keeps_matching_zelensky(self):
        """Boot audit deletes non-matching photo rows outright; a matching Zelensky portrait is kept."""
        import os, tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        libya, gaza, zel = "4c292ccdd9df73f8", "b06344259ebf4d01", "9f5bc9d66d783d25"
        P.SUBJECT_HINTS[libya] = ("Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel", "")
        P.SUBJECT_HINTS[gaza] = ("Gaza's Health Ministry has declared an epidemic alert across the territory over a rapid rise in meningitis", "")
        P.SUBJECT_HINTS[zel] = ("Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine", "")
        P.AUDIT.update(checked=0, deleted=0, typography=0, done=False, error="", deleted_cids=[])
        try:
            P._dir = lambda: Path(d)
            png = b"\x89PNG\r\n\x1a\n" + b"P" * 4000
            P.db_put(libya, dict(src="https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg",
                                 credit="Latvian pagan", license="CC0", caption="Ukraine Russia, 2023.", kind="place"),
                     jpg=b"\xff\xd8" + b"j" * 3000)
            P.put_card(libya, png, "https://upload.wikimedia.org/wikipedia/commons/themis_ukraine.jpg")
            P.db_put(gaza, dict(src="https://upload.wikimedia.org/wikipedia/commons/Ilan_Meiri_1980.jpg",
                                credit="Ilan Meiri / Wikimedia Commons", license="CC BY 4.0",
                                caption="Health Ministry. File photo.", kind="person"),
                     jpg=b"\xff\xd8" + b"g" * 3000)
            P.put_card(gaza, png, "https://upload.wikimedia.org/wikipedia/commons/Ilan_Meiri_1980.jpg")
            zsrc = "https://upload.wikimedia.org/wikipedia/commons/Volodymyr_Zelenskyy.jpg"
            P.db_put(zel, dict(src=zsrc, credit="Press Service", license="CC BY 4.0",
                               caption="Volodymyr Zelenskyy, 2025. File photo.", kind="person"),
                     jpg=b"\xff\xd8" + b"z" * 3000)
            P.put_card(zel, png, zsrc, title_hash=P.card_title_key("Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine"))
            n = S.audit_stored_photo_cards()
            self.assertGreaterEqual(n, 2)
            self.assertIn(libya, P.AUDIT["deleted_cids"])
            self.assertIn(gaza, P.AUDIT["deleted_cids"])
            self.assertIsNone(P.db_choice(libya))
            self.assertIsNone(P.get_card(libya))
            self.assertIsNone(P.db_choice(gaza))
            self.assertIsNone(P.get_card(gaza))
            # Zelensky portrait kept (file title has the full name).
            self.assertTrue(P.stored_photo_matches(zel))
            self.assertIsNotNone(P.db_choice(zel))
            self.assertNotIn(zel, P.AUDIT["deleted_cids"])
            dbg = {r["cid"]: r for r in P.photo_row_debug((libya, gaza, zel))}
            self.assertFalse(dbg[libya]["photo_row"])
            self.assertFalse(dbg[libya]["has_card"])
            self.assertFalse(dbg[gaza]["photo_row"])
            self.assertTrue(dbg[zel]["photo_row"])
        finally:
            for k in (libya, gaza, zel):
                P.SUBJECT_HINTS.pop(k, None)
            os.environ.pop("BN_CARDS_DB", None)


    def test_style_mark_is_stale_until_p_without_bumping_og_version(self):
        import og
        old = {"v": og.VERSION + "M", "src": "https://example.test/x.jpg"}
        new = {"v": og.VERSION + "MP", "src": "https://example.test/x.jpg"}
        self.assertTrue(P.card_style_stale(old))
        self.assertFalse(P.card_style_stale(new))
        self.assertFalse(P.card_stale(old))
        self.assertFalse(P.card_stale(new))
        self.assertTrue(P.card_ver_current().endswith("P"))
        self.assertTrue(P.card_ver_current().startswith(str(og.VERSION)))

    def test_newsletter_pool_extends_military_with_unique_files(self):
        import card_photo as CP
        titles = CP.topic_file_titles()
        self.assertIn("b-2 spirit original.jpg", titles)
        # Email-pool carrier / tank photos (not the repeating B-2 / F-35 pair).
        self.assertIn("flickr - official u.s. navy imagery - aircraft carrier at sea..jpg", titles)
        self.assertIn("abrams in formation.jpg", titles)
        # Satellite / ISS hurricane views from the email hazards pool must not be share-card files.
        self.assertNotIn("cyclone catarina from the iss on march 26 2004.jpg", titles)
        self.assertGreaterEqual(len(CP.TOPICS["military"][1]), 8)
        # Follow-up conflict pool (card_photo_pool.json): drones, missiles, ruins, etc.
        self.assertIn("mq-9 reaper uav.jpg", titles)
        self.assertIn("unarmed minuteman iii test launch from vandenberg (6406505).jpg", titles)
        self.assertIn("m142 himars firing.jpg", titles)
        self.assertGreaterEqual(len(CP.TOPICS["military"][1]), 40)
        self.assertGreaterEqual(len(CP.TOPICS["cyber"][1]), 8)

    def test_choose_skips_a_place_photo_already_used_by_another_story(self):
        """A second Russia story must not reuse the same Kremlin/place file; it falls through to a topic photo."""
        import os, tempfile
        import card_photo as CP
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        kremlin = "https://upload.wikimedia.org/wikipedia/commons/Kremlin_St_Basils.jpg"
        P._dir = lambda: Path(d)
        P.db_put("aaaaaaaaaaaaaaaa", dict(src=kremlin, credit="Example", license="CC BY 2.0",
                                          caption="Moscow.", kind="place", label="Moscow.",
                                          link="https://commons.wikimedia.org/wiki/File:Kremlin_St_Basils.jpg"),
                 jpg=b"\xff\xd8" + b"a" * 3000)

        def fake_place(hit):
            return {"src": kremlin, "credit": "Example", "license": "CC BY 2.0",
                    "title": "File:Kremlin St Basils.jpg",
                    "page": "https://commons.wikimedia.org/wiki/File:Kremlin_St_Basils.jpg",
                    "kind": "place", "w": 1600, "h": 900}

        def fake_topic(text, seed="", key=None, except_cid=""):
            return {"src": "https://upload.wikimedia.org/wikipedia/commons/MQ-9_Reaper_UAV.jpg",
                    "credit": "U.S. Air Force", "license": "Public domain",
                    "title": "File:MQ-9 Reaper UAV.jpg",
                    "page": "https://commons.wikimedia.org/wiki/File:MQ-9_Reaper_UAV.jpg",
                    "kind": "topic", "w": 1600, "h": 900}

        def fake_person(title, text=""):
            return None

        def fake_fetch(im):
            return "/tmp/fake.jpg"

        orig = (CP.place_photo, CP.topic_photo, CP.person_photo, CP.fetch)
        CP.place_photo, CP.topic_photo, CP.person_photo, CP.fetch = fake_place, fake_topic, fake_person, fake_fetch
        try:
            im = CP.choose("bbbbbbbbbbbbbbbb", "Russian sabotage across Europe has risen",
                           hit={"place": "Moscow", "lat": 55.75, "lon": 37.62, "cc": "RU", "precision": "city"},
                           text="", category="conflict")
            self.assertIsNotNone(im)
            self.assertEqual(im.get("kind"), "topic")
            self.assertNotEqual(CP.file_key(src=im.get("src") or "", filename=im.get("title") or ""),
                                CP.file_key(src=kremlin, filename="Kremlin St Basils.jpg"))
        finally:
            CP.place_photo, CP.topic_photo, CP.person_photo, CP.fetch = orig
            os.environ.pop("BN_CARDS_DB", None)

    def test_topic_photos_are_unique_across_stories(self):
        """Two conflict stories must not be assigned the same category photo (the live B-2 repeat)."""
        import os, tempfile
        import card_photo as CP
        d = tempfile.mkdtemp()
        os.environ["BN_CARDS_DB"] = str(Path(d) / "cards.db")
        files = list(CP.TOPICS["military"][1][:6])
        self.assertGreaterEqual(len(files), 4)
        calls = []

        def fake_commons(fn, width=1600, min_w=700):
            calls.append(fn)
            name = fn.replace("File:", "").replace(" ", "_")
            return {"src": f"https://upload.wikimedia.org/wikipedia/commons/{name}",
                    "credit": "U.S. Navy", "license": "Public domain", "title": fn,
                    "page": f"https://commons.wikimedia.org/wiki/{fn.replace(' ', '_')}", "w": 1600, "h": 900}

        orig = CP.commons_image
        CP.commons_image = fake_commons
        try:
            P._dir = lambda: Path(d)
            a = CP.topic_photo("Iran ballistic missile exercises", seed="aaaaaaaaaaaaaaaa", key="military", except_cid="aaaaaaaaaaaaaaaa")
            self.assertIsNotNone(a)
            P.db_put("aaaaaaaaaaaaaaaa", dict(src=a["src"], credit=a.get("credit") or "", license=a.get("license") or "",
                                              caption=a.get("label") or "", kind="topic", label=a.get("label") or "",
                                              link=a.get("page") or ""), jpg=b"\xff\xd8" + b"a" * 3000)
            b = CP.topic_photo("Ukraine drone evacuation", seed="bbbbbbbbbbbbbbbb", key="military", except_cid="bbbbbbbbbbbbbbbb")
            self.assertIsNotNone(b)
            self.assertNotEqual(CP.file_key(src=a["src"], filename=a.get("title")), CP.file_key(src=b["src"], filename=b.get("title")))
            # A third story also gets a still-unused file.
            P.db_put("bbbbbbbbbbbbbbbb", dict(src=b["src"], credit=b.get("credit") or "", license=b.get("license") or "",
                                              caption=b.get("label") or "", kind="topic", label=b.get("label") or "",
                                              link=b.get("page") or ""), jpg=b"\xff\xd8" + b"b" * 3000)
            c = CP.topic_photo("Japan defense policy", seed="cccccccccccccccc", key="military", except_cid="cccccccccccccccc")
            self.assertIsNotNone(c)
            keys = {CP.file_key(src=x["src"], filename=x.get("title")) for x in (a, b, c)}
            self.assertEqual(len(keys), 3, keys)
        finally:
            CP.commons_image = orig
            os.environ.pop("BN_CARDS_DB", None)

    def test_share_card_is_photo_only_no_headline_text(self):
        """The X card is the photo itself: no dark gradient, no burned-in headline or wordmark."""
        from PIL import Image
        import tempfile, os
        d = tempfile.mkdtemp()
        jpg = Path(d) / "p.jpg"
        Image.new("RGB", (1600, 900), (20, 180, 40)).save(jpg, "JPEG")
        orig = P.cached
        P.cached = lambda src: jpg
        try:
            ph = dict(src="https://upload.wikimedia.org/wikipedia/commons/unique_photo.jpg",
                      credit="U.S. Navy / Wikimedia Commons", license="Public domain", kind="topic",
                      label="Military aircraft (U.S. Air Force). File photo; not taken at this event.")
            it = dict(kind="story", id="abcabcabcabcabca",
                      title="Iran reports explosion on oil tanker after a strike in the Strait of Hormuz",
                      rank=6, color=S.AMBER, kicker="CONFLICT", loc="Strait of Hormuz",
                      art=("story", None, None, ph["src"]), photo=ph, stats=[], tags=[])
            im = S._lay_story(it)
            self.assertEqual(im.size, (1200, 675))
            # A typography card darkened the left third and painted white headline glyphs.
            # A plain photo keeps the source green across the frame.
            samples = [im.getpixel((x, y))[:3] for x, y in ((40, 40), (600, 40), (1160, 40), (40, 337), (600, 337), (1160, 630), (200, 250))]
            for px in samples:
                self.assertGreater(px[1], 140, px)
                self.assertLess(px[0], 80, px)
        finally:
            P.cached = orig



if __name__ == "__main__":
    unittest.main()
