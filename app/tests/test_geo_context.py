"""Contextual geocoder rules (geo.py v9+v10, Nov 21 2026, Matt pt1682u + pt1686u: pins in the wrong place, "No location" when the story names one).
Every case is a real item from the live Wire, Nov 13-20 2026. Offline only (Nominatim budget 0).
Run: cd app && python3 -m unittest tests.test_geo_context -v"""
import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo

def run(title, location=None, lat=None, lon=None, sources=(), brief=None, category="natural disaster"):
    cl = {"cluster_id": "t", "title": title, "category": category, "location": location, "lat": lat, "lon": lon, "n_items": 1, "brief": brief}
    mem = [{"source": s, "source_url": "", "title": None, "lat": None, "lon": None, "location": None, "official": 0} for s in sources]
    return geo.geocode(cl, mem, geo.NomBudget(0))

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        geo.GDB = os.path.join(tempfile.mkdtemp(), "geo.db"); geo.gaz()

    # --- NWS zone lists -> the real counties (Matt's Flood Watch screenshot)
    def test_nws_melbourne_flood_watch(self):
        r = run("Flood Watch issued November 16 at 3:18PM EST until November 20 at 7:00PM EST by NWS Melbourne FL",
                "Inland Volusia; Orange; Seminole; Osceola; Okeechobee; Coastal Volusia; Coastal Indian River; Coastal St. Lucie; Coastal Martin; "
                "Inland Northern Brevard; Inland Indian River; Inland St. Lucie; Inland ", sources=["NWS (api.weather.gov)"])
        self.assertEqual(r["country"], "US"); self.assertEqual(r["admin1_code"], "US.FL"); self.assertEqual(r["precision"], "county")
        self.assertTrue(27.0 < r["lat"] < 29.5 and -81.6 < r["lon"] < -80.0, (r["lat"], r["lon"]))
        self.assertEqual(r["place"], "9 counties in East Central Florida")
        self.assertNotIn(";", r["place"])

    def test_nws_office_state_is_not_zone_state(self):
        # NWS Las Vegas NV issues for Inyo County, California: the zone's own state wins
        r = run("Winter Storm Watch issued November 11 at 12:15AM PST until November 14 at 4:00PM PST by NWS Las Vegas NV",
                "Eastern Sierra Slopes of Inyo County; Owens Valley; White Mountains of Inyo County")
        self.assertEqual(r["admin1_code"], "US.CA", r)

    def test_nws_county_based_warning(self):
        r = run("Flood Warning issued November 19 at 8:38AM EST by NWS Melbourne FL", "Lake, FL; Volusia, FL")
        self.assertEqual(r["admin1_code"], "US.FL"); self.assertEqual(r["precision"], "county")

    def test_nws_ugc_codes(self):
        r = run("Flood Watch by NWS Melbourne FL", "FLZ041; FLZ045")
        self.assertEqual(r["admin1_code"], "US.FL")

    def test_nws_marine_zone(self):
        r = run("Special Marine Warning issued November 20 at 7:31AM EST until November 20 at 8:15AM EST by NWS Melbourne FL",
                "Flagler Beach to Volusia-Brevard County Line 0-20 nm")
        self.assertEqual(r["country"], "US"); self.assertTrue(28.5 < r["lat"] < 29.6)

    def test_nws_area_label(self):
        res = geo.nws_resolve("Flood Watch by NWS Melbourne FL", "Inland Volusia; Orange; Seminole")
        self.assertEqual(geo.nws_area_label(res, "Florida"), "East Central Florida")

    # --- coordinates: the country label comes from the point, never from the word "of" (the Turkish town Of)
    def test_offshore_quake_not_turkey(self):
        r = run("GeoNet: M3.4 quake 30 km east of Tokomaru Bay (MMI 3)", "30 km east of Tokomaru Bay, New Zealand", -38.0213, 178.6554, ["GeoNet NZ"])
        self.assertEqual(r["country"], "NZ")
        for title, loc, la, lo, cc in [("M 5.8 - 40 km N of Ruteng, Indonesia", "54 km NNE of Ruteng, Indonesia", -8.2501, 120.5285, "ID"),
                                       ("M 4.7 - 94 km W of Illapel, Chile", "94 km W of Illapel, Chile", -31.7842, -72.1485, "CL"),
                                       ("GEOFON: M5.0 earthquake Andreanof Islands, Aleutian Islands", "65 km SSW of Atka, Alaska", 51.49, -174.6, "US"),
                                       ("M 4.7 - 130 km W of Tofino, Canada", "130 km W of Tofino, Canada", 49.0876, -127.6912, "CA")]:
            self.assertEqual(run(title, loc, la, lo)["country"], cc, title)

    def test_quake_offset_across_border_stays_exact(self):
        r = run("CSN: M4.0 earthquake 107 km al E de Ollagüe, Chile (depth 278 km)", "107 km al E de Ollagüe, Chile", -21.2, -67.2)
        self.assertNotEqual(r["confidence"], "low")

    def test_coordinates_contradict_story_country(self):
        # merged GDACS cluster: "in Australia" headline, point in Brazil -> v10: the headline's country wins (country-level pin in Australia)
        r = run("Forest fire in Australia (green alert)", "Brazil", -1.3848, -55.0092, sources=["GDACS"])
        self.assertEqual(r["country"], "AU"); self.assertEqual(r["precision"], "country")
        self.assertTrue(-45 < r["lat"] < -10 and 110 < r["lon"] < 155, (r["lat"], r["lon"]))

    def test_coordinates_next_to_named_country(self):
        # MeteoAlarm "Israel: ..." at a generic point just inside the West Bank: the named country, same point
        r = run("Israel: Orange fog warning, 1 area (Izrael Valley) - MeteoAlarm", "Israel: Izrael Valley", 31.4, 35.0, sources=["MeteoAlarm (EUMETNET)"])
        self.assertEqual(r["country"], "IL"); self.assertEqual(r["method"], "source_coords")

    def test_source_coordinates_kept_when_story_agrees(self):
        r = run("M 5.8 - 40 km N of Ruteng, Indonesia", "40 km N of Ruteng, Indonesia", -8.2501, 120.5285, sources=["USGS"])
        self.assertEqual(r["country"], "ID"); self.assertEqual(r["method"], "source_coords")

    # --- v10 (Matt pt1686u, Nov 21 2026): weak town names never beat the story's own context
    def test_lowercase_word_is_not_a_town(self):
        r = run("Iowa deputy witnesses house explosion, runs inside to help homeowner out", sources=["Google News: KETV", "Google News: WOWT"], category="explosion")
        self.assertEqual(r["country"], "US"); self.assertEqual(r["admin1_code"], "US.IA")

    def test_direction_word_is_not_a_town(self):
        r = run("Some Central Florida cities declare state of emergency due to severe rain", sources=["Google News: WKMG", "Google News: Spectrum News 13"])
        self.assertEqual(r["admin1_code"], "US.FL"); self.assertNotIn("Louisiana", r["place"])

    def test_weak_town_in_unnamed_country_dropped(self):
        r = run("Several Palestinians were injured in an Israeli attack near Abu Sharkh roundabout in the northern Gaza Strip.", sources=["Telegram @QudsNen"], category="military")
        self.assertEqual(r["country"], "PS")
        r = run("Iran has shot down 3 American drones today which tried to violate its airspace 1x MQ-1 'Grey Eagle' 1x MQ-9 'Reaper'", category="military")
        self.assertEqual(r["country"], "IR")

    def test_us_local_tv_prior(self):
        self.assertEqual(geo.source_cc([{"source": "Google News: WGME"}, {"source": "Bluesky @wmur9.bsky.social"}]), "US")
        self.assertIsNone(geo.source_cc([{"source": "Google News: WION"}]))
        r = run("One injured after home explosion in Town of Lyons", sources=["Google News: WGME", "Bluesky @wmur9.bsky.social"], category="explosion")
        self.assertNotEqual(r.get("country"), "FR")
        self.assertIn("Lyons", r.get("reason_unlocated") or "")      # asked of the online geocoder inside the US instead

    def test_big_city_kept_when_other_countries_named(self):
        r = run("BREAKING: Russian strikes on Kyiv have killed at least one person and damaged the embassies of Austria and the Netherlands", category="military")
        self.assertEqual(r["country"], "UA")
        r = run("Fresh Israeli attack on Gaza kills three", sources=["Middle East Eye", "The Independent world"], category="military")
        self.assertEqual(r["country"], "PS")

    def test_hyphen_half_is_not_a_place(self):
        r = run("Overnight storms cause extensive flooding in Broward, Miami-Dade; Hollywood declares state of emergency", sources=["Google News: WSVN"])
        self.assertNotEqual(r.get("country"), "CN")
        r = run("SEC Charges Indianapolis-Based Backward Hat Capital and Its Co-Founders", sources=["SEC press releases"], category="financial")
        self.assertEqual(r.get("city"), "Indianapolis")

    def test_county_name_not_its_city(self):
        r = run("Explosion injures 2 at Macon County manufacturing plant, officials say", sources=["Google News: WSMV"], category="explosion")
        self.assertNotEqual(r.get("city"), "Macon"); self.assertEqual(r["country"], "US")
        r = run("El Paso County health authority addresses rise in measles cases", category="disease")
        self.assertEqual(r["country"], "US")

    def test_headline_countries_bound_later_texts(self):
        r = run("Q: Pakistan was not attacked by Iran, yet other states in the Middle East were attacked",
                brief="WHAT: Q: Pakistan was not attacked by Iran. Does that show a need for no U.S. bases in the region? Qatar's PM: Oman was attacked, and they don't have U.S. military bases.",
                category="military")
        self.assertNotEqual(r.get("country"), "US")

    # --- people and organisations are not places
    def test_people_not_places(self):
        r = run("Republican Representative, Joe Wilson, says he supports the war with Iran", category="political")
        self.assertNotEqual(r.get("city"), "Wilson")
        r = run("***LIVESTREAM ALERT*** Danny Haiphong is LIVE today w/ Ben Norton", category="political")
        self.assertNotEqual(r.get("city"), "Norton")

    def test_university_is_not_a_town(self):
        r = run("Ohio University E. Coli Cases Nearly Triple to 11, Health Officials Brace for More", category="disease")
        self.assertNotIn("University, Florida", r.get("place") or "")

    def test_state_abbreviation_word(self):
        r = run("Paris Fortified Ahead Of Mass Protests Police Flood Streets, Metro Stations Shut", sources=["Google News: The Times of India"], category="political")
        self.assertEqual(r["country"], "FR")

    def test_new_colon_britain(self):
        r = run("NEW: Britain has sanctioned eight Israeli companies involved in expanding illegal settlements", category="political")
        self.assertNotEqual(r.get("city"), "New Britain")

    def test_el_salvador_is_a_country(self):
        r = run("Two Soldiers From El Salvador Die in Haiti Explosion While Working With Explosive Materials", category="war/conflict")
        self.assertNotEqual(r.get("country"), "BR")

    def test_gulf_is_not_papua(self):
        r = run("Russian missile ship damaged in suspected Ukrainian drone attack in Gulf of Finland", category="war/conflict")
        self.assertNotEqual(r.get("country"), "PG")
        r = run("Nelson Mandela privately revealed that General Constand Viljoen prevented a military coup", category="political")
        self.assertNotEqual(r.get("country"), "NZ")

    def test_crimea(self):
        r = run("— Footage shows Russian Iskander-M ballistic missile launches from the Belogorsk area of Crimea", category="war/conflict")
        self.assertFalse(r.get("country") == "RU" and r.get("confidence") != "low", r)

    def test_broad_region_location_field(self):
        r = run("Before the first case: WHO helps South Sudan prepare for Ebola Bundibugyo virus", "Africa", category="disease")
        self.assertNotEqual(r.get("country"), "TN")

    # --- US counties named in the text
    def test_us_county(self):
        r = run("Baltimore County fire crews respond to boat explosion in Dundalk", category="war/conflict")
        self.assertEqual(r["admin1_code"], "US.MD"); self.assertEqual(r["precision"], "county")
        r = run("Bernalillo County Shigellosis Outbreak Tops 102 Cases", category="disease")
        self.assertEqual(r["admin1_code"], "US.NM")
        r = run("Orange County deputies investigate", category="war/conflict")
        self.assertNotEqual(r.get("precision"), "county")    # Orange County is in several states and none is named

    # --- source country prior and country agreement
    def test_source_prior(self):
        self.assertEqual(geo.source_cc([{"source": "GeoNet NZ"}]), "NZ")
        self.assertEqual(geo.source_cc([{"source": "Google News: SMH.com.au"}]), "AU")
        self.assertIsNone(geo.source_cc([{"source": "Telegram @intelslava"}]))

    def test_multi_city_same_country_goes_to_shared_area(self):
        r = run("Russians attack Kryvyi Rih and Kharkiv overnight", category="war/conflict")
        self.assertIn(r["precision"], ("state", "country"))


    # --- v13 (Nov 27 2026): IATA airport codes in FAA ground-stop / delay items
    def test_faa_ground_stop_ord_is_ohare(self):
        r = run("FAA Ground stop: ORD (equipment outage)", "ORD, US", category="other")
        self.assertEqual(r["located"], 1, r)
        self.assertEqual(r["method"], "iata")
        self.assertEqual(r["country"], "US")
        self.assertEqual(r["admin1_code"], "US.IL")
        self.assertTrue(41.9 < r["lat"] < 42.05 and -88.0 < r["lon"] < -87.8, (r["lat"], r["lon"]))
        self.assertRegex(r["place"], r"O.?Hare")
        self.assertNotRegex(r["place"], r"Nebraska|Ord,")

    def test_faa_ground_stop_lex_is_lexington_ky(self):
        r = run("FAA Ground stop: LEX (disabled aircraft on the runway)", "LEX, US", category="other")
        self.assertEqual(r["located"], 1, r)
        self.assertEqual(r["method"], "iata")
        self.assertEqual(r["admin1_code"], "US.KY")
        self.assertTrue(37.9 < r["lat"] < 38.2 and -84.8 < r["lon"] < -84.4, (r["lat"], r["lon"]))
        self.assertNotRegex(r["place"], r"West Virginia|Lex,")

    def test_faa_ground_stop_other_codes(self):
        cases = [
            ("FAA Ground stop: JFK (weather)", "JFK, US", "US.NY", 40.5, 40.8, -73.9, -73.7),
            ("FAA Ground delay: LAX (volume)", "LAX, US", "US.CA", 33.8, 34.1, -118.5, -118.3),
            ("FAA Airport closure: MDW (airfield)", "MDW, US", "US.IL", 41.7, 41.9, -87.85, -87.65),
            ("FAA Ground stop: ATL (staffing)", "ATL, US", "US.GA", 33.5, 33.8, -84.6, -84.3),
        ]
        for title, loc, a1, la0, la1, lo0, lo1 in cases:
            r = run(title, loc, category="other")
            self.assertEqual(r.get("admin1_code"), a1, (title, r))
            self.assertTrue(la0 < r["lat"] < la1 and lo0 < r["lon"] < lo1, (title, r["lat"], r["lon"]))

    def test_ord_nebraska_town_is_unchanged_without_aviation_context(self):
        r = run("Ord, Nebraska evacuates after flash flooding", "Ord, Nebraska, United States")
        if r.get("located"):
            self.assertNotEqual(r.get("method"), "iata", r)
            # Must not jump to O'Hare
            self.assertFalse(41.9 < (r.get("lat") or 0) < 42.05 and -88.0 < (r.get("lon") or 0) < -87.8, r)

    def test_place_label_faa_ord_is_ohare(self):
        lab = geo.place_label("FAA Ground stop: ORD (equipment outage)", "ORD, US")
        self.assertRegex(lab, r"O.?Hare")
        self.assertNotRegex(lab, r"^ORD, US$|Nebraska")

    def test_place_label_faa_lex_is_lexington_ky(self):
        lab = geo.place_label("FAA Ground stop: LEX (disabled aircraft on the runway)", "LEX, US")
        self.assertRegex(lab, r"Blue Grass|Lexington")
        self.assertNotRegex(lab, r"^LEX, US$|West Virginia")

    def test_place_label_ord_nebraska_town_unchanged(self):
        lab = geo.place_label("Ord, Nebraska evacuates after flash flooding", "Ord, Nebraska, United States")
        self.assertIn("Ord", lab)
        self.assertNotRegex(lab, r"O.?Hare")


if __name__ == "__main__": unittest.main()

class StoryPage(unittest.TestCase):
    T = "Flood Watch issued November 16 at 3:18PM EST until November 20 at 7:00PM EST by NWS Melbourne FL"
    L = ("Inland Volusia; Orange; Seminole; Osceola; Okeechobee; Coastal Volusia; Coastal Indian River; Coastal St. Lucie; Coastal Martin; "
         "Inland Northern Brevard; Inland Indian River; Inland St. Lucie; Inland ")
    def test_bottom_line_is_a_sentence(self):
        import story_report as SR, re, html
        rows = [{"title": self.T, "source": "NWS (api.weather.gov)", "official": 1, "first_seen": "2026-11-16T20:41:00Z", "source_url": "https://api.weather.gov/x", "family": "NWS"}]
        r = {"category": "natural disaster", "location": self.L, "first_seen": "2026-11-16T20:41:00Z", "updated": "2026-11-20T12:56:00Z"}
        h, _ = SR.render("c6d89535b1f468bc", r, rows, 4, "", self.T, self.T, self.L, ["NWS (api.weather.gov)"], 1, ["NWS"])
        x = html.unescape(re.sub("<[^>]+>", " ", h))
        self.assertIn("Flood Watch for 9 East Central Florida counties from NWS Melbourne, through Nov 20 at 7 PM EST.", x)
        self.assertNotIn("Inland Volusia;", x)

    def test_page_header_and_jsonld_use_place_label(self):
        # the story page header line and JSON-LD contentLocation must not print the zone dump either (live check Nov 21)
        self.assertEqual(geo.place_label(self.T, self.L), "9 counties in East Central Florida")
        src = open(os.path.join(os.path.dirname(__file__), "..", "story.py")).read()
        self.assertIn("_geo.place_label(title", src)

    def test_file_photo_must_match_place(self):
        self.assertFalse(geo.photo_matches("Indianapolis", self.T, self.L))
        self.assertTrue(geo.photo_matches("Florida", self.T, self.L))
        self.assertTrue(geo.photo_matches("tropical cyclone", self.T, self.L))     # a topic, not a place
        self.assertFalse(geo.photo_matches("Indonesia", "M 5.2 - 86 km NW of Ryotsu-minato, Japan", "86 km NW of Ryotsu-minato, Japan"))
        self.assertTrue(geo.photo_matches("Japan", "M 5.2 - 86 km NW of Ryotsu-minato, Japan", "86 km NW of Ryotsu-minato, Japan"))
        import people as PP
        self.assertFalse(PP.place_photo_ok({"kind": "place", "alt": "File photo: Indianapolis", "caption": "File photo of Indianapolis (2016). Not taken at this event."}, self.T, self.L))

class PlaceLabel(unittest.TestCase):
    def test_headline_country_beats_location_field(self):
        self.assertEqual(geo.place_label("Forest fire in Australia (green alert)", "Brazil"), "Australia")
        self.assertEqual(geo.place_label("Forest fire in India (green alert)", "India"), "India")
        self.assertEqual(geo.place_label("Forest fire in Sudan (green alert)", "Sudan, South Sudan"), "Sudan, South Sudan")
        self.assertEqual(geo.place_label("M 4.7 - 24 km S of Yacuiba, Bolivia", "Argentina"), "Argentina")     # neighbours: the feed's own place stays

class HeatFallback(unittest.TestCase):
    """v10: the classic offline fallback on the map must agree with the story (heat_all._infer_agrees)."""
    def test_infer_must_match_sources_country(self):
        import json, heat_all
        it = {"id": "x", "title": "1 injured in vehicle explosion in Palo", "loc": "", "links": json.dumps([{"source": "Google News: KCRG", "url": ""}])}
        self.assertFalse(heat_all._infer_agrees(it, {"cc": "PH", "place": "Palo", "lat": 11.1, "lon": 124.9}))
        it = {"id": "y", "title": "Overnight storms cause extensive flooding in Broward, Miami-Dade; Hollywood declares state of emergency", "loc": "", "links": "[]"}
        self.assertFalse(heat_all._infer_agrees(it, {"cc": "CN", "place": "Dade", "lat": 30.0, "lon": 110.0}))
        it = {"id": "z", "title": "Tsunami threat ABOUT 94 MILES SOUTHWEST OF GUAM", "loc": "", "links": json.dumps([{"source": "NWS", "url": ""}])}
        self.assertTrue(heat_all._infer_agrees(it, {"cc": "GU", "place": "Guam", "lat": 13.4, "lon": 144.7}))


class WriteupPlace(unittest.TestCase):
    """v11 (Matt pt1718u): a place the published write-up names reaches the map, server-side; the v10 guards still hold."""
    BARR = ("In remarks prepared for the Association for Computing Machinery's conference on AI in finance in Milan on Monday, November 16, "
            "Federal Reserve Governor Michael S. Barr said AI agents acting for customers could move funds at high speed.")
    def _wu(self, cid, what, story=None):
        import geo_text
        orig = geo_text.note_for
        geo_text.note_for = lambda c: ({"what_happened": what, **({"story": story} if story else {})} if c == cid else {})
        self.addCleanup(setattr, geo_text, "note_for", orig)

    def test_barr_remarks_in_milan(self):
        import heat_all
        self._wu("barr", self.BARR)
        it = {"id": "barr", "title": "Fed\u2019s Barr flags bank run and debt risks from rapid AI adoption", "loc": None, "lat": None, "lon": None, "a": 0,
              "category": "financial", "brief": "WHAT: Fed\u2019s Barr flags bank run and debt risks from rapid AI adoption.", "links": "[]"}
        g = {"located": 0, "reason_code": "non_geo", "reason_unlocated": "Non-geographic topic (financial) and no place named"}
        p = heat_all.place(it, g)
        self.assertEqual(p["cc"], "IT"); self.assertIn("Milan", p["place"]); self.assertNotEqual(p["tier"], "global")

    def test_v3_sections_happened_and_template_ignored(self):
        import geo_text
        orig = geo_text.note_for; self.addCleanup(setattr, geo_text, "note_for", orig)
        geo_text.note_for = lambda c: {"story": {"sections": {"happened": self.BARR, "background": "In 2019 a run in Paris ..."}}}
        self.assertIn("Milan", geo_text.factual_text("x")[0]); self.assertEqual(geo_text.factual_text("x")[1], "")
        geo_text.note_for = lambda c: {"what_happened": "1 independent source is reporting this, none of them official yet. Times of Israel reported: x"}
        self.assertEqual(geo_text.factual_text("x")[0], "")

    def test_v11_unique_region_and_sentence_article(self):
        ch = lambda t: (geo.choose(geo.extract(t))[0] or {})
        self.assertEqual(ch("A Krasnoyarsk apartment was flooded with foam through the toilet").get("cc"), "RU")
        self.assertEqual(ch("Canary Islands state of emergency as 2,200 migrants arrive in 48 hours").get("a1"), "ES.53")
        self.assertNotEqual(ch("Coup de vent en Loire-Atlantique : y a-t-il un risque").get("cc"), "BJ")
        self.assertNotEqual(ch("The carrier group has left the Persian Gulf and is heading to Japan").get("cc"), "IR")

    def test_state_pin_yields_to_writeup_city(self):
        import heat_all
        self._wu("mj", "The Canadian Food Inspection Agency confirmed avian influenza linked to the Canadian National Poultry Show held Nov. 7 in Moose Jaw, Saskatchewan, CBC reports.")
        it = {"id": "mj", "title": "Breeders cull birds after avian flu outbreak at national poultry show in Sask.", "loc": None, "lat": None, "lon": None, "a": 0, "category": "disease", "links": "[]"}
        g = {"located": 1, "lat": 54.85, "lon": -97.38, "precision": "state", "country": "CA", "admin1_code": "CA.03", "place": "Manitoba, Canada", "method": "gazetteer", "confidence": "medium"}
        p = heat_all.place(it, g)
        self.assertIn("Moose Jaw", p["place"]); self.assertEqual(p["cc"], "CA")

    def test_milan_as_adjective(self):
        r = geo.locate_texts({"title": "Fed\u2019s Barr flags bank run"}, geo.lead_sentences("In remarks for a Milan conference on Nov. 16, Barr said AI agents could speed up runs."))
        self.assertEqual(r["country"], "IT"); self.assertEqual(r["city"], "Milan")

    def test_later_sentence_needs_a_cue_and_cyber_issuer_is_not_a_place(self):
        import heat_all
        self._wu("cve", "Oracle disclosed a critical Java flaw on Nov. 18. Canada's Centre for Cyber Security issued alert AL26-029 on the same flaw.")
        it = {"id": "cve", "title": "AL26-029 - Critical vulnerability impacting Oracle Java", "loc": None, "lat": None, "lon": None, "a": 0, "category": "cyber", "links": "[]"}
        self.assertNotEqual(heat_all.place(it, {"located": 0, "reason_code": "global"}).get("cc"), "CA")

    def test_refine_keeps_country_and_lede_only(self):
        import heat_all
        self._wu("gz", "Several Palestinians were hurt near Abu Sharkh roundabout in the northern Gaza Strip on Nov. 14. Two days earlier, a strike in Khan Younis killed six.")
        it = {"id": "gz", "title": "Several Palestinians were injured in an Israeli attack near Abu Sharkh roundabout in the northern Gaza Strip.", "loc": None,
              "lat": None, "lon": None, "a": 0, "category": "war/conflict", "links": "[]"}
        g = {"located": 1, "lat": 31.4, "lon": 34.35, "precision": "country", "country": "PS", "place": "Gaza Strip", "confidence": "medium"}
        p = heat_all.place(it, g)
        self.assertEqual(p["cc"], "PS"); self.assertNotIn("Khan", p["place"])

    def test_state_named_beats_same_name_town_elsewhere(self):
        r = geo.locate_texts({"title": "Florida dengue and snowbird insurance"}, ["Florida's health department reported 100 new dengue cases; Hillsborough has 468."], refine=True)
        self.assertTrue(r is None or r.get("admin1_code") in (None, "US.FL"))

    def test_small_town_from_headline_only_when_unplaced(self):
        import heat_all
        it = {"id": "rh", "title": "'Massive explosion' prevented after suspected tampering of propane tanks in Riverhead", "loc": None, "lat": None, "lon": None, "a": 0,
              "category": "terrorism", "links": json.dumps([{"source": "Newsday", "url": "https://www.newsday.com/long-island/x"}])}
        p = heat_all.place(it, {"located": 0, "reason_code": "not_found"})
        self.assertEqual(p["cc"], "US"); self.assertIn("Riverhead", p["place"])
        self.assertIsNone(geo.small_place("Congress", {"US"}))

    def test_state_of_emergency_subject(self):
        import heat_all
        it = {"id": "os", "title": "Ocean Shores declares a state of emergency", "loc": None, "lat": None, "lon": None, "a": 0, "category": "natural disaster",
              "links": json.dumps([{"source": "Google News: KIRO 7 News Seattle", "url": "https://news.google.com/rss/articles/x"}])}
        p = heat_all.place(it, {"located": 0, "reason_code": "not_found"})
        self.assertEqual(p["cc"], "US"); self.assertIn("Ocean Shores", p["place"])

    def test_oblast_is_not_its_capital(self):
        r = geo.locate_texts({"title": "drone strike in the city of Hlukhiv"}, ["A second drone strike hit the city of Hlukhiv in Sumy Oblast on Nov. 14."])
        self.assertIn("Hlukhiv", r["place"])

    def test_source_coordinates_untouched(self):
        import heat_all
        self._wu("eq", self.BARR)
        it = {"id": "eq", "title": "M 4.7 - 24 km S of Yacuiba, Bolivia", "loc": "Bolivia", "lat": -22.2, "lon": -63.6, "a": 0, "category": "natural disaster", "links": "[]"}
        self.assertEqual(heat_all.place(it, None)["how"], "source coordinates")

    def test_admin1_names(self):
        G = geo.gaz()
        self.assertEqual(G.admin1["FR.75"]["name"], "Paris"); self.assertEqual(G.admin1["VN.20"]["name"], "Ho Chi Minh City")

    # --- v11 (Matt pt1761u, Nov 23 2026): Edgewater flooding is Edgewater, FL, not Depew, NY
    def test_edgewater_is_florida_not_depew(self):
        brief = ("VOLUSIA COUNTY, Fla. – Edgewater mayor Diezel Depew called a special City Council meeting. "
                 "Depew said homes are taking on floodwaters. The city declared a local state of emergency.")
        r = run("Edgewater declares state of emergency amid flooding", brief=brief, category="political")
        self.assertEqual(r["country"], "US")
        self.assertEqual(r["admin1_code"], "US.FL")
        self.assertEqual(r["precision"], "city")
        self.assertIn("Edgewater", r["place"])
        self.assertIn("Florida", r["place"])
        self.assertNotIn("Depew", r["place"] or "")
        self.assertNotEqual(r.get("admin1_code"), "US.NY")

    def test_depew_location_field_yields_to_florida_headline(self):
        brief = "Volusia County, Fla. officials said flooding closed roads in Edgewater."
        r = run("Edgewater declares a state of emergency as flooding hits the city",
                location="Depew, New York, United States", brief=brief, category="political")
        self.assertIn("Edgewater", r["place"])
        self.assertEqual(r["admin1_code"], "US.FL")
        self.assertNotIn("Depew", r["place"] or "")

    def test_edgewater_without_a_state_is_unlocated(self):
        r = run("Edgewater declares state of emergency amid flooding",
                location="Depew, New York, United States", category="political")
        # Several Edgewaters exist; do not guess Illinois or keep the mayor's hometown.
        self.assertTrue(not r.get("located") or r.get("precision") in ("country", "global") or r.get("city") is None)
        self.assertNotIn("Depew", r.get("place") or "")
        self.assertNotEqual(r.get("admin1_code"), "US.NY")
        self.assertNotEqual(r.get("admin1_code"), "US.IL")

    def test_heat_all_overrides_stored_depew_pin(self):
        import heat_all
        it = {"id": "1c6c54ca300b4c17", "title": "Edgewater declares state of emergency amid flooding",
              "loc": "Depew, New York, United States", "lat": None, "lon": None, "a": 0,
              "category": "political", "brief": "VOLUSIA COUNTY, Fla. – flooding hit Edgewater.",
              "links": "[]"}
        g = {"located": 1, "lat": 42.904, "lon": -78.6923, "precision": "city", "country": "US",
             "admin1_code": "US.NY", "place": "Depew, New York, United States", "method": "location_field",
             "confidence": "high"}
        p = heat_all.place(it, g)
        self.assertIn("Edgewater", p["place"])
        self.assertEqual(p["cc"], "US")
        self.assertNotIn("Depew", p["place"])
        self.assertTrue(28.5 < p["lat"] < 29.5 and -81.5 < p["lon"] < -80.5, (p["lat"], p["lon"]))

    def test_sibling_county_disambiguates_edgewater(self):
        import heat_all
        a = {"id": "a", "title": "Edgewater declares a state of emergency as flooding hits the city",
             "loc": None, "lat": None, "lon": None, "a": 0, "category": "natural disaster",
             "brief": "", "links": "[]", "t": "", "rank": 7, "watchlist": 0, "n_families": 5, "eff_families": 5, "fs": ""}
        b = {"id": "b", "title": "Edgewater declares state of emergency amid flooding",
             "loc": "Depew, New York, United States", "lat": None, "lon": None, "a": 0, "category": "political",
             "brief": "", "links": "[]", "t": "", "rank": 7, "watchlist": 0, "n_families": 7, "eff_families": 7, "fs": ""}
        geo_rows = {
            "a": {"located": 1, "lat": 29.06, "lon": -81.191, "precision": "county", "country": "US",
                  "admin1_code": "US.FL", "place": "Volusia County, Florida", "method": "gazetteer", "confidence": "high"},
            "b": {"located": 1, "lat": 42.904, "lon": -78.6923, "precision": "city", "country": "US",
                  "admin1_code": "US.NY", "place": "Depew, New York, United States", "method": "location_field", "confidence": "high"},
        }
        rows, tiers, reasons = heat_all._rows([a, b], geo_rows)
        ix = {c: i for i, c in enumerate(heat_all.COLS)}
        by_id = {r[ix["id"]]: r for r in rows}
        for rid in ("a", "b"):
            r = by_id[rid]
            self.assertIn("Edgewater", r[ix["place"]], r)
            self.assertIn("Florida", r[ix["place"]], r)
            self.assertNotIn("Depew", r[ix["place"]])
            self.assertEqual(r[ix["cat"]], "natural disaster")
            self.assertEqual(r[ix["prec"]], "city")
            self.assertTrue(28.5 < r[ix["lat"]] < 29.5)
