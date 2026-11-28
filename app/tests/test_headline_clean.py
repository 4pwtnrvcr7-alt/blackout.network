"""Display / Share-to-X headline cleanup: region codes, zero-width text, quake English."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import headline_clean as HC
import theme
import x_share as X
import story as ST
import re, html
from urllib.parse import parse_qs, urlparse, unquote


def _text(href):
    return parse_qs(urlparse(href).query).get("text", [""])[0]


class TidyText(unittest.TestCase):
    def test_strips_zero_width_space(self):
        raw = "Adjacent Sea of\u200b Chichijima Island"
        self.assertEqual(HC.tidy_text(raw), "Adjacent Sea of Chichijima Island")
        self.assertNotIn("\u200b", HC.tidy_text(raw))

    def test_strips_bom_soft_hyphen_and_nbsp(self):
        raw = "\ufeffM5.9\u00a0earthquake\u00ad Mexico"
        self.assertEqual(HC.tidy_text(raw), "M5.9 earthquake Mexico")

    def test_keeps_accents(self):
        self.assertEqual(HC.tidy_text("Séisme à Québec"), "Séisme à Québec")


class QuakeEnglish(unittest.TestCase):
    def test_mexico_sea_region_code(self):
        h = HC.display_headline("INGV: M5.9 earthquake Mexico [Sea]", location="Mexico")
        self.assertEqual(h, "M5.9 earthquake off the coast of Mexico")
        self.assertNotIn("[Sea]", h)
        self.assertNotIn("INGV", h)

    def test_mexico_land_is_in_not_off_the_coast(self):
        h = HC.display_headline("INGV: M5.9 earthquake Mexico [Land]", location="Mexico")
        self.assertEqual(h, "M5.9 earthquake in Mexico")
        self.assertNotIn("[Land]", h)

    def test_chichijima_zwsp_and_japan_from_location(self):
        raw = "JMA: M5.5 earthquake - Adjacent Sea of\u200b Chichijima Island, max seismic intensity 2"
        h = HC.display_headline(raw, location="Japan")
        self.assertEqual(h, "M5.5 earthquake near Chichijima, Japan")
        self.assertNotIn("\u200b", h)
        self.assertNotIn("Adjacent", h)
        self.assertNotIn("intensity", h)
        self.assertNotIn("JMA", h)

    def test_kuril_keeps_source_direction(self):
        h = HC.display_headline(
            "GEOFON: M4.5 earthquake Northwest of Kuril Islands",
            location="Kuril Islands",
        )
        self.assertEqual(h, "M4.5 earthquake northwest of the Kuril Islands")
        self.assertNotIn("GEOFON", h)

    def test_does_not_invent_a_country(self):
        h = HC.display_headline("INGV: M5.9 earthquake Mexico [Sea]", location="")
        self.assertEqual(h, "M5.9 earthquake off the coast of Mexico")
        self.assertNotIn("Pacific", h)
        self.assertNotIn("United", h)

    def test_idempotent(self):
        h = "M5.9 earthquake off the coast of Mexico"
        self.assertEqual(HC.display_headline(h, location="Mexico"), h)
        h2 = "M5.5 earthquake near Chichijima, Japan"
        self.assertEqual(HC.display_headline(h2, location="Japan"), h2)

    def test_keeps_tsunami_warning_clause(self):
        h = HC.display_headline(
            "M 7.2 earthquake off Japan, tsunami warning issued",
            location="Japan",
        )
        self.assertEqual(h, "M7.2 earthquake off Japan, tsunami warning issued")

    def test_already_english_near_place(self):
        h = HC.display_headline(
            "USGS: M6.1 earthquake near Anchorage, Alaska",
            location="Anchorage, Alaska",
        )
        self.assertEqual(h, "M6.1 earthquake near Anchorage, Alaska")

    def test_off_east_coast_casing(self):
        h = HC.display_headline(
            "GEOFON: M5.0 earthquake Off East Coast of Kamchatka",
            location="Kamchatka, Russia",
        )
        self.assertEqual(h, "M5.0 earthquake off the east coast of Kamchatka, Russia")

    def test_non_quake_only_loses_agency_prefix_and_junk(self):
        h = HC.display_headline(
            "GDACS: Forest fire in Australia (green alert)",
            location="Australia",
        )
        self.assertEqual(h, "Forest fire in Australia (green alert)")

    def test_non_quake_title_unchanged(self):
        t = "Tensions rise on the West Bank after a raid in East Jerusalem"
        self.assertEqual(HC.display_headline(t, location="West Bank"), t)

    def test_theme_headline_matches_and_is_not_cut(self):
        raw = "INGV: M5.9 earthquake Mexico [Sea]"
        self.assertEqual(
            theme._headline(raw, location="Mexico"),
            "M5.9 earthquake off the coast of Mexico",
        )


class ShareIntentText(unittest.TestCase):
    def _item(self, title, location):
        return {
            "cluster_id": "abcd1234abcd1234",
            "title": title,
            "headline": title,
            "location": location,
            "category": "natural disaster",
            "rank": 4,
            "brief": "",
        }

    def test_mexico_share_text_drops_brackets_and_agency(self):
        it = self._item("INGV: M5.9 earthquake Mexico [Sea]", "Mexico")
        href, h, tags = X.compose_intent(it, tags=["#Earthquake", "#Mexico", "#Seismic"])
        self.assertEqual(h, "M5.9 earthquake off the coast of Mexico")
        self.assertEqual(_text(href), h)
        self.assertNotIn("[Sea]", unquote(href))
        self.assertNotIn("INGV", unquote(href))

    def test_japan_share_text_drops_zwsp(self):
        raw = "JMA: M5.5 earthquake - Adjacent Sea of\u200b Chichijima Island, max seismic intensity 2"
        it = self._item(raw, "Japan")
        href, h, tags = X.compose_intent(it, tags=["#Earthquake", "#Japan", "#Seismic"])
        self.assertEqual(h, "M5.5 earthquake near Chichijima, Japan")
        self.assertNotIn("\u200b", h)
        self.assertNotIn("%E2%80%8B", href)
        self.assertEqual(_text(href), h)

    def test_kuril_share_text(self):
        it = self._item("GEOFON: M4.5 earthquake Northwest of Kuril Islands", "Kuril Islands")
        href, h, tags = X.compose_intent(it, tags=["#Earthquake", "#KurilIslands", "#Seismic"])
        self.assertEqual(h, "M4.5 earthquake northwest of the Kuril Islands")
        self.assertEqual(_text(href), h)
        self.assertNotIn("GEOFON", unquote(href))


# Live story fields as of the #345 verify (America/New_York, 2:17 AM ET Nov 28).
# Location still holds the raw agency phrase; a second display_headline pass
# must not glue it back on, and the H1 / Post on X href must match the
# first-pass title used for the document title.
MEXICO = {
    "title": "INGV: M5.9 earthquake Mexico [Sea]",
    "location": "Mexico [Sea]",
    "want": "M5.9 earthquake off the coast of Mexico",
    "tags": ["#Earthquake", "#Mexico", "#Seismic"],
}
JAPAN = {
    "title": "JMA: M5.5 earthquake - Adjacent Sea of\u200b Chichijima Island, max seismic intensity 2",
    "location": "Adjacent Sea of\u200b Chichijima Island, Japan",
    "want": "M5.5 earthquake near Chichijima, Japan",
    "tags": ["#Earthquake", "#Japan", "#Seismic"],
}
KURIL = {
    "title": "GEOFON: M4.5 earthquake Northwest of Kuril Islands",
    "location": "Northwest of Kuril Islands",
    "want": "M4.5 earthquake northwest of the Kuril Islands",
    "tags": ["#Earthquake", "#KurilIslands", "#Seismic"],
}
LIVE = (("Mexico", MEXICO), ("Japan", JAPAN), ("Kuril", KURIL))


def _h1_text(markup):
    m = re.search(r'<h1 class="t">(.*?)</h1>', markup, re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


class FirstPassSurfaces(unittest.TestCase):
    """H1, document title, and Post on X href stay on the first-pass clean headline."""

    def test_display_headline_idempotent_with_raw_location(self):
        for name, ex in LIVE:
            with self.subTest(name):
                first = HC.display_headline(ex["title"], location=ex["location"])
                self.assertEqual(first, ex["want"], name)
                self.assertEqual(HC.display_headline(first, location=ex["location"]), first, name)
                self.assertNotIn("\u200b", first)
                self.assertNotIn("[Sea]", first)
                self.assertNotIn("Adjacent Sea", first)
                self.assertNotIn("INGV", first)
                self.assertNotIn("JMA", first)
                self.assertNotIn("GEOFON", first)

    def test_h1_matches_first_pass_title(self):
        for name, ex in LIVE:
            with self.subTest(name):
                title = ST._display_title(ex["title"], ex["location"])
                self.assertEqual(title, ex["want"], name)
                # Same call the story page now makes: H1 from the first-pass title,
                # not from a desk/template dek_note that lost the [Sea] cue.
                markup = ST._h1(title, "A brief that is not the headline.", ex["location"])
                self.assertEqual(_h1_text(markup), ex["want"], name)
                self.assertNotIn("Adjacent Sea", markup)
                self.assertNotIn("[Sea]", markup)
                self.assertNotIn("\u200b", markup)

    def test_mexico_h1_keeps_off_the_coast_even_if_dek_note_lost_sea(self):
        title = ST._display_title(MEXICO["title"], MEXICO["location"])
        self.assertEqual(title, MEXICO["want"])
        # Old path: _h1(clean_title(dek_note), ...) with a note that had no [Sea].
        dirty_note = "M5.9 earthquake Mexico"
        self.assertEqual(ST._h1(dirty_note, "", MEXICO["location"]).count("off the coast of"), 0)
        self.assertIn("off the coast of", ST._h1(title, dirty_note, MEXICO["location"]))
        self.assertEqual(_h1_text(ST._h1(title, dirty_note, MEXICO["location"])), MEXICO["want"])

    def test_intent_href_matches_first_pass_when_headline_already_clean(self):
        for name, ex in LIVE:
            with self.subTest(name):
                first = HC.display_headline(ex["title"], location=ex["location"])
                it = {
                    "cluster_id": "abcd1234abcd1234",
                    "title": first,
                    "headline": first,
                    "location": ex["location"],
                    "category": "natural disaster",
                    "rank": 4,
                    "brief": "",
                }
                href, h, tags = X.compose_intent(it, tags=ex["tags"])
                self.assertEqual(h, ex["want"], name)
                self.assertEqual(_text(href), ex["want"], name)
                self.assertNotIn("Adjacent Sea", unquote(href))
                self.assertNotIn("[Sea]", unquote(href))
                self.assertNotIn("%E2%80%8B", href)
                self.assertNotIn("INGV", unquote(href))
                self.assertNotIn("JMA", unquote(href))
                self.assertNotIn("GEOFON", unquote(href))




if __name__ == "__main__":
    unittest.main()
