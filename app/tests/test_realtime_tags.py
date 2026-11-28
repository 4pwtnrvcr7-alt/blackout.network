"""Realtime Wire: free tag fills when the stored category is 'other', and no 5-min tag-hold trap.

Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_realtime_tags tests.test_wire_check -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wire_check as WC
import x_share


def _tags(title, stored="other"):
    k = WC.category(stored, title, "")
    item = {"title": title, "headline": title, "brief": "", "location": "", "category": stored}
    raw = x_share._entity_first(item)
    lt = x_share.location_tags(item)
    return k, WC.tags(raw, k, title, lt)


class RescueOtherCategory(unittest.TestCase):
    def test_strike_is_conflict(self):
        k, tg = _tags("#BREAKING - CENTCOM have just announced a U.S. strike on an Iranian Vessel attempting to smuggle")
        self.assertEqual(k, "conflict")
        self.assertGreaterEqual(len(tg), 3)
        self.assertLessEqual(len(tg), 5)
        self.assertIn("#US", tg)
        self.assertIn("#Conflict", tg)
        self.assertTrue("#CENTCOM" in tg or "#Iran" in tg)
        self.assertNotIn("#IranianVessel", tg)  # long run-together
        self.assertNotIn("#News", tg)
        self.assertNotIn("#BlackoutNetwork", tg)

    def test_cyberbullying_is_cyber(self):
        k, tg = _tags("From cyberbullying to extremist content, can EU Kids Act protect minors online?")
        self.assertEqual(k, "cyber")
        self.assertGreaterEqual(len(tg), 3)
        self.assertIn("#EU", tg)
        self.assertTrue("#Cybersecurity" in tg or "#Hacking" in tg)

    def test_high_wind_warning_is_weather(self):
        k, tg = _tags("High Wind Warning issued November 27 at 10:08AM MST until November 28 at 6:00PM")
        self.assertEqual(k, "weather")
        self.assertGreaterEqual(len(tg), 3)
        self.assertIn("#Weather", tg)

    def test_witkoff_putin_is_politics(self):
        k, tg = _tags("Kushner's and Witkoff's negotiating objective is, in essence, to convince Putin")
        self.assertEqual(k, "politics")
        self.assertGreaterEqual(len(tg), 3)
        self.assertIn("#Putin", tg)
        self.assertIn("#Kushner", tg)
        self.assertIn("#Witkoff", tg)

    def test_stored_other_stays_other_when_no_evidence(self):
        k, tg = _tags("A scheduled maintenance window is planned later this week")
        self.assertEqual(k, "other")


class TagHoldRecheck(unittest.TestCase):
    def test_tag_holds_recheck_faster_than_five_minutes(self):
        import wire_timeline as WT
        self.assertLessEqual(WT._V_TAG_RECHECK_S, 60)
        self.assertGreaterEqual(WT._V_TAG_RECHECK_S, 30)
        self.assertLess(WT._V_TAG_RECHECK_S, 300)

    def test_thin_headline_rechecks_as_fast_as_tags(self):
        import inspect, wire_timeline as WT
        src = inspect.getsource(WT._warm_validate)
        self.assertIn("thin_hold", src)
        self.assertIn("thin-headline", src)


class HazardWeatherAndKnownFills(unittest.TestCase):
    def test_meteoalarm_thunderstorm_stored_hazard_becomes_weather(self):
        title = "Greece: Orange thunderstorm warning, 2 areas (Thessalia, Central Makedonia) - MeteoAlarm"
        k, tg = _tags(title, stored="hazard")
        self.assertEqual(k, "weather")
        self.assertGreaterEqual(len(tg), 3)
        self.assertLessEqual(len(tg), 5)
        self.assertIn("#Weather", tg)
        self.assertTrue("#Storm" in tg or "#Greece" in tg or "#MeteoAlarm" in tg)
        self.assertNotIn("#News", tg)
        self.assertNotIn("#BlackoutNetwork", tg)

    def test_chemical_hazard_does_not_become_weather(self):
        title = "Chemical spill warning after a toxic leak at the plant prompts an evacuation"
        k, tg = _tags(title, stored="hazard")
        self.assertEqual(k, "hazard")

    def test_geofon_kamchatka_quake_gets_three_tags(self):
        title = "GEOFON: M5.0 earthquake Off East Coast of Kamchatka"
        k, tg = _tags(title, stored="quake")
        self.assertEqual(k, "quake")
        self.assertGreaterEqual(len(tg), 3)
        self.assertTrue("#GEOFON" in tg or "#Kamchatka" in tg)
        self.assertTrue("#Earthquake" in tg or "#Seismic" in tg)
        self.assertNotIn("#OffEastCoast", tg)

    def test_lukoil_refinery_strike_gets_three_tags(self):
        title = "Ukraine hits Lukoil's Novoshakhtinsk Perm refinery halting production as a strike on a Zap"
        k, tg = _tags(title, stored="conflict")
        self.assertEqual(k, "conflict")
        self.assertGreaterEqual(len(tg), 3)
        self.assertIn("#Ukraine", tg)
        self.assertTrue("#Lukoil" in tg or "#Conflict" in tg)
        self.assertNotIn("#Novoshakhtinsk", tg)

    def test_hamas_assassination_people_gets_three_tags(self):
        title = "Hamas says attempted assassination of its leader’s son is continuation of ‘criminal policy"
        k, tg = _tags(title, stored="people")
        self.assertEqual(k, "people")
        self.assertGreaterEqual(len(tg), 3)
        self.assertIn("#Hamas", tg)
        self.assertTrue("#Attack" in tg)
        self.assertNotIn("#News", tg)

    def test_no_long_run_together_or_filler(self):
        title = "High Wind Watch issued November 27 at 1:39PM EST until November 30 at 1:00AM EST"
        k, tg = _tags(title, stored="hazard")
        self.assertEqual(k, "weather")
        self.assertGreaterEqual(len(tg), 3)
        self.assertTrue(all(len(t.lstrip("#")) <= 12 or t.lstrip("#").lower() in {x.lower() for x in (WC._EXTRA | WC._ACRO)} for t in tg))
        self.assertNotIn("#News", tg)
        self.assertNotIn("#BlackoutNetwork", tg)
        self.assertNotIn("#HighWindWatch", tg)

    def test_israeli_gentilic_fills_israel(self):
        title = "Western sanctions on Israeli settlers serve to shield the Israeli state"
        k, tg = _tags(title, stored="politics")
        self.assertEqual(k, "politics")
        self.assertGreaterEqual(len(tg), 3)
        self.assertIn("#Israel", tg)
        self.assertIn("#Sanctions", tg)
        self.assertNotIn("#News", tg)



if __name__ == "__main__":
    unittest.main()
