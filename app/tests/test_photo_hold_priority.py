"""Validator no-photo-card holds jump the boot photo backfill (share_card.warm / submit).

Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_photo_hold_priority -v
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import share_card as S


class PhotoHoldPriority(unittest.TestCase):
    def setUp(self):
        self._holds = 0
        self._orig_holds = S.no_photo_holds
        S.no_photo_holds = lambda: self._holds
        with S._FLOCK:
            S._FHIGH.clear()
            S._FLOW.clear()
            S._FWAIT.clear()
            # Leave any in-flight job from another test; we only assert on the queues.

    def tearDown(self):
        S.no_photo_holds = self._orig_holds
        with S._FLOCK:
            S._FHIGH.clear()
            S._FLOW.clear()
            for cid, fut in list(S._FWAIT.items()):
                if cid.startswith(("bf-", "prio-", "skip-")) and fut is not None and not fut.done():
                    try:
                        fut.cancel()
                    except Exception:
                        pass
                    S._FWAIT.pop(cid, None)
            S._FLOW[:] = [c for c in S._FLOW if not str(c).startswith(("bf-", "prio-", "skip-"))]
            S._FHIGH[:] = [c for c in S._FHIGH if not str(c).startswith(("bf-", "prio-", "skip-"))]

    def test_photo_holds_heavy_threshold(self):
        self._holds = 0
        self.assertFalse(S.photo_holds_heavy())
        self._holds = 19
        self.assertFalse(S.photo_holds_heavy())
        self._holds = 20
        self.assertTrue(S.photo_holds_heavy())
        self._holds = 313
        self.assertTrue(S.photo_holds_heavy())

    def test_backfill_submit_deferred_when_holds_heavy(self):
        self._holds = 25
        out = S.submit("skip-backfill", fetch=True, urgent=False)
        self.assertIsNone(out)
        self.assertNotIn("skip-backfill", S._FLOW)
        self.assertNotIn("skip-backfill", S._FWAIT)
        # Urgent work still queues.
        fut = S.submit("prio-held", fetch=True, urgent=True)
        self.assertIsNotNone(fut)
        self.assertIn("prio-held", S._FHIGH)

    def test_backfill_submit_queues_when_holds_are_low(self):
        self._holds = 0
        fut = S.submit("bf-ok", fetch=True, urgent=False)
        self.assertIsNotNone(fut)
        self.assertIn("bf-ok", S._FLOW)

    def test_warm_evicts_flow_when_at_cap(self):
        self._holds = 0
        # Fill the cap with low-priority backfill.
        for i in range(S._WARM_CAP):
            S.submit(f"bf-{i:03d}", fetch=True, urgent=False)
        self.assertGreaterEqual(len(S._FLOW), S._WARM_CAP)
        self.assertGreaterEqual(S._card_queue_depth(), S._WARM_CAP)
        flow_before = len(S._FLOW)

        import story_photo as SP
        orig_get, orig_has = SP.get_card, SP.card_has_photo
        try:
            SP.get_card = lambda cid: None
            SP.card_has_photo = lambda cid: False
            S._SC.pop("prio-wire", None)
            S.warm("prio-wire")
        finally:
            SP.get_card, SP.card_has_photo = orig_get, orig_has

        self.assertIn("prio-wire", S._FHIGH)
        self.assertNotIn("prio-wire", S._FLOW)
        self.assertLess(len(S._FLOW), flow_before)


if __name__ == "__main__":
    unittest.main()
