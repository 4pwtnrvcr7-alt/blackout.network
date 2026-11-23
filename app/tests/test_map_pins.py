"""Story-map pins require a verified, specific location (Nov 23 2026, pt1761u / pt1762u)."""
import os, sys, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import map_pins

EDGE_TITLE = "7/10 Major: Edgewater declares state of emergency amid flooding"

class MapPins(unittest.TestCase):
    def test_edgewater_depew_is_dropped(self):
        self.assertFalse(map_pins.eligible(
            title=EDGE_TITLE, place="Depew, New York, United States",
            precision="city", tier="exact", lat=42.905, lon=-78.692, cc="US"))

    def test_matching_city_is_kept(self):
        self.assertTrue(map_pins.eligible(
            title="Edgewater declares state of emergency amid flooding",
            place="Edgewater, Florida, United States",
            precision="city", tier="exact", lat=28.988, lon=-80.902, cc="US"))

    def test_country_centroid_is_dropped(self):
        self.assertFalse(map_pins.eligible(
            title="Earthquake in Japan", place="Japan",
            precision="country", tier="approx", lat=36.0, lon=138.0, cc="JP"))

    def test_no_location_is_dropped(self):
        self.assertFalse(map_pins.eligible(
            title="Global software outage", place="", precision="", tier="global"))

    def test_low_confidence_and_ambiguous_are_dropped(self):
        self.assertFalse(map_pins.eligible(
            title="Talks in Georgia", place="Georgia, United States",
            precision="state", tier="exact", lat=32.9, lon=-83.4, cc="US",
            confidence="low"))
        self.assertFalse(map_pins.eligible(
            title="Talks in Georgia", place="Tbilisi, Georgia",
            precision="city", tier="exact", lat=41.7, lon=44.8, cc="GE",
            how="several places named"))

    def test_state_named_in_headline_is_kept(self):
        self.assertTrue(map_pins.eligible(
            title="Gov. Katie Hobbs declares a state of emergency as storms batter Arizona",
            place="Arizona, United States",
            precision="state", tier="exact", lat=34.2, lon=-111.6, cc="US"))

    def test_open_water_is_dropped(self):
        # Mid-Atlantic; skip the assertion if PIP data is unavailable in this checkout.
        mid = map_pins.on_water(30.0, -40.0)
        if mid is False and map_pins.on_water(39.8, -98.6) is False:
            self.skipTest("country PIP unavailable")
        self.assertTrue(mid)
        self.assertFalse(map_pins.eligible(
            title="Ship adrift in the mid-Atlantic", place="Atlantic Ocean",
            precision="point", tier="exact", lat=30.0, lon=-40.0))

    def test_heat_rows_stay_in_the_list_without_a_pin(self):
        cols = ["id", "lat", "lon", "rank", "cat", "t", "title", "place", "prec", "tier", "how"]
        rows = [
            ["ok", 28.988, -80.902, 7, "weather", "t", "Flooding in Edgewater, Florida", "Edgewater, Florida, United States", "city", "exact", "geo"],
            ["bad", 42.905, -78.692, 7, "politics", "t", EDGE_TITLE, "Depew, New York, United States", "city", "exact", "geo"],
            ["co", 36.0, 138.0, 4, "disaster", "t", "Earthquake in Japan", "Japan", "country", "approx", "geo"],
        ]
        out, dropped = map_pins.filter_heat_rows(rows, cols)
        self.assertEqual(len(out), 3)
        self.assertEqual(dropped, 2)
        self.assertEqual(out[0][1], 28.988)
        self.assertIsNone(out[1][1])
        self.assertEqual(out[1][9], "global")
        self.assertIsNone(out[2][1])

    def test_filter_points_drops_country_and_contradiction(self):
        pts = [
            {"title": "Flooding in Edgewater, Florida", "place": "Edgewater, Florida, United States",
             "precision": "city", "exact": True, "lat": 28.988, "lon": -80.902, "cc": "US"},
            {"title": EDGE_TITLE, "place": "Depew, New York, United States",
             "precision": "city", "exact": True, "lat": 42.905, "lon": -78.692, "cc": "US"},
            {"title": "Earthquake in Japan", "place": "Japan",
             "precision": "country", "exact": False, "approximate": True, "lat": 36.0, "lon": 138.0, "cc": "JP"},
        ]
        kept, dropped = map_pins.filter_points(pts)
        self.assertEqual(dropped, 2)
        self.assertEqual(len(kept), 1)
        self.assertIn("Edgewater", kept[0]["place"])

if __name__ == "__main__":
    unittest.main()
