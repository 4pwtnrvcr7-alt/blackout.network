"""Brief hold (Matt, Nov 12): a newsletter story card goes out only when its /wire/<id> page shows a full brief.
No network, no email sent. Run: cd app && python3 -m unittest tests.test_newsletter_brief_hold -v
"""
import json, os, socket, sys, tempfile, unittest
TMP = tempfile.mkdtemp(prefix="nlhold_")
for k, v in {"NEWSLETTER_DB": "nl.db", "NEWSLETTER_SRC_DB": "src.db", "NEWSLETTER_CONFIG": "nl_config.json",
             "NEWSLETTER_OUTBOX": "outbox", "NEWSLETTER_ENV": "creds/newsletter.env", "NEWSLETTER_PASSFILE": "PASS.txt",
             "NEWSLETTER_LOG": "nl.log", "NEWSLETTER_BO_CONFIG": "bo.json"}.items():
    os.environ[k] = os.path.join(TMP, v)
os.environ["NEWSLETTER_NO_WORKER"] = "1"
os.makedirs(os.path.join(TMP, "creds"), exist_ok=True)
open(os.path.join(TMP, "PASS.txt"), "w").write("x\n")
open(os.path.join(TMP, "bo.json"), "w").write("{}")
open(os.path.join(TMP, "nl_config.json"), "w").write(json.dumps({"live_sending_approved": False, "base_url": "https://blackout.network"}))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _blocked(*a, **k): raise RuntimeError("network access attempted during tests")
socket.socket.connect = _blocked
socket.create_connection = _blocked
import newsletter as NL
import story_report as SR

A, B, C, D, H = "a" * 16, "b" * 16, "c" * 16, "d" * 16, "e" * 16
NOTE = {"what_happened": "Officials said X happened on Thursday.", "headline": "X happened", "sources": [{"url": "https://example.org/x"}]}

def card(cid, sec="main"): return {"cluster_id": cid, "title": f"story {cid[:2]}", "section": sec, "rank": 6, "category": "other"}

class BriefHoldTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(TMP, "story_reports.json")
        self._old = SR.REPORTS; SR.REPORTS = self.path; SR._RC.update(mt=None, v={})
    def tearDown(self):
        SR.REPORTS = self._old; SR._RC.update(mt=None, v={})
        if os.path.exists(self.path): os.remove(self.path)
    def write(self, d):
        with open(self.path, "w") as f: json.dump(d, f)
        SR._RC.update(mt=None, v={})
    def issue(self):
        return {"main": [card(A), card(B)], "politics": [card(C, "politics")], "notable": [card(D, "notable")], "watchlist": [card(H, "watchlist")],
                "near": [], "updates": [], "follow": [], "developing": [],
                "analysis": {"items": [{"cluster_id": A}, {"cluster_id": B}, {"cluster_id": C}, {"cluster_id": D}]}}

    def test_holds_cards_without_a_brief(self):
        self.write({"notes": {A: NOTE, "f" * 16: NOTE}, "alias": {D: "f" * 16}})
        iss = self.issue(); held = NL._hold_unbriefed(iss, dict(NL.DEFAULTS))
        self.assertEqual([x["cluster_id"] for x in iss["main"]], [A])          # B has no brief
        self.assertEqual(iss["politics"], [])                                 # C has no brief
        self.assertEqual([x["cluster_id"] for x in iss["notable"]], [D])      # D is briefed through its alias
        self.assertEqual(iss["watchlist"], [])
        self.assertEqual({cid for _, cid, _ in held}, {B, C, H})
        self.assertEqual({x["cluster_id"] for x in iss["analysis"]["items"]}, {A, D})
        self.assertFalse(iss["quiet"])
        self.assertIs(iss["held"], held)

    def test_note_without_what_happened_is_not_a_brief(self):
        self.write({"notes": {A: {"headline": "only a headline"}, B: NOTE, C: NOTE, D: NOTE, H: NOTE}})
        iss = self.issue(); NL._hold_unbriefed(iss, dict(NL.DEFAULTS))
        self.assertEqual([x["cluster_id"] for x in iss["main"]], [B])

    def test_desk_hold_list(self):
        self.write({"notes": {A: NOTE, B: NOTE, C: NOTE, D: NOTE, H: NOTE}, "newsletter_hold": [C]})
        iss = self.issue(); held = NL._hold_unbriefed(iss, dict(NL.DEFAULTS))
        self.assertEqual(held, [("politics", C, "desk hold list")])

    def test_everything_held_makes_a_quiet_issue(self):
        self.write({"notes": {}})
        iss = self.issue(); NL._hold_unbriefed(iss, dict(NL.DEFAULTS))
        self.assertTrue(all(not iss[s] for s in NL._HOLD_SECTIONS))
        self.assertTrue(iss["quiet"])

    def test_missing_file_fails_open(self):
        iss = self.issue(); held = NL._hold_unbriefed(iss, dict(NL.DEFAULTS))
        self.assertEqual(held, []); self.assertEqual(len(iss["main"]), 2)

    def test_config_off(self):
        self.write({"notes": {}})
        c = dict(NL.DEFAULTS, require_story_brief=False)
        iss = self.issue(); self.assertEqual(NL._hold_unbriefed(iss, c), []); self.assertEqual(len(iss["main"]), 2)

    def test_default_is_on(self):
        self.assertTrue(NL.DEFAULTS["require_story_brief"])

if __name__ == "__main__":
    unittest.main()
