"""Share-to-X hashtag generator. Run: cd app && python3 -m unittest tests.test_x_share -v"""
import os, sys, unittest
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
        self.assertIn("#Outbreak", tags)
        self.assertNotIn("#Kenya", tags)
        self.assertNotIn("#Nigeria", tags)
        self.assertNotIn("#Bundibugyo", tags)
        desk = "Congo's Ebola outbreak reached 11,821 confirmed cases and 5,810 deaths as fighting traps responders in Ituri."
        dtags = X.hashtags(it, headline=desk)
        self.assertIn("#DRC", dtags)
        self.assertIn("#Ebola", dtags)
        self.assertIn("#Outbreak", dtags)
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
        self.assertIn("#Outbreak", tags)
        self.assertNotIn("#BirdFlu", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_ukraine_strike_rank5_has_war_tags(self):
        it = STORIES["ukraine_kryvyi"]
        tags = X.hashtags(it)
        self.assertIn("#Ukraine", tags)
        self.assertIn("#KryvyiRih", tags)
        self.assertIn("#UkraineWar", tags)
        self.assertIn("#MissileStrike", tags)
        self.assertIn("#War", tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)

    def test_kyiv_bridges_rank6_has_war_tags(self):
        it = STORIES["kyiv_bridges"]
        tags = X.hashtags(it)
        self.assertIn("#Ukraine", tags)
        self.assertIn("#Kyiv", tags)
        self.assertIn("#UkraineWar", tags)
        self.assertIn("#War", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_cyber_global_rank3_reaches_three(self):
        it = STORIES["cyber_drupal"]
        tags = X.hashtags(it)
        self.assertGreaterEqual(len(tags), 3)
        self.assertTrue("#CVE" in tags or "#Cybersecurity" in tags)
        self.assertIn("#Cyberattack", tags)

    def test_florida_rain_rank7(self):
        it = STORIES["florida_rain"]
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertIn("#Weather", tags)
        self.assertTrue("#Storm" in tags or len(tags) >= 3)
        self.assertNotIn("#Hurricane", tags)
        self.assertNotIn("#Tampa", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_miami_flood_rank7(self):
        it = STORIES["miami_flood"]
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertIn("#Miami", tags)
        self.assertIn("#Flood", tags)
        self.assertIn("#Weather", tags)
        self.assertNotIn("#Hollywood", tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertLessEqual(len(tags), 5)

    def test_tornado_watch_rank5_florida_weather(self):
        it = STORIES["fl_tornado_watch"]
        tags = X.hashtags(it)
        self.assertIn("#Florida", tags)
        self.assertIn("#Tornado", tags)
        self.assertIn("#Weather", tags)
        self.assertNotIn("#Melbourne", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_held_and_false_positive_location_plus_generic(self):
        it = dict(STORIES["ebola_drc"], hidden=True)
        tags = X.hashtags(it)
        self.assertIn("#DRC", tags)
        self.assertNotIn("#Ebola", tags)
        self.assertNotIn("#Outbreak", tags)
        self.assertGreaterEqual(len(tags), 3)
        self.assertTrue("#News" in tags or "#WorldNews" in tags)
        wl = dict(STORIES["kyiv_bridges"], rank=7, watchlist=1)
        tags = X.hashtags(wl)
        self.assertIn("#Ukraine", tags)
        self.assertNotIn("#UkraineWar", tags)
        self.assertNotIn("#War", tags)
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

    def test_intent_url_and_button_hides_tags_from_label(self):
        it = STORIES["ebola_drc"]
        href = X.intent_url(it)
        self.assertTrue(href.startswith("https://x.com/intent/post?"))
        q = parse_qs(urlparse(href).query)
        text = q["text"][0]
        url = q["url"][0]
        self.assertTrue(url.endswith("/wire/5932fb61c94775cd"))
        self.assertIn("#Ebola", text)
        self.assertIn("#DRC", text)
        self.assertNotIn("#Kenya", text)
        html = X.button_html(it)
        self.assertIn("Post on X", html)
        self.assertIn('target="_blank"', html)
        self.assertNotIn("#Ebola", html)
        self.assertNotIn("#DRC", html)
        self.assertIn("%23Ebola", html)
        self.assertLessEqual(X.weighted_len(text, url), 280)


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


if __name__ == "__main__":
    unittest.main()
