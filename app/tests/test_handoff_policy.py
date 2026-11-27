"""Deploy handoff policy: busy-peer timeouts vs going public empty.

Run: cd app && python3 -m unittest tests.test_handoff_policy -v
"""
import os, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff_db


class ErrIsTimeout(unittest.TestCase):
    def test_read_operation_timed_out(self):
        self.assertTrue(handoff_db.err_is_timeout(TimeoutError("The read operation timed out")))
        self.assertTrue(handoff_db.err_is_timeout(Exception("The read operation timed out")))
        self.assertTrue(handoff_db.err_is_timeout("The read operation timed out"))

    def test_urlerror_reason(self):
        class E(Exception):
            def __init__(self):
                super().__init__("<urlopen error timed out>")
                self.reason = TimeoutError("timed out")
        self.assertTrue(handoff_db.err_is_timeout(E()))

    def test_not_timeout(self):
        self.assertFalse(handoff_db.err_is_timeout(Exception("no live peer with data (HTTP 404)")))
        self.assertFalse(handoff_db.err_is_timeout("export bulk -> HTTP 500"))
        self.assertFalse(handoff_db.err_is_timeout(Exception("connection refused")))


class PublicEmpty(unittest.TestCase):
    def test_cold_start_may_go_public_empty(self):
        self.assertTrue(handoff_db.allow_public_without_data({"state": "gave_up", "peer_boot": None}))
        self.assertTrue(handoff_db.allow_public_without_data({"state": "off"}))

    def test_peer_seen_must_not_go_public_empty(self):
        self.assertFalse(handoff_db.allow_public_without_data({"state": "gave_up", "peer_boot": "abc123"}))
        self.assertFalse(handoff_db.allow_public_without_data({"state": "done", "peer_boot": "abc123"}))


class RenderAppSource(unittest.TestCase):
    def test_source_retries_timeouts_and_exposes_spend_seed(self):
        src = (Path(__file__).resolve().parents[1] / "render_app.py").read_text()
        self.assertIn("/internal/writer/spend", src)
        self.assertIn("story_writer.seed_spend", src)
        self.assertIn("if _handoff_timeout_detail(ex):", src)
        self.assertIn("allow_public_without_data(HANDOFF)", src)
        self.assertIn('BN_HANDOFF_PEER_HEALTHZ_S", "30"', src)
        self.assertIn('BN_HANDOFF_OWNED_S", "300"', src)
        # Thread guard must stay untouched by this change.
        self.assertIn("BLOCK_THREAD_NAMES", src)


if __name__ == "__main__":
    unittest.main()
