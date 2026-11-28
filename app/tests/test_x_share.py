"""Share-to-X hashtag generator. Run: cd app && python3 -m unittest tests.test_x_share -v"""
import os, re, sys, unittest
os.environ.setdefault("BN_XTAGS", "0")
from urllib.parse import parse_qs, urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x_share as X

# Live /api/state snapshots from 2026-11-24 ~11:25 PM ET. Fields only; no secrets.
STORIES = {
    "ebola_drc": {
        "cluster_id": "5932fb61c94775cd",
        "rank": 8,
        "category": "disease",
        "location": "Kenya and Nigeria",
        "title": "Ebola disease caused by Bundibugyo virus- Democratic Republic of the Congo, Kenya and Nigeria",
        "brief": "WHAT: Ebola disease caused by Bundibugyo virus- Democratic Republic of the Congo, Kenya and Nigeria. WHERE: Kenya and Nigeria. WHEN: 2026-11-20 22:38 UTC / Nov 20 05:38 PM ET. CONFIDENCE: High — reported by 4 item(s) from 4 independent source families.",
        "hidden": False, "watchlist": 0,
    },
    "ebola_uganda": {
        "cluster_id": "d16f7f76c0b04a24",
        "rank": 7,
        "category": "disease",
        "location": None,
        "title": "Uganda, South Sudan intensify efforts to keep Ebola out amid burgeoning DR Congo outbreak",
        "brief": "WHAT: Uganda, South Sudan intensify efforts to keep Ebola out amid burgeoning DR Congo outbreak. WHERE: location not specified by source. WHEN: 2026-11-20 20:00 UTC / Nov 20 03:00 PM ET.",
        "hidden": False, "watchlist": 0,
    },
    "h5n1_us": {
        "cluster_id": "e39c1db7e8773749",
        "rank": 6,
        "category": "disease",
        "location": "United States of America",
        "title": "Influenza A(H5N1) - United States of America",
        "brief": "WHAT: Influenza A(H5N1) - United States of America. WHERE: United States of America. WHEN: 2026-11-24 10:52 UTC / Nov 24 05:52 AM ET.",
        "hidden": False, "watchlist": 0,
    },
    "ukraine_kryvyi": {
        "cluster_id": "5dc67348eab0b5f6",
        "rank": 5,
        "category": "war/conflict",
        "location": "Ukraine",
        "title": "Russian ballistic missile strike on Ukraine’s Kryvyi Rih injures 20, including three children",
        "brief": "",
        "hidden": False, "watchlist": 0,
    },
    "kyiv_bridges": {
        "cluster_id": "59ef9dbf16160f61",
        "rank": 6,
        "category": "war/conflict",
        "location": "Kyiv",
        "title": "Russian ballistic missile strikes hit three major bridges across Kyiv’s Dnipro River on Friday, killing three people and injuring 15, Mayor Vitali Klitschko said.",
        "brief": "",
        "hidden": False, "watchlist": 0,
    },
    "cyber_drupal": {
        "cluster_id": "993caf63ffc015aa",
        "rank": 3,
        "category": "cyber",
        "location": "Global (software)",
        "title": "CVE-2026-132165 added to CISA KEV: Drupal Core - Drupal Core Remote Code Execution Vulnerability",
        "brief": "",
        "hidden": False, "watchlist": 0,
    },
    "florida_rain": {
        "cluster_id": "4e4851abef3c18a8",
        "rank": 7,
        "category": "political",
        "location": "Florida",
        "title": "Some Central Florida cities declare state of emergency due to severe rain",
        "brief": "WHAT: Some Central Florida cities declare state of emergency due to severe rain. WHERE: Florida. WHEN: 2026-11-19 13:19 UTC / Nov 19 08:19 AM ET.",
        "hidden": False, "watchlist": 0,
    },
    "miami_flood": {
        "cluster_id": "8e048e2b8d685508",
        "rank": 7,
        "category": "natural disaster",
        "location": "Miami",
        "title": "Overnight storms cause extensive flooding in Broward, Miami-Dade; Hollywood declares state of emergency",
        "brief": "WHAT: Overnight storms cause extensive flooding in Broward, Miami-Dade; Hollywood declares state of emergency. WHERE: Miami. WHEN: 2026-11-18 11:34 UTC / Nov 18 06:34 AM ET.",
        "hidden": False, "watchlist": 0,
    },
    "fl_tornado_watch": {
        "cluster_id": "9c9baa02ac70a555",
        "rank": 5,
        "category": "natural disaster",
        "location": "Indian River, FL; Martin, FL; Okeechobee, FL; St. Lucie, FL",
        "title": "Tornado Watch issued November 21 at 6:23PM EST until November 21 at 10:00PM EST by NWS Melbourne FL",
        "brief": "WHAT: Tornado Watch issued November 21 at 6:23PM EST until November 21 at 10:00PM EST by NWS Melbourne FL [NWS severity: Extreme; urgency: Future; event type: Tornado Watch]. WHERE: Indian River, FL; Martin, FL; Okeechobee, FL; St. Lucie, FL (approx. 30.11, -81.88).",
        "hidden": False, "watchlist": 0,
    },
    "bessent_iran": {
        "cluster_id": "e2ca47e325c5b8e1",
        "rank": 2,
        "category": "politics",
        "location": "Iran; Strait of Hormuz; Tehran",
        "title": "Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz: Crud",
        "brief": "WHAT: Scott Bessent Unleashes Fresh Iran Sanctions as Tehran Warns Tankers Against Using Strait of Hormuz.",
        "hidden": False, "watchlist": 0,
    },
    "riyadh_tower": {
        "cluster_id": "6b27e568eb9f503f",
        "rank": 2,
        "category": "war/conflict",
        "location": "Riyadh",
        "title": "Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days",
        "brief": "",
        "hidden": False, "watchlist": 0,
    },
    "burnham_veterans": {
        "cluster_id": "dec0cddbd508e929",
        "rank": 6,
        "category": "conflict",
        "location": "",
        "title": "Burnham launches inquiry into nuclear bomb test veterans' records",
        "brief": "UK sets up independent panel on health effects of 1950s-60s nuclear tests on veterans and families. On Nov. 24, UK Prime Minister Andy Burnham announced a non-statutory Independent Panel into the potential health impact of British nuclear weapons testing on veterans and their families, according to the UK government.",
        "hidden": False, "watchlist": 0,
    },
    "hegseth_arms": {
        "cluster_id": "9f5bc9d66d783d25",
        "rank": 6,
        "category": "conflict",
        "location": "",
        "title": "— Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine…",
        "brief": "Zelensky says US Secretary of War Pete Hegseth has not yet approved a new arms package for Ukraine, including 48 anti-ballistic missiles. Ukraine also expects missiles for F-16s and NASAMS systems.",
        "hidden": False, "watchlist": 0,
    },
}


def tweet_len(item):
    url = X.story_url(item)
    return X.weighted_len(X.share_text(item), url)




class Tags(unittest.TestCase):
    def test_every_story_has_3_to_5_tags(self):
        for key, it in STORIES.items():
            tags = X.hashtags(it)
            self.assertGreaterEqual(len(tags), 3, f"{key}: {tags}")
            self.assertLessEqual(len(tags), 5, f"{key}: {tags}")

    def test_ebola_drc_prefers_headline_primary(self):
        it = STORIES["ebola_drc"]
        tags = X.hashtags(it)
        self.assertIn("#DRC", tags)
        self.assertIn("#Ebola", tags)
        self.assertNotIn("#Kenya", tags)
        self.assertNotIn("#Nigeria", tags)
        desk = "Congo's Ebola outbreak reached 11,821 confirmed cases and 5,810 deaths as fighting traps responders in Ituri."
        dtags = X.hashtags(it, headline=desk)
        self.assertIn("#DRC", dtags)
        self.assertIn("#Ebola", dtags)
        self.assertNotIn("#Kenya", dtags)
        self.assertTrue("#Ituri" in dtags or len(dtags) >= 3)

    def test_ebola_uganda_rank7_locations_from_title(self):
        it = STORIES["ebola_uganda"]
        tags = X.hashtags(it)
        self.assertIn("#DRC", tags)
        self.assertTrue("#Uganda" in tags or "#SouthSudan" in tags)
        self.assertIn("#Ebola", tags)
        self.assertIn("#Outbreak", tags)
        self.assertLessEqual(len(tags), 5)
        self.assertGreaterEqual(len(tags), 3)

    def test_h5n1_us_rank6_has_topic_and_category(self):
        it = STORIES["h5n1_us"]
        tags = X.hashtags(it)
        self.assertIn("#US", tags)
        self.assertIn("#H5N1", tags)
        self.assertNotIn("#BirdFlu", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_ukraine_strike_rank5_has_war_tags(self):
        it = STORIES["ukraine_kryvyi"]
        tags = X.hashtags(it)
        self.assertIn("#Ukraine", tags)
        self.assertIn("#War", tags)
        self.assertTrue({"#KryvyiRih", "#Missile", "#MissileStrike"} & set(tags), tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)

    def test_kyiv_bridges_rank6_has_war_tags(self):
        it = STORIES["kyiv_bridges"]
        tags = X.hashtags(it)
        self.assertIn("#Ukraine", tags)
        self.assertIn("#Kyiv", tags)
        self.assertIn("#War", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_cyber_global_rank3_reaches_three(self):
        it = STORIES["cyber_drupal"]
        tags = X.hashtags(it)
        self.assertGreaterEqual(len(tags), 3)
        self.assertTrue("#CVE" in tags or "#Cybersecurity" in tags)
        self.assertTrue({"#Cyberattack", "#Cybersecurity", "#CVE"} & set(tags), tags)

    def test_florida_rain_rank7(self):
        it = STORIES["florida_rain"]
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertTrue({"#Storm", "#Rain", "#Flood", "#Weather"} & set(tags), tags)
        self.assertNotIn("#Hurricane", tags)
        self.assertNotIn("#Tampa", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_miami_flood_rank7(self):
        it = STORIES["miami_flood"]
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertIn("#Miami", tags)
        self.assertIn("#Flood", tags)
        self.assertNotIn("#Hollywood", tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)

    def test_tornado_watch_rank5_florida_weather(self):
        it = STORIES["fl_tornado_watch"]
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertIn("#Tornado", tags)
        self.assertNotIn("#Melbourne", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_held_and_false_positive_location_plus_generic(self):
        it = dict(STORIES["ebola_drc"], hidden=True)
        tags = X.hashtags(it)
        self.assertIn("#DRC", tags)
        self.assertNotIn("#Ebola", tags)
        self.assertNotIn("#Outbreak", tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertFalse({t.lower() for t in tags} & {"#news", "#worldnews", "#breaking", "#blackoutnetwork", "#alerts"}, tags)
        wl = dict(STORIES["kyiv_bridges"], rank=7, watchlist=1)
        tags = X.hashtags(wl)
        self.assertIn("#Ukraine", tags)
        self.assertNotIn("#War", tags)  # watchlist/held: places only, no conflict topic
        self.assertGreaterEqual(len(tags), 3)

    def test_max_five_min_three_and_280(self):
        banned = ".,;:'\"/"
        for key, it in STORIES.items():
            tags = X.hashtags(it)
            self.assertGreaterEqual(len(tags), 3, key)
            self.assertLessEqual(len(tags), 5, key)
            text = X.share_text(it)
            self.assertLessEqual(tweet_len(it), 280, f"{key}: {text!r}")
            in_text = [tg for tg in tags if tg in text]
            self.assertGreaterEqual(len(in_text), 3, f"{key}: {text!r}")
            for tg in tags:
                self.assertTrue(tg.startswith("#") and " " not in tg)
                self.assertTrue(not any(c in tg for c in banned), tg)


    def test_global_no_location_still_reaches_three(self):
        it = {"title": "Federal Reserve announces College Fed Challenge winners",
              "location": "", "category": "markets", "rank": 1, "cluster_id": "deadbeefdeadbeef"}
        tags = X.hashtags(it)
        self.assertGreaterEqual(len(tags), 3, tags)
        self.assertLessEqual(len(tags), 5, tags)

    def test_czechia_snow_ice_gets_location_and_weather(self):
        it = {"title": "Czechia: Orange snow-ice warning, 3 areas (Kraj Vysocina)",
              "location": "Czechia: Kraj Vysocina", "category": "weather", "rank": 4,
              "cluster_id": "c0ffeedc0ffeed00"}
        tags = X.hashtags(it)
        self.assertIn("#Czechia", tags)
        self.assertTrue("#Weather" in tags or "#Storm" in tags or "#Snow" in tags, tags)
        self.assertGreaterEqual(len(tags), 3, tags)
        self.assertNotIn("#Kenya", tags)

    def test_held_without_location_still_reaches_three(self):
        it = {"title": "Satellites Have a Ground-Level Cybersecurity Problem",
              "location": "", "category": "cyber", "rank": 3, "watchlist": 1,
              "cluster_id": "f011daf83275a6ef"}
        tags = X.hashtags(it)
        self.assertGreaterEqual(len(tags), 3, tags)
        self.assertNotIn("#Cyberattack", tags)

    def test_hurricane_record_comparison_is_not_hurricane_tag(self):
        it = {"title": "Days of rain flood Central and South Florida, and the St. Johns River is forecast to pass its Hurricane Ian record",
              "location": "Florida", "category": "natural disaster", "rank": 7,
              "cluster_id": "4e4851abef3c18a8"}
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertIn("#Flood", tags)
        self.assertNotIn("#Hurricane", tags)  # "Hurricane Ian record" is a comparison, not a current hurricane
        self.assertGreaterEqual(len(tags), 3)

    def test_intent_url_and_button_hides_tags_from_label(self):
        it = STORIES["ebola_drc"]
        href = X.intent_url(it)
        self.assertTrue(href.startswith("https://x.com/intent/post?"))
        q = parse_qs(urlparse(href).query)
        text = q["text"][0]
        url = q["url"][0]
        hs = [t for t in (q.get("hashtags") or [""])[0].split(",") if t]
        self.assertTrue(url.endswith("/wire/5932fb61c94775cd?s=x"))
        self.assertIn("text", q)
        self.assertIn("url", q)
        self.assertIn("hashtags", q)
        self.assertIn("Ebola", hs)
        self.assertIn("DRC", hs)
        self.assertNotIn("Kenya", hs)
        self.assertNotIn("#Ebola", text)  # tags live in the hashtags param, not in text
        self.assertNotIn("#DRC", text)
        html = X.button_html(it)
        self.assertIn("Post on X", html)
        self.assertIn('target="_blank"', html)
        self.assertNotIn("#Ebola", html)
        self.assertNotIn("#DRC", html)
        self.assertIn("hashtags=", html)
        self.assertIn("Ebola", html)
        self.assertLessEqual(X.weighted_len(X._join(text, ["#" + t for t in hs]), url), 280)

    def test_intent_uses_baked_in_tags_and_drops_banned(self):
        """Story pages pass ready.tags; banned fluff is dropped; 3-5 remain in the hashtags param."""
        it = _mk("Hackers breach FinCEN, prompting systems shutdown",
                 location="Washington", category="cyber", rank=5, brief="FinCEN systems were taken offline after a breach.")
        href = X.intent_url(it, tags=["#FinCEN", "#Cybersecurity", "#Breach", "#News", "#BlackoutNetwork", "#Breaking"])
        q = parse_qs(urlparse(href).query)
        self.assertIn("text", q)
        self.assertIn("url", q)
        hs = [t for t in q["hashtags"][0].split(",") if t]
        self.assertTrue(3 <= len(hs) <= 5, hs)
        self.assertIn("FinCEN", hs)
        self.assertIn("Cybersecurity", hs)
        self.assertIn("Breach", hs)
        for banned in ("News", "WorldNews", "Breaking", "BlackoutNetwork"):
            self.assertNotIn(banned, hs)
            self.assertNotIn("#" + banned, q["text"][0])
        # one-tap button: complete href, no follow-up fetch
        html = X.button_html(it, tags=["#FinCEN", "#Cybersecurity", "#Breach"])
        self.assertIn('href="https://x.com/intent/post?', html)
        self.assertIn("hashtags=FinCEN,Cybersecurity,Breach", html)
        self.assertIn('target="_blank"', html)


class ShareTextReport(unittest.TestCase):
    """Prints the composed share text for the live stories (assertion keeps them in the log)."""
    def test_report_share_texts(self):
        lines = []
        for key, it in STORIES.items():
            text = X.share_text(it)
            url = X.story_url(it)
            lines.append(f"{key} r={it['rank']} tags={X.hashtags(it)}\n  {text} {url}\n  weighted={X.weighted_len(text, url)}")
        desk = "Congo's Ebola outbreak reached 11,821 confirmed cases and 5,810 deaths as fighting traps responders in Ituri."
        lines.append(
            "ebola_drc_desk r=8 tags=%s\n  %s\n  weighted=%s" % (
                X.hashtags(STORIES["ebola_drc"], headline=desk),
                X.share_text(STORIES["ebola_drc"], headline=desk),
                X.weighted_len(X.share_text(STORIES["ebola_drc"], headline=desk), X.story_url(STORIES["ebola_drc"])),
            )
        )
        report = "\n".join(lines)
        self.assertTrue(report)
        print("\n----- Share texts -----\n" + report + "\n-----------------------")



def _mk(title, **kw):
    d = dict(title=title, location="", category="", rank=5, cluster_id="0123456789abcdef", brief="")
    d.update(kw)
    return d


GENERICS = {"#News", "#WorldNews", "#Breaking", "#BreakingNews"}


class EntityFirst(unittest.TestCase):
    """Matt pt1873u: Theriva Biologics shared as '#News #WorldNews #Breaking'. Tags must name what the story names."""
    def test_theriva_nyse_american(self):
        for title in ("NYSE American halts trading in small biotech Theriva Biologics after its shares fell below 10 cents",
                      "Theriva Biologics trading halted on NYSE American By Investing.com"):
            tags = X.hashtags(_mk(title, category="markets", rank=7))
            self.assertIn("#TherivaBiologics", tags)
            self.assertIn("#NYSEAmerican", tags)
            self.assertIn("#TOVX", tags)
            self.assertTrue(set(tags) & {"#Stocks", "#Biotech", "#Markets", "#TherivaBiologics"}, tags)
            self.assertFalse(set(tags) & GENERICS, tags)

    def test_ukraine_strike(self):
        tags = X.hashtags(_mk("Russian ballistic missile strike on Ukraine’s Kryvyi Rih injures 20, including three children",
                              location="Kryvyi Rih, Ukraine", category="war/conflict"))
        self.assertIn("#Ukraine", tags)
        self.assertIn("#War", tags)

    def test_ebola_drc_not_kenya(self):
        tags = X.hashtags(_mk("Congo's Ebola outbreak reached 11,821 confirmed cases and 5,810 deaths as fighting traps responders in Ituri.",
                              location="Kenya and Nigeria", category="disease", rank=8))
        for t in ("#DRC", "#Ebola"):
            self.assertIn(t, tags)
        self.assertNotIn("#Kenya", tags)

    def test_cisa_kev(self):
        tags = X.hashtags(_mk("CISA Adds Three Known Exploited Vulnerabilities to Catalog", category="cyber", rank=3))
        self.assertIn("#CISA", tags)
        self.assertTrue(set(tags) & {"#Cybersecurity", "#Cyberattack"})

    def test_florida_flood(self):
        tags = X.hashtags(_mk("Flood Watch issued November 23 at 3:58PM EST until November 26 at 1:00AM EST by NWS Miami FL",
                              location="Metro Broward County; Metropolitan Miami Dade", category="natural disaster", rank=4))
        for t in ("#Florida", "#Flood", "#Miami"):
            self.assertIn(t, tags)

    def test_libya_drone_vs_russian_vessel_is_not_ukraine_war(self):
        tags = X.hashtags(_mk("Libya's eastern government suspects a drone attack caused an explosion aboard a Russian vessel",
                              brief="Officials stressed Libya is not party to the Russian invasion of Ukraine", category="war/conflict", rank=7))
        self.assertIn("#Libya", tags)
        self.assertTrue("#Drone" in tags or "#DroneStrike" in tags, tags)
        self.assertNotIn("#UkraineWar", tags)
        self.assertNotIn("#Ukraine", tags)

    def test_earthquake_is_not_weather(self):
        tags = X.hashtags(_mk("M 4.6 - 158 km SE of Severo-Kuril’sk, Russia", location="158 km SE of Severo-Kuril’sk, Russia", category="natural disaster", rank=2))
        self.assertIn("#Earthquake", tags)
        self.assertIn("#Russia", tags)
        self.assertNotIn("#Weather", tags)

    def test_company_name_yields_a_tag(self):
        for title, tag in (("Data on clients’ assets also leaked in recent Rakuten Securities breach", "#RakutenSecurities"),
                           ("Boeing Co. grounds 737 fleet after FAA order", "#FAA"),
                           ("Pfizer Inc. recalls batch after FDA warning", "#Pfizer")):
            got = X.hashtags(_mk(title, category="cyber" if "Rakuten" in title else "business", rank=5))
            self.assertTrue(tag in got or tag.replace("Securities","") in got or any(tag.lstrip("#")[:7].lower() in x.lower() for x in got), (title, tag, got))

    def test_never_more_than_one_generic_and_3_to_5(self):
        titles = ["Iceberg D33B", "Campton declares state of emergency amid lake water concerns", "Satellites Have a Ground-Level Cybersecurity Problem",
                  "Federal Reserve announces College Fed Challenge winners", "Aliens Are Preparing to Colonize Earth, UFO researcher claims", "Minutes of the Board's discount rate meetings"]
        for ti in titles:
            for kw in ({}, {"watchlist": 1}, {"hidden": True}):
                tags = X.hashtags(_mk(ti, **kw))
                self.assertGreaterEqual(len(tags), 3, (ti, tags))
                self.assertLessEqual(len(tags), 5, (ti, tags))
                self.assertLessEqual(len(set(tags) & GENERICS), 1, (ti, tags))
        for key, it in STORIES.items():
            tags = X.hashtags(it)
            self.assertLessEqual(len(set(tags) & GENERICS), 1, (key, tags))
            self.assertLessEqual(len(set(tags) & X.SECTORS), 1, (key, tags))

    def test_headline_hashtags_stripped_and_agency_from_title_only(self):
        it = _mk("#Iran #Lebanon Iran's Islamic Revolutionary Guard Corps has evacuated its command", location="Lebanon", category="war/conflict", rank=2)
        txt = X.share_text(it)
        self.assertNotIn("#Iran #Lebanon Iran", txt)
        self.assertLessEqual(len(set(re.findall(r"#\w+", txt))), 5)
        g = _mk("GEOFON: M5.4 earthquake Near Coast of Chiapas, Mexico", brief="USGS lists a similar event", category="natural disaster", rank=3)
        self.assertNotIn("#USGS", X.hashtags(g))

    def test_llm_validation_rejects_invented_names(self):
        import x_tags_llm as L
        title = "NYSE American halts trading in small biotech Theriva Biologics after its shares fell below 10 cents"
        got = L.validate(["#TherivaBiologics", "#NYSEAmerican", "#TOVX", "#Moderna", "#News", "#WorldNews"], title, "", "", rule=["#TOVX"])
        self.assertIn("#TherivaBiologics", got)
        self.assertNotIn("#Moderna", got)
        self.assertLessEqual(len([t for t in got if t in GENERICS]), 1)
        self.assertIsNone(L.validate(["#Moderna", "#Pfizer", "#Tesla"], title, "", ""))


    def test_bessent_names_the_person_agency_topic_and_keeps_location(self):
        it = STORIES["bessent_iran"]
        tags = X.hashtags(it)
        self.assertIn("#ScottBessent", tags)
        self.assertIn("#Treasury", tags)
        self.assertIn("#Sanctions", tags)
        self.assertTrue(any(t in tags for t in ("#Iran", "#Tehran", "#Hormuz")), tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)
        text = X.share_text(it)
        self.assertIn("#ScottBessent", text)
        self.assertLessEqual(X.weighted_len(text, X.story_url(it)), 280)

    def test_named_person_at_start_of_title_is_tagged(self):
        it = {"cluster_id": "a"*16, "rank": 5, "category": "politics", "location": "Washington",
              "title": "Jane Doe Imposes new export controls in Washington", "brief": "", "hidden": False, "watchlist": 0}
        tags = X.hashtags(it)
        self.assertIn("#JaneDoe", tags)


    def test_burnham_nuclear_test_veterans(self):
        it = STORIES["burnham_veterans"]
        tags = X.hashtags(it)
        self.assertIn("#AndyBurnham", tags, tags)
        self.assertIn("#Nuclear", tags)
        self.assertTrue(any(t in tags for t in ("#UK", "#Manchester")), tags)
        self.assertNotIn("#War", tags)
        self.assertNotIn("#Conflict", tags)
        self.assertFalse(any("PrimeMinister" in t or t == "#News" for t in tags if t in tags and "Burnham" in t), tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)

    def test_hegseth_arms_package_is_not_a_strike(self):
        it = STORIES["hegseth_arms"]
        tags = X.hashtags(it)
        self.assertIn("#PeteHegseth", tags, tags)
        self.assertIn("#Zelensky", tags, tags)
        self.assertIn("#Ukraine", tags, tags)
        self.assertTrue(any(t in tags for t in ("#NASAMS", "#F16")), tags)
        self.assertNotIn("#WarPeteHegseth", tags)
        self.assertNotIn("#SecretaryPeteHegseth", tags)
        self.assertNotIn("#MissileStrike", tags)
        self.assertNotIn("#War", tags)
        self.assertNotIn("#UkraineWar", tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)

    def test_role_prefix_stripped_from_person_tag(self):
        tags = X.hashtags(_mk("Secretary of War Pete Hegseth visits Kyiv", location="Kyiv", category="politics", rank=5,
                              brief="US Secretary of War Pete Hegseth arrived in Kyiv."))
        self.assertIn("#PeteHegseth", tags, tags)
        self.assertNotIn("#WarPeteHegseth", tags)

    def test_llm_rejects_generic_war_conflict_for_non_armed_story(self):
        import x_tags_llm as L
        title = "Burnham launches inquiry into nuclear bomb test veterans' records"
        brief = "UK Prime Minister Andy Burnham announced a panel on nuclear tests on veterans."
        self.assertIsNone(L.validate(["#War", "#News", "#Conflict"], title, brief, "United Kingdom"))
        got = L.validate(["#AndyBurnham", "#NuclearTestVeterans", "#UK"], title, brief, "United Kingdom")
        self.assertEqual(got, ["#AndyBurnham", "#NuclearTestVeterans", "#UK"])

    def test_xtags_only_for_rank_5_plus_and_one_call_per_story(self):
        import tempfile, os, json
        import x_tags_llm as L
        tmp = tempfile.mkdtemp()
        os.environ["BN_XTAGS_DB"] = os.path.join(tmp, "xtags.db")
        os.environ["BN_XTAGS"] = "1"
        os.environ["XAI_API_KEY"] = "test-key-not-used"
        L._CACHE.clear(); L._PENDING.clear(); L._STARTED = False
        # rank 4 must not queue
        self.assertIsNone(L.lookup("aaaaaaaaaaaaaaaa", "Hello", "", "UK", rank=4))
        self.assertEqual(L._Q.qsize(), 0)
        # one call recorded => never queued again even at rank 6
        L._store("bbbbbbbbbbbbbbbb", "ok", ["#AndyBurnham", "#UK", "#NuclearTests"], 10, 5, 0.0001, 6)
        L._CACHE["bbbbbbbbbbbbbbbb"] = ("ok", ["#AndyBurnham", "#UK", "#NuclearTests"])
        got = L.lookup("bbbbbbbbbbbbbbbb", "Burnham launches inquiry into nuclear tests",
                       "Andy Burnham in the UK", "United Kingdom", rank=6)
        self.assertEqual(got, ["#AndyBurnham", "#UK", "#NuclearTests"])
        self.assertTrue(L.already_called("bbbbbbbbbbbbbbbb"))
        os.environ["BN_XTAGS"] = "0"




    def test_burnham_surname_and_uk_from_body_when_brief_and_location_empty(self):
        """Live share used the scanner title with an empty location and a thin brief; Andy and UK live in the write-up."""
        it = dict(STORIES["burnham_veterans"])
        it["brief"] = ""
        it["location"] = ""
        it["body"] = ("UK sets up independent panel on health effects of 1950s-60s nuclear tests on veterans and families. "
                      "On Nov. 24, UK Prime Minister Andy Burnham announced a non-statutory Independent Panel.")
        tags = X.hashtags(it)
        self.assertIn("#AndyBurnham", tags, tags)
        self.assertIn("#UK", tags, tags)

    def test_person_and_place_kept_when_xai_omits_them(self):
        """xAI is primary but must not drop people or places the full extractor found (live Hegseth missed #Zelensky)."""
        it = dict(STORIES["hegseth_arms"])
        fake = ["#PeteHegseth", "#NASAMS", "#F16", "#Ukraine", "#AntiBallisticMissiles"]
        class _Fake:
            def lookup(self, *a, **k):
                return list(fake)
        import sys
        sys.modules["x_tags_llm"] = _Fake()
        try:
            tags = X.hashtags(it)
        finally:
            sys.modules.pop("x_tags_llm", None)
        self.assertIn("#Zelensky", tags, tags)
        self.assertIn("#PeteHegseth", tags, tags)
        self.assertIn("#Ukraine", tags, tags)
        self.assertNotIn("#WarPeteHegseth", tags)
        self.assertNotIn("#MissileStrike", tags)
        self.assertNotIn("#War", tags)

    def test_location_from_body_even_when_brief_has_no_place(self):
        it = _mk("Burnham launches inquiry into nuclear bomb test veterans' records",
                 location="", category="conflict", rank=6,
                 brief="An inquiry into nuclear bomb test veterans' records has been announced.")
        it["body"] = "UK Prime Minister Andy Burnham announced the panel in Manchester."
        tags = X.hashtags(it)
        self.assertIn("#AndyBurnham", tags, tags)
        self.assertTrue("#UK" in tags or "#Manchester" in tags, tags)

    def test_related_story_titles_in_writeup_do_not_leak_topic_tags(self):
        """Template write-ups append 'Related stories we are also tracking: …' with other
        headlines. Those titles must not become this story's topic tags (live Riyadh
        picked up #NuclearTestVeterans from the Burnham headline)."""
        riyadh = _mk("Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days",
                     location="Riyadh, Saudi Arabia", category="war/conflict", rank=2, brief="")
        riyadh["body"] = (
            "The PIF Tower in Riyadh was struck in an aerial attack for the second time in five days. "
            "Related stories we are also tracking: Burnham launches inquiry into nuclear bomb test "
            "veterans' records (UK); UK Prime Minister Andy Burnham announced the panel."
        )
        tags = X.hashtags(riyadh)
        self.assertNotIn("#NuclearTestVeterans", tags, tags)
        self.assertNotIn("#NuclearTests", tags, tags)
        self.assertNotIn("#AndyBurnham", tags, tags)
        self.assertTrue("#Riyadh" in tags or "#SaudiArabia" in tags or "#PIFTower" in tags, tags)
        # The Burnham story itself still gets the veteran / person tags from its own text.
        burnham = _mk("Burnham launches inquiry into nuclear bomb test veterans' records",
                      location="", category="politics", rank=6, brief="")
        burnham["body"] = "UK Prime Minister Andy Burnham opened an inquiry into nuclear bomb test veterans' records."
        bt = X.hashtags(burnham)
        self.assertIn("#AndyBurnham", bt, bt)
        self.assertIn("#UK", bt, bt)
        self.assertIn("#Nuclear", bt)

    def test_intent_url_when_d_is_the_item_dict(self):
        """The timeline once passed the item dict as `d` after reusing that name; hashtags
        then crashed and left xu empty. String fields only; the share button still builds."""
        it = _mk("Riyadh's landmark 'PIF Tower' struck in aerial attack for second time in five days",
                 location="", category="war/conflict", rank=2, brief="")
        it["d"] = it  # circular: the old timeline payload
        url = X.intent_url(X.with_body(it))
        self.assertTrue(url.startswith("https://x.com/intent/post?"), url)
        self.assertIn("PIF", url)
        self.assertNotIn("NuclearTestVeterans", url)



class FinalTagRule(unittest.TestCase):
    """Matt, Nov 25 1:03 PM ET: 3-5 short popular tags for engagement. Topic words like #War are good. Never #News/#Alerts/#Update or long run-togethers."""
    BANNED = {"#news", "#worldnews", "#breaking", "#breakingnews", "#blackoutnetwork", "#alerts", "#alert", "#wire", "#live", "#update", "#updates"}
    LOW = [
        ("Synology security advisory (AV26-1193)", "", "cyber", 3),
        ("Forest fire in Australia (green alert)", "Australia", "natural disaster", 1),
        ("M 4.7 - 18 km ESE of Güvercinlik, Turkey", "Turkey", "natural disaster", 2),
        ("Space weather: WATCH: Geomagnetic Storm Category G1 Predicted", "Global (Earth)", "space", 2),
        ("Minutes of the Board's discount rate meetings on October 19", "", "markets", 1),
        ("WHO: urgent action needed to safeguard the effectiveness of antibiotics", "", "disease", 1),
        ("Director Liability Italy: Bank Failure Guide 2026", "", "financial", 4),
        ("Flood Watch issued November 25 at 1:47AM EST until November 26", "North Carolina", "natural disaster", 4),
        ("Level 2 - Malaria in Panama", "Panama", "disease", 1),
        ("Society for UAP Studies Opens Registration for One of the Finest Courses", "", "uap", 2),
    ]

    def _ok(self, tags, label):
        self.assertTrue(3 <= len(tags) <= 5, (label, tags))
        self.assertFalse({t.lower() for t in tags} & self.BANNED, (label, tags))
        self.assertEqual(len({t.lower() for t in tags}), len(tags), (label, tags))
        for t in tags:
            words = X._camel_words(t)
            self.assertFalse(len(words) >= 3, (label, t, "long run-together"))
            s = t.lstrip("#")
            self.assertTrue(len(s) <= 16 or s.lower() in X.POPULAR, (label, t, "too long"))
            self.assertNotIn(s.lower(), {"toward", "predicted", "canadian", "effectiveness"})

    def test_low_rank_rows_get_entity_tags_not_filler(self):
        for title, loc, cat, rk in self.LOW:
            it = {"cluster_id": "x" + str(abs(hash(title)) % 10**8), "title": title, "headline": title, "location": loc, "category": cat, "rank": rk, "brief": ""}
            self._ok(X.hashtags(it), title)

    def test_held_rows_and_every_story_fixture_follow_the_rule(self):
        for name, it in STORIES.items():
            self._ok(X.hashtags(it), name)
            self._ok(X.hashtags(dict(it, hidden=True)), name + " (held)")

    def test_finalize_drops_filler_and_pads_from_the_text(self):
        it = {"title": "Nvidia CEO Jensen Huang meets Trump at the White House", "headline": "Nvidia CEO Jensen Huang meets Trump at the White House", "rank": 4}
        tags = X.finalize_tags(["#News", "#BlackoutNetwork", "#Alerts", "#Health"], it)
        self._ok(tags, "padded")
        self.assertTrue({"#Nvidia", "#JensenHuang"} & set(tags), tags)
        self.assertEqual(X.finalize_tags(["#Japan", "#Tokyo", "#Earthquake", "#News", "#Weather"], {"title": "Quake near Tokyo, Japan"}), ["#Earthquake", "#Japan", "#Tokyo"])

    def test_short_popular_tags_topic_first_no_run_togethers(self):
        tags = X.finalize_tags(["#NuclearThreat", "#WarInTheMiddleEast", "#ChiquitaCanyonLandfill", "#Iran"],
                               {"title": "Iran nuclear threat and war in the Middle East", "headline": "Iran nuclear threat and war in the Middle East"})
        self._ok(tags, "shorten")
        self.assertIn("#Nuclear", tags)
        self.assertIn("#War", tags)
        self.assertIn("#Iran", tags)
        self.assertNotIn("#NuclearThreat", tags)
        self.assertNotIn("#WarInTheMiddleEast", tags)
        self.assertNotIn("#ChiquitaCanyonLandfill", tags)
        self.assertIn(tags[0].lstrip("#").lower(), X.POPULAR)  # topic word first
        # stored/junk tags are cleaned when passed into Share-to-X
        it = {"title": "Forest fire in Australia (green alert)", "headline": "Forest fire in Australia (green alert)", "location": "Australia", "category": "natural disaster"}
        text = X.share_text(it, url="https://blackout.network/wire/x?s=x", tags=["#Toward", "#Canadian", "#Predicted", "#WildfireSeasonAlert"])
        self.assertIn("#Wildfire", text)
        self.assertNotIn("#Toward", text)
        self.assertNotIn("#Canadian", text)
        self.assertNotIn("#Predicted", text)
        self.assertNotIn("#WildfireSeasonAlert", text)


if __name__ == "__main__":
    unittest.main()
