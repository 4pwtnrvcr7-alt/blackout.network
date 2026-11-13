"""Nov 13 fix: the 7 AM brief was blocked for every subscriber (Nov 12 + Nov 13) because a fallback (un-noted) story card printed a
boilerplate ANALYSIS line that the renderer let through (it judged WHAT HAPPENED + ANALYSIS together) while the pre-send QA gate
judges each paragraph alone. Offline: no network, no send, no database."""
import os, sys, unittest
from pathlib import Path
os.environ.setdefault("NEWSLETTER_NO_WORKER", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import newsletter_analysis as NA
import newsletter_qa as QA
import story_gates as SG

WHAT = "On the record (Israeli occupation forces): 6 deaths stated in the reports, rank 5/10, 1 independent source after collapsing repeated headlines."
ANAL = "The reports describe the use of force in Khan Younis (Israeli occupation forces), rank 5/10."
TITLE = "Israeli occupation forces carried out a new massacre at dawn today, bombing the intensive care unit at Nasser Medical Complex"

def fallback(**kw):
    a = {"from_note": False, "cluster_id": "38dad02c3cdcc6bf", "title": TITLE, "category": "war/conflict", "rank": 5,
         "what_short": WHAT, "analysis_short": ANAL, "trajectory": "Steady", "outlook": "The danger holds at rank 5/10.",
         "trend_from_history": True, "confidence": "Low", "confidence_line": "Confidence: Low. 1 independent source (RSS: AP)."}
    a.update(kw); return a

def gate(html):
    return QA.check("Morning Brief, Nov 13: A story + 9 more", html, "", [], [])

class MorningFillerTests(unittest.TestCase):
    def test_the_mismatch_that_blocked_the_issue(self):
        # renderer's old combined test passes the pair; the gate's per-line test flags the ANALYSIS line alone
        self.assertFalse(SG.is_template_filler(WHAT, ANAL, TITLE))
        self.assertTrue(SG.is_template_filler("", ANAL, ""))
        self.assertFalse(SG.is_template_filler(WHAT, "", ""))

    def test_fallback_card_drops_boilerplate_analysis_and_passes_gate(self):
        html = NA.card_fragment(fallback())
        self.assertNotIn("The reports describe the use of force", html)
        self.assertIn("6 deaths stated in the reports", html)      # the fact-bearing line stays
        r = gate(html)
        self.assertTrue(r["ok"], r["blockers"])

    def test_filler_what_line_dropped_alone(self):
        w = "On the record (Some place): rank 5/10, 1 independent source after collapsing repeated headlines."
        html = NA.card_fragment(fallback(what_short=w))
        self.assertNotIn("On the record (Some place)", html)
        self.assertTrue(gate(html)["ok"], gate(html)["blockers"])

    def test_takeaway_alone_is_not_an_empty_analysis_paragraph(self):
        html = NA.card_fragment(fallback(takeaway="Six people were killed, including a surgeon, in a strike on the hospital."))
        self.assertIn("ANALYSIS", html)
        r = gate(html)
        self.assertTrue(r["ok"], r["blockers"])
        self.assertFalse(any("empty" in b for b in r["blockers"]))

    def test_why_ranked_takeaway_still_suppressed(self):
        html = NA.card_fragment(fallback(takeaway="Rank 5 is why this is ranked here."))
        self.assertNotIn("why this is ranked", html)

    def test_real_analysis_kept(self):
        real = "Israel says it targeted a Hamas brigade commander; the hospital denies fighters were inside, and reporters cannot enter Gaza to check."
        html = NA.card_fragment(fallback(analysis_short=real))
        self.assertIn("reporters cannot enter Gaza", html)
        self.assertTrue(gate(html)["ok"])

    def test_note_cards_unchanged(self):
        a = {"from_note": True, "what": "An Israeli strike hit Nasser hospital, killing six people.", "analysis": "Strikes continue despite the ceasefire.",
             "outlook": "More strikes are likely.", "confidence": "Medium", "what_to_do": "Nothing for US readers.", "trajectory": "Steady"}
        html = NA.card_fragment(a)
        self.assertIn("Strikes continue despite the ceasefire.", html)

class GatePrefixTests(unittest.TestCase):
    SRC = "Bomb alert at train station in northern France disrupts Eurostar trains between London and Paris. French authorities have evacuated the station"

    def test_whole_first_sentence_is_not_a_cut(self):
        self.assertIsNone(QA._prefix_of("Bomb alert at train station in northern France disrupts Eurostar trains between London and Paris", [self.SRC]))

    def test_real_mid_sentence_cut_still_blocks(self):
        self.assertEqual(QA._prefix_of("Bomb alert at train station in northern France disrupts Eurostar trains between", [self.SRC]), self.SRC)
        self.assertIsNotNone(QA._prefix_of("Iran warns ships around the strait even", ["Iran warns ships around the strait even while it says it wants a deal."]))

if __name__ == "__main__":
    unittest.main()
