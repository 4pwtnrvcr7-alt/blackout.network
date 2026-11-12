"""Story report layer (story_report.py) and its box-side builder (tools/story_reports/build.py)."""
import json, os, sys, tempfile, unittest, importlib
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP); sys.path.insert(0, os.path.join(os.path.dirname(APP), "tools", "story_reports"))

CID = "abcdef0123456789"
NOTE = {"headline": "Officials say the strait stays closed as tanker attacks continue.", "what_happened": "Two tankers were hit on Nov. 11, officials said.",
        "why_it_matters": "Shipping through the strait is down sharply.", "analysis": "Traffic fell to 10 ships a day. This was verified by us.",
        "trajectory": "Steady", "outlook": "More incidents are likely within 72 hours.", "confidence": "High", "confidence_why": "Two outlets.",
        "sources": [{"url": "https://example.org/a", "domain": "example.org", "status": "ok"}], "generated_at": "2026-11-11T22:59:29+00:00",
        "edition": "Nov 11 evening brief"}
ROW = lambda i, fam="USGS", off=1, t="2026-11-11T10:00:00Z": {"source": fam, "family": fam, "title": f"M 6.4 earthquake report {i}", "source_url": f"https://example.org/{i}",
                                                          "first_seen": t, "official": off, "location": "x"}
CL = {"cluster_id": CID, "title": "M 6.4 - 30 km WSW of Lata, Solomon Islands", "category": "natural disaster", "location": "Solomon Islands",
      "brief": "WHAT: M 6.4 - 30 km WSW of Lata [magnitude: 6.4; USGS PAGER alert: green]. WHERE: x. WHEN: y. VERIFY: https://a",
      "first_seen": "2026-11-11T10:00:00Z", "updated": "2026-11-12T01:00:00Z", "event_time": "2026-11-11T09:50:00Z"}

def load(data):
    d = tempfile.mkdtemp(); p = os.path.join(d, "story_reports.json")
    if data is not None: json.dump(data, open(p, "w"))
    os.environ["BN_STORY_REPORTS"] = p
    import story_report; return importlib.reload(story_report)

class Render(unittest.TestCase):
    def test_no_file_degrades_to_factual_summary(self):
        SR = load(None)
        rows = [ROW(i, f) for i, f in enumerate(["USGS", "EMSC", "GDACS"])]
        h, dek = SR.render(CID, CL, rows, 5, "Significant", CL["title"], "", "Solomon Islands", ["USGS"], 3, ["EMSC", "GDACS", "USGS"])
        self.assertEqual(dek, "")
        self.assertIn("What\u2019s happening", h); self.assertIn("Key facts", h); self.assertIn("Magnitude", h)
        self.assertNotIn("BLACKOUT.NETWORK analysis", h); self.assertNotIn("VERIFY", h); self.assertNotIn("<img", h)

    def test_note_renders_analysis_and_dek(self):
        SR = load({"notes": {CID: NOTE}, "images": {}})
        h, dek = SR.render(CID, CL, [ROW(1)], 7, "Major", CL["title"], "", "", [], 1, ["USGS"])
        self.assertEqual(dek, NOTE["headline"])
        for s in ("BLACKOUT.NETWORK analysis", "Why it matters", "What to watch", "Confidence: High", "example.org", "Nov 11 evening brief"):
            self.assertIn(s, h)
        self.assertIn("new reports since", h)        # story updated after the note was written

    def test_empty_story_drops_everything(self):
        SR = load({})
        c = dict(CL, brief="", title="X")
        h, _ = SR.render(CID, c, [], 2, "Low", "X", "", "", [], 0, [])
        self.assertEqual(h, "")

    def test_image_needs_https_and_credit_line(self):
        SR = load({"images": {CID: [{"src": "http://insecure/x.jpg", "w": 10, "h": 10, "link": "https://a"},
                                     {"src": "https://earthquake.usgs.gov/i.jpg", "w": 830, "h": 1006, "link": "https://earthquake.usgs.gov/e",
                                      "alt": "ShakeMap", "caption": "Shaking", "credit": "U.S. Geological Survey ShakeMap", "license": "Public domain"}]}})
        self.assertEqual(SR.figure({"src": "http://insecure/x.jpg", "w": 1, "h": 1, "link": "https://a"}), "")
        f = SR.figure(SR.reports()["images"][CID][1])
        for s in ('loading="lazy"', 'width="830"', 'height="1006"', 'alt="ShakeMap"', "Image: U.S. Geological Survey ShakeMap. Public domain."):
            self.assertIn(s, f)

    def test_no_emoji_in_moments(self):
        SR = load({})
        self.assertEqual(SR.txt("\U0001F6A8 #BREAKING : \U0001F1F8\U0001F1E6 Missile intercepted"), "Missile intercepted")
        rows = [ROW(1, "social", 0), ROW(2, "USGS"), dict(ROW(3, "EMSC"), title="#a #b #c tags only")]
        labs = [l for l, _ in SR.moments(rows)]
        self.assertEqual(labs, ["Earliest report", "Earliest official source"])

class Builder(unittest.TestCase):
    def test_word_rules_and_prep_tips_dropped(self):
        import build as B
        self.assertEqual(B.clean_text("Traffic fell. This was verified by us. Oil rose."), "Traffic fell. Oil rose.")
        self.assertEqual(B.clean_text("On the anniversary of the war, talks resumed."), "")
        self.assertEqual(B.clean_text("blackout network reported it."), "BLACKOUT.NETWORK reported it.")
        d = tempfile.mkdtemp(); p = os.path.join(d, "newsletter_analysis_20261111_pm.json")
        from datetime import datetime, timezone
        it = {"headline": "H.", "what_happened": "W.", "why_it_matters": "Y.", "analysis": "A.", "trajectory": "UPTREND", "outlook": "O.",
              "confidence": "High", "confidence_why": "C.", "what_to_do": "Fill your tank.", "guide": "Prepare", "sources": ["https://example.org/x"]}
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "items": {CID: it, "no sources here x": it, "0123456789abcdef": dict(it, sources=[])}}, open(p, "w"))
        n = B.load_notes([d], 21)
        self.assertEqual(list(n), [CID])
        self.assertNotIn("what_to_do", n[CID]); self.assertNotIn("guide", n[CID])
        self.assertEqual(n[CID]["trajectory"], "Rising"); self.assertEqual(n[CID]["edition"], "Nov 11 evening brief")

if __name__ == "__main__":
    unittest.main()
