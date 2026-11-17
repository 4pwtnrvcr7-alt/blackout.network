import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import newsletter_v4 as V4

class V4Tests(unittest.TestCase):
    def test_flag(self):
        os.environ.pop("BN_NL_V4", None); self.assertTrue(V4.on({}))
        os.environ["BN_NL_V4"] = "0"; self.assertFalse(V4.on({})); os.environ.pop("BN_NL_V4", None)
        self.assertFalse(V4.on({"template": "v2"}))
    def test_rank_colours(self):
        self.assertEqual(V4.rank_col(7), V4.RED); self.assertEqual(V4.rank_col(10), V4.RED)
        self.assertNotEqual(V4.rank_col(6), V4.RED)
    def test_pool_rotates_without_repeats(self):
        P = V4.pool(); self.assertTrue(P.get("war"))
        from datetime import datetime, timezone
        seen = []
        for n in range(len(P["war"])):
            iss = {"end": datetime(2026, 11, 17, 23, tzinfo=timezone.utc), "slot": "evening"}
            seen.append(P["war"][(V4.issue_no(iss) + n) % len(P["war"])]["name"])
        self.assertEqual(len(set(seen)), len(P["war"]))
        for ims in P.values():
            for im in ims: self.assertTrue(os.path.exists(os.path.join(os.path.dirname(V4.__file__), "theme_static", "media", im["name"] + ".b64")))

if __name__ == "__main__": unittest.main()
