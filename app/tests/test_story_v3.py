"""Story v3 pages (BN_STORY_V3): narrative layout, no scoring jargon, flag-off leaves Wire v2 unchanged."""
import json, os, sys, unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
# Isolate from whatever the box already exported
for k in list(os.environ):
    if k.startswith("BN_STORY"):
        os.environ.pop(k, None)

STATE_CANDIDATES = [
    os.environ.get("BN_STORY_V3_STATE", ""),
    "/workspace/previews/story_v3/state_snapshot.json",
    "/workspace/previews/wire_v2/state_snapshot.json",
]
MERS = "6727e7f2ac056676"

def load_state():
    for p in STATE_CANDIDATES:
        if p and os.path.isfile(p):
            return json.load(open(p))
    raise unittest.SkipTest("no /api/state snapshot")

class StoryV3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["BN_STORY_V3_BRIEFS"] = str(APP / "data" / "story_v3_briefs.json")
        cls.state = load_state()
        import wire_v2
        cls.W = wire_v2

    def setUp(self):
        os.environ.pop("BN_STORY_V3", None)
        self.W._C.clear()

    def test_on_by_default(self):
        import story_v3 as V3
        os.environ.pop("BN_STORY_V3", None); self.assertTrue(V3.on())
        os.environ["BN_STORY_V3"] = "0"; self.assertFalse(V3.on())

    def test_story_css_follows_wire2_version(self):
        html = self.W.render_story(self.state, MERS)
        self.assertIn("story3.css", html)

    def test_flag_off_keeps_v2_card(self):
        os.environ["BN_STORY_V3"] = "0"
        html = self.W.render_story(self.state, MERS)
        self.assertIsNotNone(html)
        self.assertIn("FULL REPORT", html)
        self.assertIn("CONFIDENCE", html)
        self.assertNotIn('class="sv3-hero"', html)
        self.assertNotIn("What happened", html)

    def test_mers_is_a_real_story(self):
        os.environ["BN_STORY_V3"] = "1"
        html = self.W.render_story(self.state, MERS)
        self.assertIsNotNone(html)
        self.assertIn('class="sv3-hero"', html)
        self.assertIn("sv3_mers_hero.mp4", html)
        self.assertIn("sv3_mers_hero_m.webp", html)
        self.assertIn("What happened", html)
        self.assertIn("Background and history", html)
        self.assertIn("Our analysis", html)
        self.assertIn("What to watch next", html)
        self.assertIn("WHO Disease Outbreak News", html)
        self.assertIn("All 99 contacts", html)
        self.assertIn("2012", html)
        self.assertNotIn("severity 65/100", html)
        self.assertNotIn("none of them official yet", html)
        self.assertNotIn("item(s)", html)
        # compact rank/confidence sit after the narrative, not as the lead
        self.assertLess(html.find("What happened"), html.find("Confidence and rank"))
        self.assertIn("How we rank", html)
        self.assertIn("/credits#stories", html)
        self.assertNotIn("scroll-snap-type: y", html.lower())

    def test_all_five_top_stories_have_narrative(self):
        os.environ["BN_STORY_V3"] = "1"
        ids = [
            "6727e7f2ac056676",
            "c5dc0cd611846d11",
            "7c3eeef121ae8d73",
            "845376abeeade96f",
            "bb45c246c2ea909b",
        ]
        for cid in ids:
            html = self.W.render_story(self.state, cid)
            self.assertIsNotNone(html, cid)
            self.assertIn("What happened", html, cid)
            self.assertIn("Background and history", html, cid)
            self.assertIn("Our analysis", html, cid)
            self.assertIn("What to watch next", html, cid)
            self.assertIn('class="sv3-hero"', html, cid)
            self.assertNotIn("severity ", html, cid)

    def test_fallback_without_desk_story_is_honest(self):
        os.environ["BN_STORY_V3"] = "1"
        # a cluster with no v3 brief and no desk note: the page must stay honest
        fake = {
            "cluster_id": "aaaaaaaaaaaaaaaa",
            "title": "A listed story with only a scanner title",
            "category": "other",
            "rank": 4,
            "n_families": 2,
            "families": ["example.com", "other.example"],
            "n_items": 2,
            "brief": "WHAT: A listed story with only a scanner title. CONFIDENCE: High — reported by 2 item(s); severity 40/100, rank 4/10.",
            "links": [{"source": "Example", "url": "https://example.com/story"}],
            "updated": "2026-11-17T20:00:00Z",
        }
        st = dict(self.state)
        st["main"] = list(self.state.get("main") or []) + [fake]
        html = self.W.render_story(st, fake["cluster_id"])
        self.assertIsNotNone(html)
        self.assertIn('class="sv3-hero"', html)
        self.assertIn("We have not yet written this story up", html)
        self.assertNotIn("Background and history", html)
        self.assertNotIn("severity 40/100", html)
        self.assertNotIn("item(s)", html)

    def test_schema_is_backwards_compatible(self):
        d = json.load(open(APP / "data" / "story_v3_briefs.json"))
        b = d["briefs"][MERS]
        for k in ("headline", "what_happened", "analysis", "sources", "written_at"):
            self.assertTrue(b.get(k), k)
        st = b["story"]
        self.assertIn("happened", st["sections"])
        self.assertIn("background", st["sections"])
        self.assertIn("analysis", st["sections"])
        self.assertIn("watch", st["sections"])

    def test_css_has_no_yellow_or_snap(self):
        css = (APP / "wire_v2_static" / "story3.css").read_text()
        self.assertNotRegex(css, r"#(?:ffc|f5c|eab|ff0|FFD|ffd)")
        self.assertNotIn("yellow", css.lower())
        self.assertIn("scroll-snap-type: none", css)

    def test_build_passes_story_through(self):
        sys.path.insert(0, str(APP.parent / "tools" / "story_reports"))
        import build
        sample = {
            "briefs": {
                MERS: {
                    "headline": "Test headline about a sourced fact.",
                    "what_happened": "Something happened on Tuesday, according to WHO.",
                    "why_it_matters": "It matters.",
                    "analysis": "Because of the sources.",
                    "rank_why": "Rank note.",
                    "risk": "Low",
                    "risk_why": "Contained.",
                    "if_true": "Signposts.",
                    "if_false": "Otherwise.",
                    "what_to_do": "No action is needed.",
                    "confidence": "High",
                    "confidence_why": "WHO notice.",
                    "sources": ["https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON626"],
                    "written_at": "2026-11-17T21:40:00Z",
                    "story": {"headline": "Full", "sections": {"happened": "A", "background": "B", "analysis": "C", "watch": "D"}},
                }
            }
        }
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(sample, f)
            path = f.name
        out = build.load_desk_briefs(path, 21)
        self.assertIn(MERS, out)
        self.assertEqual(out[MERS]["story"]["sections"]["background"], "B")
        os.unlink(path)

if __name__ == "__main__":
    unittest.main()
