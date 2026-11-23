"""Display-time category, entertainment filter, and WHERE fallback."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import story_display as SD

ILL = "Mystery Illness Strikes California Marathon Runners"
MOVIE = ("Wild Horse Nine - watched this today and loved it. It's a dark comedy about two CIA agents "
         "in Chile right before the military coup in 1973. It has a stellar cast with John Malkovich")
BRIEF = "WHAT: Mystery Illness Strikes California Marathon Runners. WHERE: location not specified by source. WHEN: Nov 9."

class Category(unittest.TestCase):
    def test_illness_strikes_is_disease(self):
        self.assertEqual(SD.display_category(ILL, "war/conflict"), "disease")
        self.assertEqual(SD.display_category(ILL, "political"), "disease")
    def test_strong_conflict_kept(self):
        t = "Missile strikes hospital as measles outbreak spreads in Gaza"
        self.assertEqual(SD.display_category(t, "war/conflict"), "war/conflict")
    def test_hits_alone_with_outbreak(self):
        self.assertEqual(SD.display_category("Outbreak hits boarding schools in Kenya", "war/conflict"), "disease")
    def test_flood_emergency_is_disaster(self):
        self.assertEqual(SD.display_category("Edgewater declares state of emergency amid flooding", "political"), "natural disaster")
        self.assertEqual(SD.display_category("Edgewater declares a state of emergency as flooding hits the city", "political"), "natural disaster")
        self.assertEqual(SD.display_category("Storms batter the Arizona coast as the governor declares an emergency", "political"), "natural disaster")
    def test_coup_emergency_stays_political(self):
        self.assertEqual(SD.display_category("President declares state of emergency after coup attempt", "political"), "political")
        self.assertEqual(SD.display_category("Mass protests as parliament is dissolved", "political"), "political")
    def test_conflict_with_weather_word_kept(self):
        self.assertEqual(SD.display_category("Missile strikes hospital as storms delay the evacuation", "war/conflict"), "war/conflict")

class Entertainment(unittest.TestCase):
    def test_movie_review(self):
        self.assertTrue(SD.is_entertainment_junk(MOVIE))
        self.assertFalse(SD.visible({"title": MOVIE}))
    def test_news_not_hidden(self):
        self.assertFalse(SD.is_entertainment_junk("Series of attacks on grain ships in the Red Sea"))
        self.assertFalse(SD.is_entertainment_junk("Flu season drives hospital admissions in New York"))
        self.assertFalse(SD.is_entertainment_junk(ILL))

class Where(unittest.TestCase):
    def test_california_from_headline(self):
        self.assertEqual(SD.place_from_headline(ILL), "California")
        b = SD.rewrite_brief(BRIEF, ILL, None)
        self.assertIn("WHERE: California", b)
        self.assertNotIn("not specified", b)
    def test_apply_sets_location_and_category(self):
        out = SD.apply({"title": ILL, "category": "war/conflict", "brief": BRIEF, "location": None})
        self.assertEqual(out["category"], "disease")
        self.assertEqual(out["location"], "California")
        self.assertIn("WHERE: California", out["brief"])
        self.assertFalse(out["hidden"])

if __name__ == "__main__":
    unittest.main()
