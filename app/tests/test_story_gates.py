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


    def test_commemoration_dropped_even_with_facts_threats_kept(self):
        """Wreath/anniversary/memorial ceremonies drop even with fact-bearing analysis.
        Real current-threat items must not be affected."""
        wreath = {
            "cluster_id": "wilm1898",
            "title": "Wreath ceremony honors the 128th anniversary of Wilmington's 1898 coup and massacre",
            "category": "political", "rank": 5,
            "analyst": {
                "what": "Wilmington held a wreath ceremony marking the 128th anniversary of the 1898 coup and massacre.",
                "analysis": "The ceremony recalled the 1898 coup that overthrew the city's government and killed dozens of Black residents.",
            },
        }
        today = {
            "cluster_id": "tih1",
            "title": "Today in History: a bomb killed 241 US service members in Beirut in 1983",
            "category": "war", "rank": 6,
            "analyst": {
                "what": "On this date in 1983, a bomb killed 241 US service members in Beirut.",
                "analysis": "The attack remains one of the deadliest days for US forces since World War II.",
            },
        }
        kasparov = {
            "cluster_id": "9e63d729bb63212d",
            "title": "Garry Kasparov cancels a Berlin appearance after security services warn of a Russian assassination threat.",
            "category": "political", "rank": 7, "from_note": True,
            "analyst": {"from_note": True,
                        "what": "Kasparov canceled a Berlin appearance after security services warned of a Russian assassination threat.",
                        "analysis": "When a US-based dissident cannot safely visit a European capital, it shows how far Russia's covert operations are believed to reach."},
        }
        iran = {
            "cluster_id": "fridge1",
            "title": "France summons Iran's ambassador and seeks EU sanctions over a cyberattack that sabotaged fridges in 700 supermarkets",
            "category": "cyber", "rank": 7,
            "analyst": {
                "what": "France summoned Iran's ambassador after a cyberattack sabotaged refrigerators in about 700 supermarkets.",
                "analysis": "An IRGC-linked unit is blamed for hitting grocery cold chains far from any battlefield.",
            },
        }
        self.assertEqual(SG.item_drop_reason(wreath), "historical commemoration, not a current threat")
        self.assertEqual(SG.item_drop_reason(today), "historical commemoration, not a current threat")
        self.assertIsNone(SG.item_drop_reason(kasparov))
        self.assertIsNone(SG.item_drop_reason(iran))
        issue = {"politics": [wreath, kasparov], "main": [today, iran], "analysis": {"items": [
            {"cluster_id": "wilm1898"}, {"cluster_id": "tih1"},
            {"cluster_id": "9e63d729bb63212d"}, {"cluster_id": "fridge1"},
        ]}}
        dropped = SG.prune_issue(issue)
        drop_ids = {d[1] for d in dropped}
        self.assertEqual(drop_ids, {"wilm1898", "tih1"})
        self.assertEqual([it["cluster_id"] for it in issue["politics"]], ["9e63d729bb63212d"])
        self.assertEqual([it["cluster_id"] for it in issue["main"]], ["fridge1"])
        self.assertEqual({x["cluster_id"] for x in issue["analysis"]["items"]}, {"9e63d729bb63212d", "fridge1"})

    def test_unnoted_filler_dropped_even_with_fact_headline(self):
        """A late story with no analyst note and template WHAT HAPPENED is dropped,
        even when the headline itself states a death or other fact. Keeping it used
        to ship filler and block the whole issue at the QA gate (Nov 11 morning)."""
        indiana = {
            "cluster_id": "33fdb1b760f2e54a",
            "title": "Man killed in southeastern Indiana home explosion, fire",
            "category": "war/conflict",
            "rank": 5,
            "analyst": {
                "what": "On the record for Man killed in southeastern Indiana home explosion, fire: rank 5/10, 0 independent sources after collapsing repeated headlines.",
                "analysis": "The reports describe the use of force in Indiana (Man killed in southeastern Indiana home). Cluster first seen Nov 11. Scanner history 24h: not enough history.",
            },
        }
        self.assertIsNone(SG.item_drop_reason(indiana))  # no notes file in play: historic keep
        self.assertIsNotNone(SG.item_drop_reason(indiana, notes_active=True))
        self.assertIn("no analyst note", SG.item_drop_reason(indiana, notes_active=True))
        # A fact-bearing scanner summary can still salvage the card when notes are active.
        salvaged = dict(indiana)
        salvaged["what"] = "A man was killed when a home exploded and caught fire in southeastern Indiana early Wednesday, Nov. 11, local officials said."
        salvaged["analyst"] = dict(indiana["analyst"])
        self.assertIsNone(SG.item_drop_reason(salvaged, notes_active=True))
        self.assertNotIn("On the record", (salvaged.get("analyst") or {}).get("what") or "")
        noted = {
            "cluster_id": "noted1",
            "title": "Treasury Secretary Bessent moved to a military base after an Iranian threat.",
            "category": "political", "rank": 7, "from_note": True,
            "analyst": {"from_note": True,
                        "what": "Treasury Secretary Scott Bessent moved to a military base after an Iranian threat against his life.",
                        "analysis": "The war's risk is now reaching US officials at home."},
        }
        # give salvaged its own id so prune can keep it
        salvaged["cluster_id"] = "keep1"
        issue = {"notes_lead": "Today is Veterans Day. Thank you to everyone who has served.",
                 "notable": [indiana], "main": [noted, salvaged], "analysis": {"items": [
            {"cluster_id": "33fdb1b760f2e54a"}, {"cluster_id": "keep1"}, {"cluster_id": "noted1"},
        ]}}
        dropped = SG.prune_issue(issue)
        self.assertTrue(any(d[1] == "33fdb1b760f2e54a" for d in dropped))
        self.assertEqual([it["cluster_id"] for it in issue["notable"]], [])
        self.assertEqual([it["cluster_id"] for it in issue["main"]], ["noted1", "keep1"])

    def test_prep_unaffected(self):

        self.assertIsNone(SG.selection_block_reason({"kind": "prep", "title": SMIC}))

if __name__ == "__main__":
    unittest.main()
