"""Full A→B deploy lifecycle for licensed photo cards.

Instance A builds photo cards under render_app.py's thread guard. A deploy hands
the Render-owned cards.db (same snapshot/install as export_tar/_apply_tar) to a
fresh instance B, which also runs under that guard. B must serve those photos on
the first hit, never overwrite a photo PNG with a map, and a newly requested id
must get a photo within 60s while a 50-item backfill is queued.

Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_card_deploy_handoff -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Exact thread-guard rule from render_app.py (do not import render_app: it chdirs
# to /workspace/blackout and patches subprocess). Keep "loop" out of targets.
_BLOCK_THREAD_NAMES = {
    "bn-search-index", "politics_hist", "politics_markets", "netstatus",
    "heatmap_geocoder", "solar_seismic_logger", "video-subs-bg", "streams-live",
    "bcast-text", "bcast-audio",
}
_BLOCK_TARGETS = {"_loop", "loop", "_warm_loop", "_indexer", "_text_loop", "_audio_loop", "harvest", "scheduler", "jet_loop", "_harvest"}
_ALLOW_TARGETS = {"_watch", "bg", "process_request_thread", "_render_bg", "_photo_jobs", "_run_lookup"}


def install_render_thread_guard():
    _orig = threading.Thread.start

    def _guarded_start(self):
        t = getattr(self, "_target", None)
        tn = getattr(t, "__name__", "") or ""
        if tn not in _ALLOW_TARGETS and (
            self.name in _BLOCK_THREAD_NAMES
            or tn in _BLOCK_TARGETS
            or any(w in tn.lower() for w in ("loop", "harvest", "indexer"))
        ):
            return None
        return _orig(self)

    threading.Thread.start = _guarded_start
    return _orig


def _tiny_png(kind=b"PHOTO"):
    """A valid-looking PNG blob (>2000 bytes) tagged so we can tell photo from map."""
    return b"\x89PNG\r\n\x1a\n" + kind + (b"P" if kind == b"PHOTO" else b"M") * 3000


def _tiny_jpg():
    return b"\xff\xd8" + b"J" * 3000


class CardDeployHandoff(unittest.TestCase):
    def setUp(self):
        self._orig_start = install_render_thread_guard()
        self.tmp = tempfile.mkdtemp()
        self.a_dir = Path(self.tmp) / "A"
        self.b_dir = Path(self.tmp) / "B"
        self.a_dir.mkdir()
        self.b_dir.mkdir()
        self.a_db = str(self.a_dir / "cards.db")
        self.b_db = str(self.b_dir / "cards.db")
        os.environ["BN_CARDS_DB"] = self.a_db
        # Isolate module state that would leak across tests in this process.
        import story_photo as P
        import share_card as S
        P._MEM.clear()
        S._SC.clear()
        # Reuse the live writer if one is already running in this process (same _WQ);
        # just point it at this test's cards.db. Starting a second writer would steal jobs.
        if P._WTHREAD is not None and P._WTHREAD.is_alive() and P._WPID == os.getpid():
            P.reopen()
        else:
            P._WPID = None
            P._WTHREAD = None
            P._WSTARTED = False
            self.assertTrue(P._ensure_writer(), "cards.db writer did not start under the thread guard")

    def tearDown(self):
        threading.Thread.start = self._orig_start
        os.environ.pop("BN_CARDS_DB", None)

    def _put_photo(self, cid, tag=b"PHOTO"):
        import story_photo as P
        cand = dict(
            src=f"https://upload.wikimedia.org/wikipedia/commons/test/{cid}.jpg",
            credit="Public domain test",
            license="Public domain",
            caption="",
            kind="person",
            label="",
            link="",
        )
        png = _tiny_png(tag)
        jpg = _tiny_jpg()
        self.assertTrue(P._write(lambda k: None) or P._WTHREAD is not None)
        P.db_put(cid, cand, jpg=jpg)
        P.put_card(cid, png, cand["src"])
        # _write is async-confirmed; db_put/put_card should have committed.
        self.assertTrue(P.has_photo(cid), f"JPEG for {cid} did not persist under the thread guard")
        self.assertTrue(P.card_has_photo(cid), f"photo PNG for {cid} did not persist under the thread guard")
        return png

    def _handoff_to_b(self):
        import handoff_db
        snap = handoff_db.snapshot_sqlite(self.a_db, str(self.b_dir))
        handoff_db.install_sqlite(self.b_db, snap)

    def _become_b(self):
        import story_photo as P
        import share_card as S
        os.environ["BN_CARDS_DB"] = self.b_db
        P._MEM.clear()
        S._SC.clear()
        # Simulate a fresh instance: close A's writer and open B's file.
        P.reopen()
        P._ensure_writer()

    def test_writer_starts_under_render_app_thread_guard(self):
        import story_photo as P
        self.assertTrue(P._ensure_writer())
        self.assertTrue(P._WTHREAD and P._WTHREAD.is_alive())
        self.assertEqual(P._card_writes.__name__, "_card_writes")
        self.assertNotIn("loop", P._card_writes.__name__.lower())

    def test_old_write_loop_name_is_blocked_by_the_guard(self):
        """Document the production bug: a target named _write_loop never runs under render_app."""
        ran = {"n": 0}

        def _write_loop():
            ran["n"] += 1

        t = threading.Thread(target=_write_loop, name="cards-db", daemon=True)
        t.start()
        time.sleep(0.2)
        self.assertFalse(t.is_alive())
        self.assertEqual(ran["n"], 0)

    def test_handoff_b_serves_a_photos_on_first_hit(self):
        import story_photo as P
        import share_card as S
        cids = ["zelenskytest0001", "bessenttest00002", "burnhamtest00003"]
        photos = {cid: self._put_photo(cid) for cid in cids}
        # A "deploy": snapshot cards.db the same way render_app.export_tar does, install on B.
        self._handoff_to_b()
        self._become_b()
        # First hit on B, empty memory cache, must be the photo (not a map, not earth).
        for cid in cids:
            t0 = time.time()
            got = S.ensure_current_card(cid)
            elapsed = time.time() - t0
            self.assertIsNotNone(got, f"B first hit missed stored photo for {cid}")
            self.assertEqual(got, photos[cid], f"B first hit was not the handed-off photo for {cid}")
            self.assertLess(elapsed, 2.0, f"B first hit took {elapsed:.2f}s for {cid}")
            self.assertTrue(P.card_has_photo(cid))
            # Never overwrite a photo with a map after the handoff.
            map_png = _tiny_png(b"MAPXX")
            P.put_card(cid, map_png, "map")
            self.assertEqual(P.get_card(cid), photos[cid])

    def test_requested_id_bypasses_backfill_within_60s(self):
        import story_photo as P
        import share_card as S

        # Start from a handed-off photo store so this is instance B with a 50-item backfill.
        self._put_photo("kept-photo-card")
        self._handoff_to_b()
        self._become_b()

        order = []
        orig_prefetch = S._network_prefetch

        def fake_prefetch(cid):
            # Backfill jobs are slower than a request; still well under the 10s lookup timeout.
            if str(cid).startswith("backfill-"):
                time.sleep(0.25)
            else:
                time.sleep(0.05)
            cand = dict(
                src=f"https://upload.wikimedia.org/wikipedia/commons/test/{cid}.jpg",
                credit="Public domain test",
                license="Public domain",
                caption="",
                kind="person",
                label="",
                link="",
            )
            P.db_put(cid, cand, jpg=_tiny_jpg())
            # The worker then calls _story_build(fetch=False); we also record order here.
            order.append(cid)

        S._network_prefetch = fake_prefetch
        # Prevent _story_build from doing real map work (needs blackout.db / item data).
        orig_build = S._story_build

        def fake_build(cid, fetch=False):
            if fetch:
                fake_prefetch(cid)
            c = P.db_choice(cid)
            src = (c or {}).get("src") or ""
            if src.startswith("https://"):
                png = _tiny_png(b"PHOTO")
                P.put_card(cid, png, src)
                S._SC[cid] = (time.time(), png, False)
                return png
            png = _tiny_png(b"MAPXX")
            P.put_card(cid, png, "map")
            return png

        S._story_build = fake_build
        try:
            # Drain any leftover queue from the previous test in this process.
            with S._FLOCK:
                S._FHIGH.clear()
                S._FLOW.clear()
                S._FWAIT.clear()
                S._FINFLIGHT.clear()
            self.assertTrue(S._ensure_fworker())
            self.assertTrue(S._FWORKER and S._FWORKER.is_alive())

            backfill = [f"backfill-{i:03d}" for i in range(50)]
            for cid in backfill:
                S.submit(cid, fetch=True, urgent=False)
            # Confirm backfill sat on the low queue, not the request queue.
            with S._FLOCK:
                high_before = list(S._FHIGH)
                low_n = len(S._FLOW)
            self.assertEqual(high_before, [])
            self.assertGreaterEqual(low_n, 50)

            requested = "requested-new-story"
            t0 = time.time()
            S.submit(requested, fetch=True, urgent=True)
            deadline = t0 + 60
            while time.time() < deadline:
                if P.card_has_photo(requested) or P.has_photo(requested):
                    break
                time.sleep(0.05)
            elapsed = time.time() - t0
            self.assertLess(elapsed, 60, f"requested id took {elapsed:.2f}s under a 50-item backfill")
            self.assertTrue(P.has_photo(requested) or P.card_has_photo(requested))
            # The request must have run before the backfill finished (it jumped the queue).
            self.assertIn(requested, order)
            backfill_done = sum(1 for c in order if str(c).startswith("backfill-"))
            self.assertLess(backfill_done, 50, "requested id waited for the whole backfill")
            self.assertLess(order.index(requested), 5, f"requested id was not near the front: {order[:8]}")
        finally:
            S._network_prefetch = orig_prefetch
            S._story_build = orig_build


if __name__ == "__main__":
    unittest.main()
