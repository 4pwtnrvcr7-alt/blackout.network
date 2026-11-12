"""Earthquakes card: counts on every bar including 0, title '24 hours', x-axis 'Magnitude',
live 'Biggest this week' line from the USGS week feed (not hardcoded).
Run: cd app && python3 -m unittest tests.test_quakechart -v
"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import apple_v1 as A

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "bn-apple-home.js")
CSS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "bn-apple.css")


class WeekBig(unittest.TestCase):
    def test_prefers_now_quake_biggest(self):
        q = {"biggest": {"mag": 6.4, "place": "30 km WSW of Testville", "t": "2026-11-10T12:00:00Z", "tsunami": 0, "url": "https://example.test/q"}}
        lst = [{"mag": 7.1, "place": "should not win", "t": "2026-11-09T00:00:00Z"}]
        got = A.week_big_quake(q, lst)
        self.assertEqual(got["mag"], 6.4)
        self.assertEqual(got["place"], "30 km WSW of Testville")
        self.assertEqual(got["url"], "https://example.test/q")

    def test_falls_back_to_week_map_max(self):
        lst = [
            {"mag": 4.8, "place": "near A", "t": "2026-11-09T00:00:00Z"},
            {"mag": 5.9, "place": "near B", "t": "2026-11-08T00:00:00Z", "tsunami": 1, "url": "https://example.test/b"},
            {"place": "no mag"},
        ]
        got = A.week_big_quake({}, lst)
        self.assertEqual(got["mag"], 5.9)
        self.assertEqual(got["place"], "near B")
        self.assertEqual(got["tsunami"], 1)

    def test_empty_is_none(self):
        self.assertIsNone(A.week_big_quake({}, []))
        self.assertIsNone(A.week_big_quake(None, None))
        self.assertIsNone(A.week_big_quake({"biggest": {"place": "no mag"}}, []))


class ChartMarkup(unittest.TestCase):
    def setUp(self):
        with open(JS) as f:
            self.js = f.read()
        with open(CSS) as f:
            self.css = f.read()

    def test_bars_options_and_helpers(self):
        self.assertIn('title:"24 hours"', self.js)
        self.assertIn('axis:"Magnitude"', self.js)
        self.assertIn("counts:1", self.js)
        self.assertIn("Biggest this week:", self.js)
        self.assertIn("function quakeBars", self.js)
        self.assertIn("function weekBig", self.js)
        self.assertIn("q.week_big", self.js)
        self.assertIn("c:quakeBars(q)", self.js)
        self.assertIn("+quakeBars(q)", self.js)
        self.assertNotIn("Last 24 hours by magnitude", self.js)
        # Must not bake a specific event into the source.
        self.assertNotIn("Solomon", self.js)
        self.assertNotIn("Lata", self.js)

    def test_counts_include_zero(self):
        # Count row is built from every column total, including 0; not skipped when the bar is empty.
        self.assertIn("o.counts", self.js)
        self.assertIn("barTot(c)", self.js)
        self.assertIn("bna-cn", self.js)
        self.assertIn(".bna-cht", self.css)
        self.assertIn(".bna-cax", self.css)
        self.assertIn(".bna-qwk", self.css)

    def test_no_hardcoded_place_in_python(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apple_v1.py")).read()
        self.assertIn("week_big_quake", src)
        self.assertIn('"week_big": week_big_quake(q, lst)', src)
        self.assertNotIn("Solomon", src)
        self.assertNotIn("Lata", src)


if __name__ == "__main__":
    unittest.main()
