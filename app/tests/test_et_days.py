"""7-day ET chart window: ends today, no future days, not a 168-hour UTC slice."""
import sys, os, unittest
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import et_days

class EtLastDays(unittest.TestCase):
    def test_seven_days_ending_today_et_on_nov_11(self):
        # 16:51 UTC on Nov 11 2026 is 11:51 AM ET. Window is Nov 5-11, not Nov 4-14.
        now = datetime(2026, 11, 11, 16, 51, 12, tzinfo=timezone.utc)
        days = et_days.et_last_days(7, now)
        self.assertEqual(days, [
            "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08",
            "2026-11-09", "2026-11-10", "2026-11-11",
        ])
        self.assertEqual(len(days), 7)
        self.assertEqual(days[-1], "2026-11-11")
        self.assertNotIn("2026-11-04", days)
        self.assertNotIn("2026-11-12", days)
        self.assertNotIn("2026-11-14", days)

    def test_just_after_midnight_et(self):
        # 00:30 ET Nov 11 = 05:30 UTC Nov 11. Today is still Nov 11; Nov 4 is out.
        now = datetime(2026, 11, 11, 5, 30, tzinfo=timezone.utc)
        days = et_days.et_last_days(7, now)
        self.assertEqual(days[0], "2026-11-05")
        self.assertEqual(days[-1], "2026-11-11")

    def test_late_evening_et_not_next_utc_day(self):
        # 11:30 PM ET Nov 11 = 04:30 UTC Nov 12. Today ET is still Nov 11.
        now = datetime(2026, 11, 12, 4, 30, tzinfo=timezone.utc)
        days = et_days.et_last_days(7, now)
        self.assertEqual(days[-1], "2026-11-11")
        self.assertNotIn("2026-11-12", days)

    def test_dst_spring_forward(self):
        # 2026-03-08 is the US spring-forward Sunday. 7 days ending that date.
        now = datetime(2026, 3, 8, 16, 0, tzinfo=timezone.utc)  # 12:00 EDT
        days = et_days.et_last_days(7, now)
        self.assertEqual(len(days), 7)
        self.assertEqual(days[-1], "2026-03-08")
        self.assertEqual(days[0], "2026-03-02")


class EtDay(unittest.TestCase):
    def test_utc_prefix_is_not_the_et_date(self):
        # 04:00 UTC Nov 12 is 11:00 PM ET Nov 11.
        self.assertEqual(et_days.et_day("2026-11-12T04:00:00Z"), "2026-11-11")
        self.assertEqual(et_days.et_day("2026-11-11T16:00:00Z"), "2026-11-11")

    def test_unix_seconds(self):
        ts = datetime(2026, 11, 11, 16, 51, tzinfo=timezone.utc).timestamp()
        self.assertEqual(et_days.et_day(ts), "2026-11-11")


class BucketVolumeTrend(unittest.TestCase):
    def test_drops_future_and_pre_window_dates_and_zero_fills(self):
        days = [
            "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08",
            "2026-11-09", "2026-11-10", "2026-11-11",
        ]
        rows = [
            {"t": "2026-11-04T20:00:00Z", "category": "war/conflict", "score": 40, "watchlist": 0},  # before window
            {"t": "2026-11-11T16:00:00Z", "category": "war/conflict", "score": 64, "watchlist": 0},
            {"t": "2026-11-11T17:00:00Z", "category": "natural disaster", "score": 20, "watchlist": 0},
            {"t": "2026-11-12T16:00:00Z", "category": "natural disaster", "score": 50, "watchlist": 0},  # future
            {"t": "2026-11-14T00:00:00Z", "category": "natural disaster", "score": 36, "watchlist": 0},
            {"t": "2026-11-05T15:00:00Z", "category": "disease", "score": 86, "watchlist": 0},
            {"t": "2026-11-10T12:00:00Z", "category": "war/conflict", "score": 10, "watchlist": 1},  # volume only
        ]
        vol, trend = et_days.bucket_volume_trend(rows, days, high_threshold=60)
        self.assertEqual([t["d"] for t in trend], days)
        self.assertEqual(len(trend), 7)
        vol_dates = {v["d"] for v in vol}
        self.assertNotIn("2026-11-04", vol_dates)
        self.assertNotIn("2026-11-12", vol_dates)
        self.assertNotIn("2026-11-14", vol_dates)
        self.assertEqual({(v["d"], v["category"], v["n"]) for v in vol}, {
            ("2026-11-11", "war/conflict", 1),
            ("2026-11-11", "natural disaster", 1),
            ("2026-11-05", "disease", 1),
            ("2026-11-10", "war/conflict", 1),
        })
        t11 = next(t for t in trend if t["d"] == "2026-11-11")
        self.assertEqual(t11["mx"], 64)
        self.assertEqual(t11["high"], 1)
        self.assertEqual(t11["avg"], 42.0)  # (64+20)/2
        t06 = next(t for t in trend if t["d"] == "2026-11-06")
        self.assertEqual(t06, {"d": "2026-11-06", "mx": 0, "avg": 0, "high": 0})
        t10 = next(t for t in trend if t["d"] == "2026-11-10")
        # watchlist item is not in the severity trend
        self.assertEqual(t10["n"] if "n" in t10 else t10["mx"], 0)
        self.assertEqual(t10["mx"], 0)


if __name__ == "__main__":
    unittest.main()
