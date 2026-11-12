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
        for s in ("What happened", "What we see", "Why we ranked it this way", "Risk factor", "If it\u2019s true", "If it\u2019s overblown",
                  "What you should do", "Sources", "Key facts", "Magnitude", "Signal snapshot", "Quick brief, built automatically", "ready.gov/earthquakes"):
            self.assertIn(s, h)
        self.assertIn("3 independent sources are reporting this, including 1 official source (USGS)", h)
        self.assertNotIn("VERIFY", h); self.assertNotIn("<img", h)

    def test_note_renders_analysis_and_dek(self):
        SR = load({"notes": {CID: NOTE}, "images": {}})
        h, dek = SR.render(CID, CL, [ROW(1)], 7, "Major", CL["title"], "", "", [], 1, ["USGS"])
        self.assertEqual(dek, NOTE["headline"])
        for s in ("Bottom line", "Why it matters", "If it\u2019s true", "More incidents are likely within 72 hours.", "confidence in the reporting is high",
                  "example.org", "Nov 11 evening brief", "Risk: High"):
            self.assertIn(s, h)
        self.assertNotIn("Quick brief", h)
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

    def test_risk_bands_and_desk_override(self):
        SR = load({"notes": {CID: dict(NOTE, risk="Low", risk_why="Officials say there is no wider risk")}})
        self.assertEqual(SR.risk(3)[0], "Low"); self.assertEqual(SR.risk(4)[0], "Medium"); self.assertEqual(SR.risk(6)[0], "Medium"); self.assertEqual(SR.risk(7)[0], "High")
        h, _ = SR.render(CID, CL, [ROW(1)], 7, "Major", CL["title"], "", "", [], 1, ["USGS"])
        self.assertIn("Risk: Low", h); self.assertIn("Our analysts rate this low: Officials say there is no wider risk.", h)

    def test_alias_and_share_cards_need_approval(self):
        sh = {"src": "https://img.example.org/a.jpg", "link": "https://example.org/a", "site": "Example", "title": "T", "ok": False}
        SR = load({"notes": {"1111111111111111": NOTE}, "alias": {CID: "1111111111111111"}, "shares": {CID: [sh]}})
        h, dek = SR.render(CID, CL, [ROW(1)], 5, "Significant", CL["title"], "", "", ["USGS"], 1, ["USGS"])
        self.assertEqual(dek, NOTE["headline"]); self.assertNotIn("sr-share", h.split("</style>", 1)[1])
        SR = load({"shares": {CID: [dict(sh, ok=True)]}})
        h, _ = SR.render(CID, CL, [ROW(1)], 5, "Significant", CL["title"], "", "", ["USGS"], 1, ["USGS"])
        self.assertIn('class="sr-share"', h); self.assertIn("shown as a link preview", h)

    def test_share_cards_auto_policy_shows_with_credit(self):
        sh = {"src": "https://img.example.org/a.jpg", "link": "https://example.org/a", "site": "Example News", "title": "T", "ok": False}
        SR = load({"shares": {CID: [sh]}, "share_policy": {"auto": True}})
        h, _ = SR.render(CID, CL, [ROW(1)], 5, "Significant", CL["title"], "", "", ["USGS"], 1, ["USGS"])
        body = h.split("</style>", 1)[1]
        self.assertIn('class="sr-share"', body); self.assertIn("Example News", body); self.assertIn('href="https://example.org/a"', body)

    def test_desk_brief_renders_risk_override_capped(self):
        n = dict(NOTE, risk="High", risk_why="Officials say it is contained", rank_why="Two outlets confirm it.", desk=True,
                 edition="BLACKOUT.NETWORK desk brief", if_true="T.", if_false="F.", what_to_do="Stay alert.")
        SR = load({"notes": {CID: n}})
        h, _ = SR.render(CID, CL, [ROW(1)], 5, "Significant", CL["title"], "", "", ["USGS"], 1, ["USGS"])
        body = h.split("</style>", 1)[1]
        self.assertIn("Our analysts rate this medium: Officials say it is contained", body)   # High capped to the rank-5 band
        self.assertIn("Our read:</b> Two outlets confirm it.", body); self.assertIn("Stay alert.", body)
        SR = load({"notes": {CID: dict(n, risk="Low", what_to_do="No action is needed.")}})
        h, _ = SR.render(CID, CL, [ROW(1)], 5, "Significant", CL["title"], "", "", ["USGS"], 1, ["USGS"])
        body = h.split("</style>", 1)[1]
        self.assertIn("<li>No action is needed.</li>", body); self.assertNotIn("Fuel prices", body); self.assertNotIn("Drop, Cover", body)

    def test_quotes_are_cleaned(self):
        SR = load({})
        self.assertEqual(SR._q("Kenya starts countdown https://t.co/x #Ebola #Kenya"), "Kenya starts countdown")
        self.assertEqual(SR._q("Uphold delays protos.com/ripple-linke..."), "Uphold delays")
        self.assertTrue(SR._is_social({"source": "Google News: Facebook", "family": "news"}))
        self.assertEqual(SR._q("BREAKING NEWS What Happened RIYADH — Saudi air defense intercepts missiles"), "RIYADH — Saudi air defense intercepts missiles")
        self.assertTrue(SR._BANNED.search("happy anniversary to the coup"))
        self.assertEqual(SR._sname("Google News: ABC News - Breaking News, Latest News and Videos"), "ABC News")

    def test_every_part_has_no_banned_words(self):
        SR = load({})
        rows = [ROW(i, f) for i, f in enumerate(["USGS", "EMSC", "GDACS"])]
        h, _ = SR.render(CID, CL, rows, 7, "Major", CL["title"], "", "Solomon Islands", ["USGS"], 3, ["EMSC", "GDACS", "USGS"])
        body = h.split("</style>", 1)[1]
        for w in ("verified", "BREAKING", "before the news", "first to"): self.assertNotIn(w, body)

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
        self.assertEqual(n[CID]["what_to_do"], "Fill your tank."); self.assertNotIn("guide", n[CID])   # v2: prep tip feeds "What you should do"
        self.assertEqual(n[CID]["trajectory"], "Rising"); self.assertEqual(n[CID]["edition"], "Nov 11 evening brief")

    def test_note_alias_is_strict(self):
        import build as B
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        notes = {"aaaaaaaaaaaaaaaa": {"headline": "Kenya begins Ebola-free countdown as Congo outbreak tops 11,000 cases", "generated_at": now},
                 "bbbbbbbbbbbbbbbb": {"headline": "Iran refuses to send enriched uranium abroad", "generated_at": now}}
        home = {"cccccccccccccccc": {"title": "Kenya begins Ebola-free countdown as DR Congo tops 11,000 cases", "rank": 7},
                "dddddddddddddddd": {"title": "Trump announcement live: nuclear attack on Iran?", "rank": 6}}
        self.assertEqual(B.note_alias(notes, home), {"cccccccccccccccc": "aaaaaaaaaaaaaaaa"})
        old = {"aaaaaaaaaaaaaaaa": dict(notes["aaaaaaaaaaaaaaaa"], generated_at="2026-01-01T00:00:00+00:00")}
        self.assertEqual(B.note_alias(old, home), {})

    def test_share_filters(self):
        import build as B
        for u in ("https://www.iranintl.com/images/ii/og-fallback.jpg", "https://www.aljazeera.com/wp-content/uploads/2026/11/afp_6af50c4ce48a.jpg",
                  "https://www.gov.uk/assets/frontend/govuk-opengraph-image.png", "https://i.ytimg.com/vi/x/maxresdefault.jpg"):
            self.assertTrue(B.AGENCY_IMG.search(u) or B.BAD_IMG.search(u), u)

    def test_desk_briefs_load_and_filter(self):
        import build as B
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        it = {"headline": "H.", "what_happened": "W happened.", "why_it_matters": "Y.", "analysis": "A. This was verified by us.", "rank_why": "R.",
              "risk": "Low", "risk_why": "Contained.", "if_true": "T.", "if_false": "F.", "what_to_do": "Nothing.", "confidence": "High",
              "confidence_why": "C.", "sources": ["https://example.org/x"], "written_at": now.isoformat()}
        d = tempfile.mkdtemp(); p = os.path.join(d, "briefs.json")
        json.dump({"briefs": {CID: it, "1111111111111111": dict(it, sources=[]), "2222222222222222": dict(it, written_at=(now - timedelta(days=30)).isoformat()),
                              "not-an-id": it}}, open(p, "w"))
        n = B.load_desk_briefs(p, 21)
        self.assertEqual(list(n), [CID]); self.assertTrue(n[CID]["desk"]); self.assertEqual(n[CID]["risk"], "Low")
        self.assertEqual(n[CID]["analysis"], "A."); self.assertEqual(n[CID]["sources"][0]["domain"], "example.org")
        self.assertEqual(n[CID]["edition"], "BLACKOUT.NETWORK desk brief")

    def test_queue_lists_missing_and_stale_briefs(self):
        import build as B, types
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        d = tempfile.mkdtemp(); q = os.path.join(d, "needs_brief.json")
        a = types.SimpleNamespace(queue=q, queue_rank=5, site="https://blackout.network")
        home = {"aaaaaaaaaaaaaaaa": {"title": "No brief", "rank": 6}, "bbbbbbbbbbbbbbbb": {"title": "Stale", "rank": 7},
                "cccccccccccccccc": {"title": "Fresh", "rank": 5}, "dddddddddddddddd": {"title": "Low rank", "rank": 4}}
        notes = {"bbbbbbbbbbbbbbbb": {"generated_at": (now - timedelta(hours=30)).isoformat(), "desk": True},
                 "cccccccccccccccc": {"generated_at": (now - timedelta(hours=2)).isoformat(), "desk": True}}
        old = B.wire_latest
        B.wire_latest = lambda net, site, cid: (now - timedelta(hours=1)).isoformat()
        try: B.write_queue(a, None, notes, {}, home)
        finally: B.wire_latest = old
        out = json.load(open(q))
        self.assertEqual(out["count"], 2)
        self.assertEqual({i["cluster_id"]: i["reason"] for i in out["items"]},
                         {"aaaaaaaaaaaaaaaa": "no brief", "bbbbbbbbbbbbbbbb": "brief over 24 h old, new reports since"})

if __name__ == "__main__":
    unittest.main()
