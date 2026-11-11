"""Offline tests for story_gates (brief + social selection). No network, no send, no scanner writes."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_gates as SG
SMIC = "Coup de pouce au smic: le gouvernement fracture l’intersyndicale, pas la mobilisation sociale"
SMIC_ID = "d4c11e75bf8722e0"

class StoryGatesTests(unittest.TestCase):
    def test_hard_block_by_cluster_id(self):
        item = {"cluster_id": SMIC_ID, "title": "Unrelated English placeholder", "category": "political", "rank": 9}
        self.assertIsNotNone(SG.is_hard_blocked(item))
        self.assertIn("cluster", SG.selection_block_reason(item))

    def test_hard_block_by_headline_new_cluster(self):
        item = {"cluster_id": "ffffffffffffffff", "title": SMIC, "category": "political", "rank": 9}
        self.assertIsNotNone(SG.is_hard_blocked(item))
        self.assertIn("headline", SG.selection_block_reason(item))

    def test_hard_block_english_retitle(self):
        item = {"cluster_id": "eeeeeeeeeeeeeeee", "headline": "France raises the SMIC minimum wage after union talks", "rank": 8}
        self.assertIsNotNone(SG.is_hard_blocked(item))

    def test_seismic_not_blocked_as_smic(self):
        item = {"cluster_id": "c6f83f83f5f79feb",
                "title": "JMA: M6.1 earthquake - Off the east Coast of Kanto, max seismic intensity 3",
                "category": "natural disaster", "rank": 5}
        self.assertIsNone(SG.is_hard_blocked(item))
        self.assertTrue(SG.is_english_headline(item["title"]))
        self.assertIsNone(SG.selection_block_reason(item))

    def test_non_english_dropped(self):
        item = {"title": SMIC, "cluster_id": "ffffffffffffffff", "category": "political"}
        self.assertFalse(SG.is_english_headline(SMIC))
        # hard block wins, but language would also drop it
        self.assertFalse(SG.is_english_headline("El gobierno anuncia un recorte del gasto publico en Madrid"))

    def test_english_with_accents_kept(self):
        self.assertTrue(SG.is_english_headline("Paraguay's ousted president Santiago Peña is under house arrest."))
        self.assertTrue(SG.is_english_headline("A dam burst near São Paulo kills 12 after heavy rain."))

    def test_foreign_labor_excluded_geopolitical_kept(self):
        labor = {"title": "German unions call a nationwide strike over a wage dispute", "category": "political", "rank": 8}
        self.assertIsNotNone(SG.is_foreign_domestic_nonthreat(labor))
        cyber = {"title": "France summons Iran's ambassador and seeks EU sanctions over a cyberattack that sabotaged fridges in 700 supermarkets.",
                 "category": "cyber", "rank": 7}
        self.assertIsNone(SG.selection_block_reason(cyber))
        kasparov = {"title": "Garry Kasparov cancels a Berlin appearance after security services warn of a Russian assassination threat.",
                    "category": "political", "rank": 7}
        self.assertIsNone(SG.selection_block_reason(kasparov))
        us_pol = {"title": "The House holds its first test vote on impeaching Defense Secretary Hegseth as he calls the effort a 'farce.'",
                  "category": "political", "rank": 7, "location": "Washington, D.C."}
        self.assertIsNone(SG.selection_block_reason(us_pol))
        bank = {"title": "Paraguay says 93% of eligible Ueno Bank savers have been repaid, but the fight over pension money continues",
                "category": "financial", "rank": 7}
        self.assertIsNone(SG.selection_block_reason(bank))

    def test_template_filler_vs_facts(self):
        what = "On the record for Coup de pouce au smic: le gouvernement…: rank 5/10."
        anal = ("The reports describe a government action in “Coup de pouce au smic: le gouvernement fracture "
                "l’intersyndicale, pas la mobilisation…”. Cluster first seen Nov 10, 1:16 AM ET. "
                "Scanner history 24h: not enough history.")
        self.assertTrue(SG.is_template_filler(what, anal, SMIC))
        self.assertFalse(SG.is_template_filler(
            "On the record for M6.4 Solomon Islands: M6.4, 3 deaths in the latest report that states a figure, rank 5/10.",
            "The reports describe a natural hazard in “M 6.4 - 30 km WSW of Lata, Solomon Islands”. Official source on record: USGS. deaths stated in the reports rose from 0 to 3.",
            "M 6.4 - 30 km WSW of Lata, Solomon Islands"))
        self.assertFalse(SG.is_template_filler(
            "The Justice Department unsealed an eight-count indictment in Manhattan on Tuesday, Nov. 10, charging three men.",
            "Prosecutors say the network was behind about 18 attacks in Europe and a plot at RAF Fairford.",
            "US charges three Iran-backed operatives over attacks in Europe and a plot at a UK base.",
            from_note=True))

    def test_prune_drops_smic_and_filler(self):
        issue = {
            "politics": [
                {"cluster_id": SMIC_ID, "title": SMIC, "category": "political", "rank": 5,
                 "analyst": {"what": "On the record for Coup de pouce au smic: le gouvernement…: rank 5/10.",
                             "analysis": "The reports describe a government action in “Coup de pouce au smic”."}},
                {"cluster_id": "9e63d729bb63212d",
                 "title": "Garry Kasparov cancels a Berlin appearance after security services warn of a Russian assassination threat.",
                 "category": "political", "rank": 7, "from_note": True,
                 "analyst": {"from_note": True,
                             "what": "Kasparov canceled a Berlin appearance after security services warned of a Russian assassination threat.",
                             "analysis": "When a US-based dissident cannot safely visit a European capital, it shows how far Russia's covert operations are believed to reach."}},
            ],
            "main": [],
            "analysis": {"items": [{"cluster_id": SMIC_ID}, {"cluster_id": "9e63d729bb63212d"}]},
        }
        dropped = SG.prune_issue(issue)
        self.assertTrue(any(d[1] == SMIC_ID for d in dropped))
        self.assertEqual([it["cluster_id"] for it in issue["politics"]], ["9e63d729bb63212d"])
        self.assertEqual([x["cluster_id"] for x in issue["analysis"]["items"]], ["9e63d729bb63212d"])

    def test_prep_unaffected(self):
        self.assertIsNone(SG.selection_block_reason({"kind": "prep", "title": SMIC}))

if __name__ == "__main__":
    unittest.main()
