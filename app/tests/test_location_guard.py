"""Location-accuracy guard (Matt, Nov 23 2026, 12:37 PM ET, pt1767u).

Runs on every PR and must pass before a deploy. Also run live with:
  cd app && python3 -m location_guard --live

The No location chip is an honest count and is not removed by this test.
"""
import os, sys, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import location_guard as G


class LocationGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile, geo
        geo.GDB = os.path.join(tempfile.mkdtemp(), "geo.db")
        geo.gaz()

    def test_baseline_file_is_present_and_honest(self):
        b = G.load_baseline()
        self.assertEqual(b["window_days"], 7)
        self.assertEqual(b["total"], 4134)
        self.assertEqual(b["located"], 1933)
        self.assertEqual(b["no_location"], 2201)
        self.assertAlmostEqual(b["no_location_share_pct"], 53.24, places=2)
        self.assertEqual(b["tolerance_points"], 2.0)
        self.assertEqual(b["no_location"] + b["located"], b["total"])
        # The chip stays: the baseline is the No location count, not a hidden or zeroed figure.
        self.assertGreater(b["no_location"], 0)
        self.assertIn("No location", b["notes"])

    def test_share_fails_when_it_rises_more_than_two_points(self):
        b = G.load_baseline()
        base = b["no_location_share_pct"]
        ok, info = G.share_ok(base)
        self.assertTrue(ok)
        ok, info = G.share_ok(base + 2.0)
        self.assertTrue(ok)
        ok, info = G.share_ok(base + 2.01)
        self.assertFalse(ok)
        self.assertGreater(info["live_pct"], info["max_allowed_pct"])
        ok, _ = G.share_ok(base - 5.0)  # an improvement is not a failure
        self.assertTrue(ok)

    def test_golden_set_has_about_forty_tricky_stories(self):
        data = G.load_golden()
        n = len(data["cases"])
        self.assertGreaterEqual(n, 35)
        self.assertLessEqual(n, 50)
        ids = {c["id"] for c in data["cases"]}
        for need in ("edgewater-fl-not-depew", "barr-remarks-in-milan",
                     "paraguay-senate-impeaches-not-colombia", "joe-wilson-is-not-a-city",
                     "kyiv-not-pulled-to-actor-country"):
            self.assertIn(need, ids)

    def test_golden_pins_are_correct(self):
        """A story that clearly states a location must never show as no location, and must not land in the wrong place."""
        result = G.check_golden()
        if not result["ok"]:
            lines = []
            for f in result["failures"]:
                lines.append("%s: %s | %s" % (f.get("id"), f.get("problems") or f.get("error"), f.get("got")))
            self.fail("%s of %s golden cases failed:\n%s" % (len(result["failures"]), result["checked"], "\n".join(lines)))

    def test_contradiction_fixtures(self):
        result = G.check_contradiction_fixtures()
        if not result["ok"]:
            self.fail("contradiction fixtures failed: " + str(result["failures"]))

    def test_ward_ala_is_not_ward_county_texas(self):
        self.assertTrue(G.pin_contradicts_headline(
            "Explosion in Ward, Ala.", "Ward County, Texas, United States", "US", "US.TX"))
        self.assertFalse(G.pin_contradicts_headline(
            "A MASSIVE PIPELINE EXPLOSION lit up the night sky near Ward, Alabama, last night",
            "Sumter County, Alabama", "US", "US.AL"))

    def test_live_share_when_configured(self):
        if not os.environ.get("LOCATION_GUARD_LIVE"):
            self.skipTest("LOCATION_GUARD_LIVE not set; run: python3 -m location_guard --live")
        body = G.fetch_heat(os.environ["LOCATION_GUARD_LIVE"])
        cov = G.coverage_from_heat(body)
        ok, info = G.share_ok(cov.get("no_location_share_pct"))
        if not ok:
            self.fail("7-day no-location share is %s, more than 2 points above baseline %s" % (
                info.get("live_pct"), info.get("baseline_pct")))


if __name__ == "__main__":
    unittest.main()
