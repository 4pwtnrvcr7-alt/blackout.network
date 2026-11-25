import io, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import share_card as S

SOLAR = {"ok": True, "planets": [{"id": "earth", "pos": [1, 0, 0], "v_km_s": 29.8}, {"id": "jupiter", "pos": [5.2, 0, 0], "v_km_s": 13.0}],
         "craft": [{"id": "voyager1", "name": "Voyager 1", "operator": "NASA / JPL", "launch": "1977-09-05", "status": "Operational. In interstellar space.", "earth_au": 168.0, "v_km_s": 16.9}]}
NET = {"nets": [{"id": "cox", "name": "Cox", "level": 2, "status": "Outage signal on 1 of 1 network", "incidents": [{"t": "routing drop"}], "uptime": 97.8, "days": [0] * 28 + [2, 2], "group": "isp"},
                {"id": "spectrum", "name": "Spectrum", "level": 0, "status": "No outage signal", "incidents": [], "uptime": 99.8, "days": [0] * 30, "group": "isp"}],
       "groups": [{"id": "isp", "name": "Internet providers"}], "cloud": [{"p": "aws", "name": "US East (N. Virginia)", "lon": -77.5, "lat": 39.0, "level": 1}], "outages": {"countries": []}}
LAUNCH = {"launches": [{"id": "abc-1", "name": "Falcon 9 Block 5 | Starlink Group 12-3", "vehicle": "Falcon 9 Block 5", "mission": "Starlink Group 12-3", "net": "2099-01-01T12:00:00Z", "status_name": "Go for Launch",
                        "pad": "Space Launch Complex 40", "location": "Cape Canaveral SFS, FL, USA", "pad_lat": 28.56, "pad_lon": -80.58, "orbit": "LEO", "provider": "SpaceX", "ascent": [[-80.58, 28.56, 0, 0], [-79.0, 29.0, 1000, 10]]}]}


class T(unittest.TestCase):
    def setUp(self):
        S.HOOKS.update(solar=lambda: SOLAR, net=lambda: NET, launches=lambda: LAUNCH)

    def tearDown(self):
        S.HOOKS.clear()

    def png(self, kind, ident):
        b = S.png_for(kind, ident)
        from PIL import Image
        im = Image.open(io.BytesIO(b))
        self.assertEqual(im.size, (1200, 675))
        return b

    def test_each_kind_renders_distinct(self):
        items = [("planet", "jupiter"), ("planet", "moon"), ("craft", "voyager1"), ("sat", "starlink"), ("launch", "abc-1"), ("net", "cox"), ("net", "spectrum"),
                 ("cloud", "aws~us-east-n-virginia"), ("page", "weather"), ("site", "moon~apollo11")]
        seen = set()
        for k, i in items:
            b = self.png(k, i)
            seen.add(hash(b))
        self.assertEqual(len(seen), len(items))

    def test_text_and_tags(self):
        for k, i in [("planet", "jupiter"), ("craft", "voyager1"), ("launch", "abc-1"), ("net", "cox"), ("cloud", "aws~us-east-n-virginia"), ("page", "weather")]:
            it = S.resolve(k, i)
            href, text, tags, url = S.intent(it)
            self.assertTrue(3 <= len(tags) <= 5, (k, tags))
            from x_share import weighted_len
            self.assertLessEqual(weighted_len(text, url), 280, (k, text))
            self.assertTrue(href.startswith("https://x.com/intent/post?text="))
            self.assertTrue(all(t.startswith("#") for t in tags))

    def test_no_yellow_accents(self):
        for c in (S.SPACE_C, S.LAUNCH_C, S.WX_C, S.NET_C, S.GREEN, S.RED):
            self.assertFalse(c[0] > 200 and c[1] > 170 and c[2] < 90)

    def test_adaptor(self):
        it = S.item_for_share("network", "cox", {})
        self.assertEqual(it["title"], "Cox")
        it = S.item_for_share("cloud", "aws-USEastN.Virginia", {})
        self.assertIn("AWS", it["title"])
        it = S.item_for_share("weather", "wx-X", {"n": ["Sanford weather"], "d": ["Clear 72F"]})
        self.assertEqual(it["art"][0], "type")
        self.assertIsNone(S.item_for_share("weather", "wx-X", {}))
        code, body, ctype = S.og_share("/og/share/network/cox.png", {})
        self.assertEqual((code, ctype), (200, "image/png"))

    def test_launches_bytes_payload(self):
        S.HOOKS["launches"] = lambda: json.dumps(LAUNCH).encode()   # netlaunch.launches_cached() returns JSON bytes
        it = S.resolve("launch", "abc-1")
        self.assertTrue(it and it["title"].startswith("Starlink"))
        self.png("launch", "abc-1")

    def test_unknown_is_404(self):
        self.assertIsNone(S.png_for("planet", "pluto"))
        self.assertEqual(S.handle_get("/og/share/zzz/none.png")[0], 404)


if __name__ == "__main__":
    unittest.main()


class QuickFallback(unittest.TestCase):
    def test_png_for_story_fast_fallback_does_not_raise_and_is_unique(self):
        import og, share_card
        old = share_card.story_png_fast
        share_card.story_png_fast = lambda cid, budget=1.0: None
        try:
            import story
            o = story.load
            story.load = lambda cid: ({"title": "Theriva Biologics halted on NYSE American", "rank": 7}, [])
            try:
                a = og.png_for_story_fast("a" * 16)
                self.assertGreater(len(a), 5000)
                from PIL import Image
                import io
                im = Image.open(io.BytesIO(a))
                self.assertEqual(im.size, (1200, 675))  # designed map card, never the 1200x630 earth fallback
                self.assertEqual(a, og.png_for_story_fast("a" * 16))
                code, body, ct = og.handle_get("/og/wire/" + "a" * 16 + ".png")
                self.assertEqual(body, a)
            finally:
                story.load = o
        finally:
            share_card.story_png_fast = old


    def test_story_item_does_not_call_api_state(self):
        called = {"n": 0}
        import theme, story
        old_srv, old_load = theme._srv, story.load
        theme._srv = lambda: type("S", (), {"api_state": staticmethod(lambda: called.__setitem__("n", called["n"] + 1) or {})})()
        story.load = lambda cid: ({"title": "Scott Bessent Unleashes Fresh Iran Sanctions", "brief": "WHAT: sanctions",
                                   "rank": 2, "location": "Iran", "category": "politics", "lat": None, "lon": None,
                                   "families": "a,b", "watchlist": 0, "hidden": 0}, [])
        try:
            got = S._story_item("e2ca47e325c5b8e1")
            self.assertIsNotNone(got)
            self.assertEqual(called["n"], 0)
            self.assertIn("Bessent", got[0]["title"])
            card = S._r_story("e2ca47e325c5b8e1")
            self.assertIsNotNone(card)
            self.assertEqual(called["n"], 0)
        finally:
            theme._srv = old_srv
            story.load = old_load


class CrawlerFirstFetch(unittest.TestCase):
    """X cards (Nov 25 2026): a story is not public until its card is baked, and a crawler never waits on the board."""

    def test_allow_queues_bake_but_does_not_hold_the_story(self):
        import story_writer as SW, share_card as S
        from unittest import mock
        S._BAKED.discard("abcdabcdabcdabcd")
        with mock.patch.object(SW, "gate_on", return_value=True), \
             mock.patch.object(SW, "_is_needs_paid", return_value=False), \
             mock.patch.object(SW, "has_writeup", return_value=True), \
             mock.patch.object(S, "card_baked", return_value=False), \
             mock.patch.object(S, "bake_card") as bake:
            self.assertTrue(SW.allow("abcdabcdabcdabcd"))  # fail open after queueing the bake (OOM hotfix)
            bake.assert_called_once_with("abcdabcdabcdabcd")
        with mock.patch.object(SW, "gate_on", return_value=True), \
             mock.patch.object(SW, "_is_needs_paid", return_value=False), \
             mock.patch.object(SW, "has_writeup", return_value=True), \
             mock.patch.object(S, "card_baked", return_value=True):
            self.assertTrue(SW.allow("abcdabcdabcdabcd"))


    def test_bake_card_uses_one_worker_not_one_thread_per_story(self):
        import share_card as S
        from unittest import mock
        S._BAKE_Q = None
        S._BAKED.clear(); S._BAKING.clear()
        started = []
        class Q:
            def __init__(self):
                self.items=[]
            def put(self, cid):
                self.items.append(cid)
        def fake_thread(*a, **k):
            started.append(k.get("name") or (a[0] if a else "t"))
            class T:
                def start(self): started.append("start")
            return T()
        with mock.patch("share_card.threading.Thread", side_effect=fake_thread):
            import queue as _q
            with mock.patch("queue.Queue", side_effect=lambda: Q()):
                S.bake_card("aaaaaaaaaaaaaaaa")
                S.bake_card("bbbbbbbbbbbbbbbb")
                S.bake_card("aaaaaaaaaaaaaaaa")  # dedup
        # One worker thread started, both distinct cids queued, duplicate skipped
        self.assertGreaterEqual(started.count("card-bake"), 1)
        self.assertEqual(started.count("card-bake"), 1)
        self.assertEqual(S._BAKE_Q.items, ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"])

    def test_crawler_gets_og_stub_without_waiting_for_the_board(self):
        import wire_v2 as W
        from unittest import mock
        from concurrent.futures import Future
        never = Future()   # a board build that never finishes
        W._C.pop("abcdabcdabcdabcd", None); W._INFL.pop("abcdabcdabcdabcd", None); W._NEG.pop("abcdabcdabcdabcd", None)
        stub = '<meta name="twitter:card" content="summary_large_image">'
        class P:
            def submit(self, *a, **k): return never
        with mock.patch.object(W, "_pool", return_value=P()), mock.patch.object(W, "_light_story", return_value=stub):
            import time
            t0 = time.time()
            code, body, _ = W.handle("/wire/abcdabcdabcdabcd", {}, headers={"User-Agent": "Twitterbot/1.0"})
            self.assertLess(time.time() - t0, 0.5)
            self.assertEqual(code, 200)
            self.assertIn("twitter:card", body)
        W._INFL.pop("abcdabcdabcdabcd", None)


class CardPhotoV3(unittest.TestCase):
    """v3 photo cards: topic before place for disease/wildfire/storm/flood; bare Congo is DRC."""

    def test_topic_comes_before_place_for_disease_wildfire_storm_flood(self):
        import card_photo as CP
        self.assertEqual(CP.choose_order("Gaza Health Ministry epidemic alert over meningitis"), ("person", "topic", "place"))
        self.assertEqual(CP.choose_order("Forest fire burns acres in Virginia"), ("person", "topic", "place"))
        self.assertEqual(CP.choose_order("NWS Freeze Watch for Lake Charles"), ("person", "topic", "place"))
        self.assertEqual(CP.choose_order("Coastal Flood Warning issued by NWS Seattle"), ("person", "topic", "place"))
        self.assertEqual(CP.choose_order("Measles outbreak in Wisconsin"), ("person", "topic", "place"))
        # Quake and cyber keep place before topic.
        self.assertEqual(CP.choose_order("Magnitude 6.0 earthquake near Guam"), ("person", "place", "topic"))
        self.assertEqual(CP.choose_order("Cisco security advisory on a VPN vulnerability"), ("person", "place", "topic"))

    def test_bare_congo_is_dr_congo_unless_brazzaville_is_named(self):
        import signal_place as SP
        self.assertEqual(SP.named_countries("Ebola outbreak in Congo approaches 5,000 deaths"), ["CD"])
        hit = SP.infer("Ebola outbreak in Congo approaches 5,000 deaths")
        self.assertEqual((hit or {}).get("cc"), "CD")
        self.assertIn("Democratic Republic", (hit or {}).get("place") or "")
        hit2 = SP.infer("Republic of the Congo reports cases in Brazzaville")
        self.assertEqual((hit2 or {}).get("cc"), "CG")

    def test_flag_off_disables_chooser(self):
        import os, card_photo as CP
        old = os.environ.get("BN_CARD_PHOTO")
        os.environ["BN_CARD_PHOTO"] = "0"
        try:
            self.assertFalse(CP.enabled())
        finally:
            if old is None:
                os.environ.pop("BN_CARD_PHOTO", None)
            else:
                os.environ["BN_CARD_PHOTO"] = old
            self.assertTrue(CP.enabled() or old == "0")

    def test_rebuild_is_one_paced_worker_and_drops_pngs_from_ram(self):
        """A long v3 rebuild must not start a thread per story or keep PNGs in _SC."""
        import share_card as S
        from unittest import mock
        fake = b"\x89PNG" + b"x" * (800 * 1024)  # mid-range of the 0.6–1.2 MB live cards
        ids = [f"{i:016x}" for i in range(12)]
        started = []

        def fake_thread(*a, **k):
            started.append(k.get("name") or "t")
            class T:
                def start(self):
                    started.append("start")
            return T()

        put_sizes = []

        def fake_put(cid, png, src="", title_hash="", allow_downgrade=None):
            put_sizes.append(len(png))

        with mock.patch.object(S, "card_photo_on", return_value=True), \
             mock.patch.object(S, "apply_card_photo", return_value={"src": "https://example.test/x.jpg"}), \
             mock.patch.object(S, "render_story_fresh", return_value=fake), \
             mock.patch.object(S, "generic_story_card", return_value=None), \
             mock.patch.object(S, "_force_title", return_value=("Title", "", "")), \
             mock.patch.object(S, "invalidate_card_layers"), \
             mock.patch("share_card.threading.Thread", side_effect=fake_thread), \
             mock.patch("story_photo.put_card", side_effect=fake_put), \
             mock.patch("story_photo.pick", return_value=None):
            for cid in ids:
                S._SC[cid] = (0, fake, False)
            out = S.rebuild_card_photos(ids, pause=0)
        self.assertEqual(out["ids"], 12)
        self.assertTrue(out["done"])
        self.assertEqual(started, [])  # no per-story threads
        self.assertEqual(put_sizes, [len(fake)] * 12)
        for cid in ids:
            self.assertNotIn(cid, S._SC)
        # A second caller is a no-op while a rebuild already holds the lock.
        S._REBUILD_LOCK.acquire()
        try:
            out2 = S.rebuild_card_photos(ids, pause=0)
            self.assertTrue(out2["done"])
            self.assertEqual(out2["ids"], 12)  # not reset or re-run
        finally:
            S._REBUILD_LOCK.release()

    def test_stored_map_is_stale_when_photo_cards_are_on(self):
        """A leftover map (no https src) must be rebuilt as a v3 photo card, even at the current VERSION."""
        import story_photo as P
        import os
        old = os.environ.get("BN_CARD_PHOTO")
        os.environ.pop("BN_CARD_PHOTO", None)
        try:
            self.assertTrue(P.card_stale({"v": __import__("og").VERSION, "src": ""}))
            self.assertTrue(P.card_stale({"v": "23", "src": "https://example.test/x.jpg"}))
            self.assertFalse(P.card_stale({"v": __import__("og").VERSION, "src": "https://example.test/x.jpg"}))
        finally:
            if old is None:
                os.environ.pop("BN_CARD_PHOTO", None)
            else:
                os.environ["BN_CARD_PHOTO"] = old
