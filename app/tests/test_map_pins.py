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

    def test_city_not_in_headline_is_dropped_even_if_country_is(self):
        self.assertFalse(map_pins.eligible(
            title="Iran says it will use 'all means' to fight US sanctions",
            place="Tehran, Tehran, Iran",
            precision="city", tier="exact", lat=35.69, lon=51.39, cc="IR"))
        self.assertFalse(map_pins.eligible(
            title="Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel.",
            place="Benghazi, Banghazi, Libya",
            precision="city", tier="exact", lat=32.12, lon=20.07, cc="LY"))
        self.assertFalse(map_pins.eligible(
            title="This is what a Russian strike leaves behind. Izium, 19 Nov: the site after the strike",
            place="Kyiv, Kyiv City, Ukraine",
            precision="city", tier="exact", lat=50.45, lon=30.52, cc="UA"))

    def test_tehran_named_in_headline_is_kept(self):
        self.assertTrue(map_pins.eligible(
            title="Preliminary reports of explosions in southern Tehran, the capital of Iran.",
            place="Tehran, Tehran, Iran",
            precision="city", tier="exact", lat=35.69, lon=51.39, cc="IR"))

    def test_offset_and_spelling_variants_are_kept(self):
        self.assertTrue(map_pins.eligible(
            title="CSN: M5.0 earthquake 33 km al NE de Calama, Chile (depth 116 km)",
            place="38 km NE of Calama, Chile",
            precision="point", tier="exact", lat=-22.3, lon=-68.7, cc="CL"))
        self.assertTrue(map_pins.eligible(
            title="Russian ballistic missile strike on Ukraine’s Kryvyi Rih injures 20",
            place="Kryvyy Rih, Dnipropetrovsk, Ukraine",
            precision="city", tier="exact", lat=47.91, lon=33.39, cc="UA"))
        self.assertTrue(map_pins.eligible(
            title="#BREAKING : RUSSIAN STRIKE ON ZAPORIZHZHIA KILLS THREE",
            place="Zaporizhzhya, Zaporizhzhia, Ukraine",
            precision="city", tier="exact", lat=47.85, lon=35.17, cc="UA"))
        self.assertTrue(map_pins.eligible(
            title="Several Palestinians were injured in the Al-Tawbah area of Jabalia refugee camp in northern Gaza",
            place="Jabālyā, Gaza Strip, Palestinian Territory",
            precision="city", tier="exact", lat=31.53, lon=34.48, cc="PS"))
        self.assertTrue(map_pins.eligible(
            title="A Palestinian man was injured in central Khan Younis, southern Gaza Strip",
            place="Khān Yūnis, Gaza Strip, Palestinian Territory",
            precision="city", tier="exact", lat=31.35, lon=34.30, cc="PS"))
        self.assertTrue(map_pins.eligible(
            title="Drone attack targets oil storage facilities near Almetyevsk in Russia’s Tatarstan",
            place="Al’met’yevsk, Tatarstan Republic, Russia",
            precision="city", tier="exact", lat=54.90, lon=52.32, cc="RU"))

    def test_truncated_city_name_is_kept(self):
        self.assertTrue(map_pins.eligible(
            title="Princess Cruises’ Caribbean Princess, which left Port Everglades in Fort Lauder",
            place="Fort Lauderdale, Florida, United States",
            precision="city", tier="exact", lat=26.12, lon=-80.14, cc="US"))

    def test_quake_city_not_in_headline_is_dropped(self):
        # "Central Peru" names only the country, not Carhuamayo — no country-centroid pin.
        self.assertFalse(map_pins.eligible(
            title="EMSC: M5.4 earthquake Central Peru",
            place="9 km NNE of Carhuamayo, Peru",
            precision="point", tier="exact", lat=-10.9, lon=-76.0, cc="PE"))

    def test_city_demoted_to_named_state(self):
        title = "A cruise liner reports a gastrointestinal illness off the Florida coast"
        place = "Fort Lauderdale, Florida, United States"
        self.assertFalse(map_pins.city_named_in_headline(title, place))
        pin = map_pins.resolve_pin(title=title, place=place, precision="city",
                                   lat=26.12, lon=-80.14, cc="US")
        self.assertIsNotNone(pin)
        self.assertEqual(pin["precision"], "state")
        self.assertIn("Florida", pin["place"])
        self.assertNotIn("Fort Lauderdale", pin["place"])
        # State centroid, not the city (Florida label is around 28.16, -81.62).
        self.assertGreater(abs(pin["lat"] - 26.12), 0.5)

    def test_filter_demotes_heat_row_and_keeps_it_in_the_list(self):
        cols = ["id", "lat", "lon", "rank", "cat", "t", "title", "place", "prec", "tier", "how", "cc"]
        rows = [[
            "fl", 26.12, -80.14, 4, "health", "t",
            "A cruise liner reports a gastrointestinal illness off the Florida coast",
            "Fort Lauderdale, Florida, United States", "city", "exact", "geo", "US",
        ]]
        out, dropped = map_pins.filter_heat_rows(rows, cols)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][9], "exact")
        self.assertEqual(out[0][8], "state")
        self.assertIn("Florida", out[0][7])
        self.assertIsNotNone(out[0][1])

    def test_filter_points_demotes_and_drops(self):
        pts = [
            {"title": "A cruise liner reports a gastrointestinal illness off the Florida coast",
             "place": "Fort Lauderdale, Florida, United States",
             "precision": "city", "lat": 26.12, "lon": -80.14, "cc": "US"},
            {"title": "Iran says it will use 'all means' to fight US sanctions",
             "place": "Tehran, Tehran, Iran",
             "precision": "city", "lat": 35.69, "lon": 51.39, "cc": "IR"},
        ]
        kept, dropped = map_pins.filter_points(pts)
        self.assertEqual(dropped, 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["precision"], "state")
        self.assertIn("Florida", kept[0]["place"])

    def test_gaza_container_when_camp_unlisted(self):
        # City spelling that does not match, but Gaza is named → pin at Gaza Strip, not the camp.
        pin = map_pins.resolve_pin(
            title="An Israeli strike in northern Gaza wounded several people, witnesses said",
            place="Jabālyā, Gaza Strip, Palestinian Territory",
            precision="city", lat=31.53, lon=34.48, cc="PS")
        self.assertIsNotNone(pin)
        self.assertIn("Gaza", pin["place"])
        self.assertNotIn("Jab", pin["place"])
        self.assertEqual(pin["precision"], "state")


    def test_possessive_and_admin_short_names_are_kept(self):
        self.assertTrue(map_pins.eligible(
            title="UNRWA has warned that 85% of Gaza’s population faces repeated disruptions to safe water supplies",
            place="Gaza, Gaza Strip, Palestinian Territory",
            precision="city", lat=31.5, lon=34.47, cc="PS"))
        self.assertTrue(map_pins.eligible(
            title="UPDATE: Gas System Explosion at Basra's Hartha Power Plant Sparks Major Fire",
            place="Basrah, Basra, Iraq",
            precision="city", lat=30.5, lon=47.8, cc="IQ"))
        self.assertTrue(map_pins.eligible(
            title="Suspected Disease Outbreak Hits Bayelsa Community Without Functional Hospital",
            place="Bayelsa State, Nigeria",
            precision="state", lat=4.8, lon=6.2, cc="NG"))
        self.assertTrue(map_pins.eligible(
            title="Air Raid Warnings for Jazan City, Saudi Arabia",
            place="Jazan Region, Saudi Arabia",
            precision="state", lat=16.9, lon=42.6, cc="SA"))
        self.assertTrue(map_pins.eligible(
            title="Houthis Strike Saudi Arabia's Ash-Shaikh Power Station and Jizan Port",
            place="Jazan Region, Saudi Arabia",
            precision="state", lat=16.9, lon=42.6, cc="SA"))
        self.assertTrue(map_pins.eligible(
            title="Active Air Defense Operations in Bryansk Region",
            place="Bryansk Oblast, Russia",
            precision="state", lat=53.0, lon=33.4, cc="RU"))
        self.assertTrue(map_pins.eligible(
            title="Yemen Reports of 25 Saudi airstrikes targeting areas in Hodeidah, Al-Bayda and Saada governorates.",
            place="Şa‘dah, Yemen",
            precision="state", lat=16.94, lon=43.76, cc="YE"))
        self.assertTrue(map_pins.eligible(
            title="Russian ballistic missile strikes hit three major bridges across Kyiv’s Dnipro River",
            place="Kyiv, Kyiv City, Ukraine",
            precision="city", lat=50.45, lon=30.52, cc="UA"))

    def test_kordofan_demotes_to_named_state(self):
        pin = map_pins.resolve_pin(
            title="Sudanese army airstrike kills 15, including four children, in Kordofan",
            place="Abū Zabad, West Kordofan, Sudan",
            precision="city", lat=12.35, lon=29.25, cc="SD")
        self.assertIsNotNone(pin)
        self.assertIn("Kordofan", pin["place"])
        self.assertNotIn("Zabad", pin["place"])

    def test_contradicting_state_is_dropped(self):
        self.assertFalse(map_pins.eligible(
            title="Explosion in Ward, Ala.",
            place="Ward County, Texas, United States",
            precision="county", lat=33.6, lon=-95.3, cc="US"))

    def test_demoted_state_stays_eligible_via_postal(self):
        cols = ["id", "lat", "lon", "rank", "cat", "t", "title", "place", "prec", "tier", "how", "cc"]
        rows = [["t", 26.1, -80.2, 6, "weather", "t",
                 "Tornado Warning issued November 21 at 11:57AM EST until November 21 at 12:30PM EST by NWS Miami FL",
                 "Broward, FL; Miami-Dade, FL", "point", "exact", "geo", "US"]]
        out, dropped = map_pins.filter_heat_rows(rows, cols)
        self.assertEqual(dropped, 0)
        self.assertEqual(out[0][8], "state")
        self.assertTrue(map_pins.row_eligible(out[0], cols))



    def test_ill_in_illness_does_not_count_as_illinois(self):
        title = ("Almost 150 cruise passengers fall ill with unknown illness More than 140 "
                 "passengers and crew have reported a gastrointestinal illness aboard Princess "
                 "Cruises’ Caribbean Princess, which left Port Everglades in Fort Lauder")
        self.assertTrue(map_pins.eligible(
            title=title, place="Fort Lauderdale, Florida, United States",
            precision="city", lat=26.12, lon=-80.14, cc="US"))

    def test_kiev_hashtag_is_kept(self):
        self.assertTrue(map_pins.eligible(
            title="In #Kiev The Narcoführer perform’s a carefully staged display of collective grief",
            place="Kyiv, Kyiv City, Ukraine",
            precision="city", lat=50.45, lon=30.52, cc="UA"))

    def test_meteoalarm_wrong_country_is_dropped(self):
        self.assertFalse(map_pins.eligible(
            title="Croatia: Orange wind warning, 6 areas (Osječko-baranjska, Bjelovarsko-bilogorska, Vukovarsko-srijemska +3 more) - MeteoAlarm",
            place="Italy: Calabria, Abruzzo, Toscana +1 more",
            precision="point", lat=45.1, lon=15.6, cc="HR"))

    def test_generic_costa_does_not_demote_to_wrong_coast(self):
        self.assertFalse(map_pins.eligible(
            title="Spain: Orange coastalevent warning, 1 area (Costa - Litoral cántabro) - MeteoAlarm",
            place="Spain: Costa - Bizkaia litoral, Costa - Gipuzkoa litoral",
            precision="point", lat=40.2, lon=-3.6, cc="ES"))



if __name__ == "__main__":
    unittest.main()
