"""Display / Share-to-X headline cleanup: region codes, zero-width text, quake English."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import headline_clean as HC
import theme
import x_share as X
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


if __name__ == "__main__":
    unittest.main()
