"""Desk stories (t1330u): the FEMA/FCC nationwide EAS test page at /wire/<id> and its homepage featured notice.
Run: cd app && python3 -m unittest tests.test_desk_stories -v
"""
import json, os, re, sqlite3, sys, tempfile, unittest, importlib
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import desk_stories as DS

CID = "ed747e9064795131"
IN = DS._ts("2026-11-15T12:00:00Z"); BEFORE = DS._ts("2026-11-12T12:00:00Z"); AFTER = DS._ts("2026-11-18T06:00:00Z")
WORDS = re.compile(r"\b(?:un)?verified\b|\bverif(?:y|ies|ying)\b|\bbreaking\b|\bfirst to\b|before the news|anniversar|today in history|"
                   r"meshtastic|\blora\b|\bmatt\b|johnston", re.I)

def all_text(o):
    if isinstance(o, str): return [o]
    if isinstance(o, dict): return [t for v in o.values() for t in all_text(v)]
    if isinstance(o, list): return [t for v in o for t in all_text(v)]
    return []

class Data(unittest.TestCase):
    def setUp(self):
        self.s = DS.get(CID)

    def test_entry_loads_with_rank_and_reports(self):
        self.assertIsNotNone(self.s)
        self.assertEqual(self.s["rank"], 2)                       # what unchanged scanner scoring gives four official reports
        r, rows = DS.cluster(CID)
        self.assertTrue(r["desk_story"]); self.assertEqual(r["rank"], 2); self.assertEqual(r["watchlist"], 0)
        self.assertGreaterEqual(len(rows), 3); self.assertTrue(all(a["official"] for a in rows))
        self.assertEqual([a["first_seen"] for a in rows], sorted(a["first_seen"] for a in rows))

    def test_brief_has_all_seven_parts_and_sources(self):
        b = self.s["brief"]
        for k in ("headline", "why_it_matters", "what_happened", "analysis", "rank_why", "risk", "risk_why", "if_true", "if_false",
                  "what_to_do", "confidence", "confidence_why", "sources", "written_at"):
            self.assertTrue(b.get(k), k)
        self.assertEqual(b["risk"], "Low"); self.assertTrue(b["what_to_do"].startswith("No action is needed."))
        self.assertLessEqual(len(b["headline"]), 115)
        self.assertTrue(2 <= len(b["sources"]) <= 6 and all(u.startswith("https://") for u in b["sources"]))
        n = DS.note(CID)
        self.assertEqual(n["what_happened"], b["what_happened"])     # nothing dropped by the word rules
        self.assertEqual(n["analysis"], b["analysis"]); self.assertTrue(n["desk"])

    def test_word_rules_and_privacy(self):
        for t in all_text(self.s):
            self.assertIsNone(WORDS.search(t), t[:120])

    def test_analysis_is_labeled_and_fortress_is_handled_honestly(self):
        an = [x for x in self.s["sections"] if x.get("label")]
        self.assertEqual(len(an), 1); self.assertEqual(an[0]["label"], "Our analysis")
        txt = " ".join(all_text(an[0]))
        self.assertIn("found no official program called \u201cFortress Protocol\u201d", txt)
        self.assertIn("FORTRESS America", txt); self.assertIn("Not supported", txt)
        facts = " ".join(t for x in self.s["sections"] if not x.get("label") for t in all_text(x))
        self.assertNotIn("FORTRESS", facts)                           # kept out of the sourced-facts sections

    def test_every_link_is_https_or_site_path(self):
        for t in all_text(self.s["sections"]):
            for u in re.findall(r"\]\(([^)]*)\)", t):
                self.assertRegex(u, r"^(https://|/wire/[0-9a-f]{16}$)")

class Inline(unittest.TestCase):
    def test_escapes_and_rejects_bad_urls(self):
        h = DS.inline('<b>x</b> [ok](https://a.gov/x) [bad](javascript:alert(1)) [in](/wire/2cb682f7fe34d1ff)')
        self.assertIn("&lt;b&gt;", h); self.assertIn('<a href="https://a.gov/x" target="_blank" rel="noopener">ok</a>', h)
        self.assertNotIn('href="javascript', h); self.assertIn('<a href="/wire/2cb682f7fe34d1ff">in</a>', h)

class Notice(unittest.TestCase):
    def test_window(self):
        self.assertEqual(DS.notice_html(BEFORE), ""); self.assertEqual(DS.notice_html(AFTER), "")
        h = DS.notice_html(IN)
        self.assertIn(f'href="/wire/{CID}"', h); self.assertNotIn(f"/wire/{CID}#", h)
        self.assertIn("Nov. 17, 2:20 PM ET", h); self.assertIn("Rank 2/10", h); self.assertNotIn("#ff3b3b", h)

    def test_board_no_longer_carries_the_notice_block(self):
        # Nov 13 (Matt): the notice moved into the top row as card 2, so the block under the first group is off by default.
        import apple_v1 as A
        real = DS.notice_html
        try:
            DS.notice_html = lambda now=None: real(IN)
            os.environ.pop("BN_DESK_NOTICE_BLOCK", None)
            h = A._board_html()
            self.assertNotIn("bna-notice", h); self.assertTrue(h.endswith("</section>")); self.assertEqual(h.count("<section"), 1)
            os.environ["BN_DESK_NOTICE_BLOCK"] = "1"          # opt-in restores the old block under the first group
            h = A._board_html()
            g = [m.start() for m in re.finditer(r'class="bna-wrap bna-grp"', h)]; n = h.find('class="bna-wrap bna-notice"')
            self.assertGreater(len(g), 1); self.assertTrue(g[0] < n < g[1])
        finally:
            DS.notice_html = real; os.environ.pop("BN_DESK_NOTICE_BLOCK", None)

    def test_feature_card_window_and_link(self):
        self.assertIsNone(DS.feature_card(BEFORE)); self.assertIsNone(DS.feature_card(AFTER))
        f = DS.feature_card(IN)
        self.assertEqual(f["cluster_id"], CID); self.assertEqual(f["href"], f"/wire/{CID}"); self.assertNotIn("#", f["href"])
        self.assertEqual(f["rank"], 2); self.assertIn("Nov. 17, 2:20 PM ET", f["title"]); self.assertEqual(f["show_until"], "2026-11-18T05:00:00Z")
        self.assertFalse(WORDS.search(" ".join(all_text(f))))

    def test_feature_card_kill_switch(self):
        os.environ["BN_DESK_STORIES"] = "0"
        try: self.assertIsNone(DS.feature_card(IN))
        finally: os.environ.pop("BN_DESK_STORIES", None)

    def test_bad_file_fails_closed(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, "x.json"); open(p, "w").write("{not json")
        old = DS.PATH; DS.PATH = p; DS._C["mt"] = None
        try:
            self.assertIsNone(DS.get(CID)); self.assertEqual(DS.notice_html(IN), ""); self.assertIsNone(DS.feature_card(IN)); self.assertEqual(DS.cluster(CID), (None, []))
        finally:
            DS.PATH = old; DS._C["mt"] = None

    def test_kill_switch(self):
        os.environ["BN_DESK_STORIES"] = "0"
        try: self.assertIsNone(DS.get(CID)); self.assertEqual(DS.notice_html(IN), "")
        finally: os.environ.pop("BN_DESK_STORIES"); DS._C["mt"] = None

class Page(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(); db = os.path.join(self.td, "blackout.db")
        c = sqlite3.connect(db); c.execute("CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT)"); c.execute("CREATE TABLE alerts(cluster_id TEXT)"); c.commit(); c.close()
        os.environ["BN_STORY_REPORTS"] = os.path.join(self.td, "none.json")
        import story_report; importlib.reload(story_report)
        import story; self.st = importlib.reload(story); self.st.DB = db

    def test_page_renders_brief_breakdown_and_graphic(self):
        code, body = self.st.render(CID); body = body.decode("utf-8") if isinstance(body, bytes) else body
        self.assertEqual(code, 200)
        for s in ("FEMA and the FCC will run a nationwide Emergency Alert System test", "RANK 2/10 · MINOR", "Bottom line", "What happened",
                  "Why it matters", "Why we ranked it this way", "Risk factor", "What you should do", "Sources", "Full breakdown and analysis",
                  "Our analysis", "How the alert travels", "How past nationwide tests went", "Timeline and sources", "docs.fcc.gov", "<svg"):
            self.assertIn(s, body, s)
        self.assertNotIn("Quick brief, built automatically", body)     # never an empty or placeholder brief
        self.assertNotIn('content="noindex', body)
        self.assertNotIn("<img", body.split("Full breakdown")[1].split("Timeline and sources")[0])

    def test_pushed_note_wins_over_fallback(self):
        p = os.environ["BN_STORY_REPORTS"]
        n = DS.note(CID); n["headline"] = "Pushed desk headline for the alert test."
        json.dump({"notes": {CID: n}}, open(p, "w"))
        import story_report; importlib.reload(story_report)
        code, body = self.st.render(CID); body = body.decode("utf-8") if isinstance(body, bytes) else body
        self.assertIn("Pushed desk headline for the alert test", body)

    def test_unknown_id_still_404(self):
        code, _ = self.st.render("0123456789abcdef")
        self.assertEqual(code, 404)

if __name__ == "__main__":
    unittest.main()
