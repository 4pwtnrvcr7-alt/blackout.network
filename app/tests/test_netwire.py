import os, sys, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netwire

NOW = datetime(2026, 11, 27, 19, 30, tzinfo=timezone.utc)

def row(**k):
    d = {"id": "bbbbbbbbbbbbbbbb", "title": "Malawi: internet outage, 10.0 h (IODA)", "place": "Malawi",
         "cc": "MW", "t": "2026-11-27T12:00:00Z", "src": "IODA internet outages",
         "url": "https://ioda.inetintel.cc.gatech.edu/country/MW", "lat": -13.4, "lon": 33.6, "rank": 3}
    d.update(k)
    return d

class T(unittest.TestCase):
    def test_current_ioda_from_duration(self):
        s = netwire.story_from(row(), now=NOW)
        self.assertEqual(s["kind"], "internet")
        self.assertTrue(s["cur"])
        self.assertEqual(s["hours"], 10.0)
        self.assertEqual(s["href"], "/wire/bbbbbbbbbbbbbbbb")
        self.assertEqual(s["end"], "2026-11-27T22:00:00Z")

    def test_ended_ioda_not_current(self):
        s = netwire.story_from(row(t="2026-11-26T02:05:00Z", title="Malawi: internet outage, 10.0 h (IODA)"), now=NOW)
        self.assertFalse(s["cur"])
        self.assertEqual(s["kind"], "internet")

    def test_status_page_incident_is_cloud_not_internet(self):
        s = netwire.story_from(row(
            title="Anthropic outage: Degraded performance for Claude Fable 5.2 (major impact, monitoring)",
            src="Anthropic status (major/critical incidents)", place="Global (internet)", cc=None,
        ), now=NOW)
        self.assertEqual(s["kind"], "cloud")
        self.assertNotEqual(s["kind"], "internet")

    def test_power_story(self):
        s = netwire.story_from(row(
            title="More than 424,000 are without power from New York to North Carolina",
            src="Telegram @CIG_telegram", place="New York", cc="US", t="2026-11-27T18:03:29Z",
        ), now=NOW)
        self.assertEqual(s["kind"], "power")

    def test_countries_and_daily(self):
        b = netwire.stories_from_rows([
            row(),
            row(id="cccccccccccccccc", title="Macedonia: internet outage, 8.2 h (IODA)",
                place="Macedonia", cc="MK", t="2026-11-26T02:00:00Z", lat=41.5, lon=21.5),
        ], now=NOW)
        self.assertEqual(len(b["internet"]), 2)
        self.assertTrue(b["internet"][0]["cur"])  # current first
        cs = netwire.countries(b["internet"], now=NOW)
        self.assertEqual({c["cc"] for c in cs}, {"MW", "MK"})
        mw = [c for c in cs if c["cc"] == "MW"][0]
        self.assertTrue(mw["cur"])
        self.assertEqual(mw["href"], "/wire/bbbbbbbbbbbbbbbb")
        self.assertEqual(mw["src"], "IODA internet outages")
        daily = netwire.daily_from(b["internet"], 30, NOW)
        self.assertEqual(sum(daily), 2)
        self.assertGreater(daily[-1], 0)  # today (Malawi)

    def test_apply_inet_empty_wire_clears_all_down(self):
        dead = {"all_down": True, "via": "none", "places": {
            "C:FR": {"k": "C:FR", "name": "France", "level": -1, "status": "No data", "signals": []}}}
        out = netwire.apply_inet(dead, {"internet": [], "ok": True}, now=NOW)
        self.assertFalse(out["all_down"])
        self.assertEqual(out["places"]["C:FR"]["status"], "Normal")
        self.assertEqual(out["counts"]["no_data"], 0)

    def test_apply_inet_marks_current_country(self):
        dead = {"all_down": True, "via": "none", "places": {
            "C:MW": {"k": "C:MW", "name": "Malawi", "level": -1, "status": "No data", "signals": []},
            "C:FR": {"k": "C:FR", "name": "France", "level": -1, "status": "No data", "signals": []}}}
        b = netwire.stories_from_rows([row()], now=NOW)
        out = netwire.apply_inet(dead, b, now=NOW)
        self.assertFalse(out["all_down"])
        self.assertEqual(out["via"], "wire")
        self.assertEqual(out["places"]["C:MW"]["status"], "Outage")
        self.assertEqual(out["places"]["C:FR"]["status"], "Normal")
        self.assertEqual(out["places"]["C:MW"]["wire"][0]["url"], "/wire/bbbbbbbbbbbbbbbb")


    def test_prefers_event_time_over_activity_t(self):
        # heat t is last activity; 61.3 h from that would still look current
        s = netwire.story_from(row(
            t="2026-11-26T12:04:48Z",
            event_time="2026-11-23T22:47:00Z",
            title="Tashkent, Uzbekistan: internet outage, 61.3 h (IODA)",
            place="Tashkent, Uzbekistan", cc="UZ",
        ), now=NOW)
        self.assertFalse(s["cur"])
        self.assertEqual(s["t"], "2026-11-23T22:47:00Z")
        self.assertEqual(s["end"], "2026-11-26T12:05:00Z")

    def test_ioda_url_from_beats_activity_t(self):
        s = netwire.story_from(row(
            t="2026-11-26T12:04:48Z",
            title="Tashkent, Uzbekistan: internet outage, 61.3 h (IODA)",
            place="Tashkent, Uzbekistan", cc="UZ",
            url="https://ioda.inetintel.cc.gatech.edu/region/4473?from=1795470420&until=1795481683",
        ), now=NOW)
        self.assertFalse(s["cur"])
        self.assertEqual(s["t"], "2026-11-23T21:47:00Z")

    def test_load_prefers_sql_event_time(self):
        heat = [row(t="2026-11-26T12:04:48Z",
                    title="Tashkent, Uzbekistan: internet outage, 61.3 h (IODA)",
                    place="Tashkent, Uzbekistan", cc="UZ")]
        sql = [row(t="2026-11-23T22:47:00Z", event_time="2026-11-23T22:47:00Z",
                   title="Tashkent, Uzbekistan: internet outage, 61.3 h (IODA)",
                   place="Tashkent, Uzbekistan", cc="UZ")]
        orig_sql, orig_heat = netwire._sql_rows, netwire._heat_rows
        try:
            netwire._sql_rows = lambda days=7: sql
            netwire._heat_rows = lambda: heat
            b = netwire.load(now=NOW)
        finally:
            netwire._sql_rows, netwire._heat_rows = orig_sql, orig_heat
        self.assertFalse(b["internet"][0]["cur"])
        self.assertEqual(b["internet"][0]["t"], "2026-11-23T22:47:00Z")


    def test_ended_ioda_has_week_band(self):
        s = netwire.story_from(row(t="2026-11-26T02:05:00Z", title="Malawi: internet outage, 10.0 h (IODA)"), now=NOW)
        self.assertFalse(s["cur"])
        self.assertEqual(s["band"], "7d")

    def test_current_is_6h_band(self):
        s = netwire.story_from(row(), now=NOW)
        self.assertTrue(s["cur"])
        self.assertEqual(s["band"], "6h")

    def test_recent_end_is_6h_even_if_not_current(self):
        # ended 2 h ago, outside 75 min grace so not current, still in the last 6 h
        s = netwire.story_from(row(t="2026-11-27T11:30:00Z", title="Malawi: internet outage, 6.0 h (IODA)"), now=NOW)
        self.assertFalse(s["cur"])
        self.assertEqual(s["band"], "6h")

    def test_layer_kinds(self):
        self.assertEqual(netwire.story_from(row(title="Oroville Dam spillway damaged after heavy rain", place="California", cc="US", t="2026-11-27T18:00:00Z"), now=NOW)["kind"], "hydro")
        self.assertEqual(netwire.story_from(row(title="Undersea cable cut disrupts traffic in the Red Sea", place="Red Sea", t="2026-11-27T10:00:00Z"), now=NOW)["kind"], "cable")
        self.assertEqual(netwire.story_from(row(title="Fire at a Dallas data center takes websites offline", place="Dallas", cc="US", t="2026-11-27T18:00:00Z"), now=NOW)["kind"], "dc")
        self.assertEqual(netwire.story_from(row(title="Cellular outage hits cell towers across Ohio", place="Ohio", cc="US", t="2026-11-27T18:00:00Z"), now=NOW)["kind"], "towers")

    def test_pill_internet_24h_and_empty_hydro(self):
        b = netwire.stories_from_rows([
            row(),
            row(id="cccccccccccccccc", title="Macedonia: internet outage, 8.2 h (IODA)",
                place="Macedonia", cc="MK", t="2026-11-26T02:00:00Z", lat=41.5, lon=21.5),
        ], now=NOW)
        layers = netwire.layers(b, now=NOW)
        self.assertEqual(layers["internet"]["n6"], 1)
        self.assertEqual(layers["internet"]["n7"], 2)
        self.assertEqual(netwire.pill_text(["hydro"], layers), "No dam incidents on the Wire in the last 7 days")
        txt = netwire.pill_text(["internet"], layers)
        self.assertIn("internet outages in 24 h", txt)
        self.assertIn("U.S.: none major", txt)

    def test_apply_inet_sets_band_for_ended_story(self):
        dead = {"all_down": True, "via": "none", "places": {
            "C:MW": {"k": "C:MW", "name": "Malawi", "level": -1, "status": "No data", "signals": []}}}
        b = netwire.stories_from_rows([row(t="2026-11-26T02:05:00Z")], now=NOW)
        out = netwire.apply_inet(dead, b, now=NOW)
        self.assertEqual(out["places"]["C:MW"]["band"], "7d")
        self.assertIn(out["places"]["C:MW"]["wire"][0]["band"], ("7d",))


if __name__ == "__main__":
    unittest.main()
