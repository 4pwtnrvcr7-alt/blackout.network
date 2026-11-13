"""Newsletter layout v2 (Matt, Nov 13 2026, t1365u): off by default, behind BN_NL_V2=1. Every story card gets a picture served
from blackout.network with a credit, a short summary, "Read the full brief", "Watch on YouTube" when our video exists, and
headshots with a Profile link for named people. Offline: temp databases, no network, no send, no worker."""
import os, sys, json, sqlite3, tempfile, unittest, io, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
TMP = tempfile.mkdtemp(prefix="nlv2_")
open(os.path.join(TMP, "nl.env"), "w").write("NEWSLETTER_SENDER=preview\n")
SRCU = "https://upload.wikimedia.org/wikipedia/commons/a/aa/Test_quake.jpg"
REPORTS = {"images": {"aaaaaaaaaaaaaaa1": [{"src": SRCU, "w": 1200, "h": 800, "alt": "Damaged street", "caption": "A damaged street, Nov 13, 2026.",
                                             "credit": "U.S. Geological Survey", "license": "Public domain", "link": "https://earthquake.usgs.gov/x", "kind": "photo"}]},
           "people": {"profiles": {"donald-trump": {"slug": "donald-trump", "name": "Donald Trump", "rx": r"\bTrump\b", "role": "President of the United States",
                                                     "portrait": {"author": "The White House", "license": "Public domain", "src": "https://upload.wikimedia.org/x/Trump.jpg"}}},
                      "story_people": {"aaaaaaaaaaaaaaa2": ["donald-trump"]}, "lead": {}, "places": {}, "country_alias": {}},
           "notes": {c: {"what_happened": "Sourced brief text for the test story."} for c in ("aaaaaaaaaaaaaaa1", "aaaaaaaaaaaaaaa2", "aaaaaaaaaaaaaaa3")},
           "shares": {}}
json.dump(REPORTS, open(os.path.join(TMP, "reports.json"), "w"))
LINKSF = os.path.join(TMP, "social_links.json")
json.dump({"stories": {"aaaaaaaaaaaaaaa2": {"policy_ok": True, "yt_ok": True, "yt_url": "https://www.youtube.com/shorts/abcDEF12345", "x_ok": False, "hidden": []}}},
          open(LINKSF, "w"))
os.environ.update({"NEWSLETTER_NO_WORKER": "1", "NEWSLETTER_ENV": os.path.join(TMP, "nl.env"), "NEWSLETTER_DB": os.path.join(TMP, "nl.db"),
                   "NEWSLETTER_SRC_DB": os.path.join(TMP, "src.db"), "NEWSLETTER_OUTBOX": os.path.join(TMP, "outbox"),
                   "NEWSLETTER_CONFIG": os.path.join(TMP, "newsletter_config.json"), "NEWSLETTER_ANALYSIS_JSON": os.path.join(TMP, "none.json"),
                   "NEWSLETTER_PASSFILE": os.path.join(TMP, "pass.txt"), "BN_STORY_REPORTS": os.path.join(TMP, "reports.json")})
os.environ.pop("BN_NL_V2", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import newsletter as N, newsletter_qa as QA, newsletter_v2 as V2, newsletter_img as NI, home_feed as HF
HF.F_LINKS = LINKSF
NI.CACHE = os.path.join(TMP, "imgcache")
UTC = timezone.utc
AT = datetime(2026, 11, 14, 0, 0, tzinfo=UTC)   # Nov 13, 7 PM ET
LINKS = {"unsubscribe": "https://blackout.network/newsletter/unsubscribe?token=x", "manage": "https://blackout.network/newsletter",
         "categories": "https://blackout.network/newsletter", "sources": "https://blackout.network/sources",
         "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
STORIES = [("aaaaaaaaaaaaaaa1", "Magnitude 7.4 earthquake strikes near Hualien, Taiwan, damaging buildings", "natural disaster", "Hualien, Taiwan", 8),
           ("aaaaaaaaaaaaaaa2", "Trump orders new sanctions on Iran's oil exports after tanker seizure in the Gulf", "political", "Washington", 7),
           ("aaaaaaaaaaaaaaa3", "Ransomware attack shuts down hospital systems across three US states", "cyber", "Not specified", 7)]

def _src():
    k = sqlite3.connect(N.P["src"])
    k.executescript("""CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT, event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT, first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE TABLE IF NOT EXISTS clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER, eff_families INTEGER, rank INTEGER, pushed_at TEXT);
    CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, started TEXT, finished TEXT, trigger TEXT, fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);""")
    t = (AT - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for cid, title, cat, loc, rk in STORIES:
        fams = ["Reuters", "AP", "BBC"]
        k.execute("INSERT OR REPLACE INTO clusters(cluster_id,title,category,location,event_time,first_seen,updated,score,confidence,n_items,n_families,families,links,watchlist,brief,eff_families,rank,high_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, title, cat, loc, t, t, t, rk * 10, "high", 6, 3, json.dumps(fams), json.dumps([]), 0, title + ".", 3, rk, t))
        for i, f in enumerate(fams):
            k.execute("INSERT OR REPLACE INTO alerts(id,source,family,title,category,source_url,event_time,location,base,official,first_seen,last_seen,cluster_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (f"{cid}-{i}", f, f, title, cat, f"https://example.org/{cid}/{i}", t, loc, 5, 1 if i == 0 else 0, t, t, cid))
    k.commit(); k.close()

def _issue():
    return N.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=AT, since=AT - timedelta(hours=12), slot="evening")

class V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): _src()

    def tearDown(self): os.environ.pop("BN_NL_V2", None)

    def test_off_by_default_keeps_v1(self):
        subj, html, text = N.render(_issue(), LINKS)
        self.assertNotIn("TOP 3 RIGHT NOW", html)
        self.assertNotIn("/newsletter/img/", html)

    def test_v2_cards_images_buttons_people_and_gate(self):
        os.environ["BN_NL_V2"] = "1"
        issue = _issue()
        shown = [it for sec in ("near", "follow", "main", "politics", "updates", "notable") for it in issue.get(sec) or []]
        self.assertEqual(len(shown), 3, {k: len(v) for k, v in issue.items() if isinstance(v, list)})
        subj, html, text = N.render(issue, LINKS)
        self.assertIn("TOP 3 RIGHT NOW", html)
        # one picture per story card, all absolute https on blackout.network, never data:, WebP or SVG
        imgs = re.findall(r'<img src="([^"]+)"', html)
        self.assertTrue(all(u.startswith("https://blackout.network/") for u in imgs), imgs)
        self.assertFalse(any(u.startswith("data:") or u.endswith((".webp", ".svg")) for u in imgs))
        for cid, *_ in STORIES:
            self.assertIn(f"/wire/{cid}", html)
        self.assertIn("/newsletter/img/lead/", html)                       # rights-cleared photo, through the same-origin copy
        self.assertIn("Image: U.S. Geological Survey, Public domain", html)  # its credit
        self.assertIn("/newsletter/img/card/aaaaaaaaaaaaaaa3.png", html)  # no photo: our own data graphic, labelled
        self.assertIn("Graphic: BLACKOUT.NETWORK", html)
        self.assertEqual(html.count("Read the full brief"), len(shown) + len(issue.get("featured") or []))
        self.assertIn("https://www.youtube.com/shorts/abcDEF12345", html)
        self.assertEqual(html.count("Watch on YouTube"), 1)
        self.assertIn("https://blackout.network/people/donald-trump", html)
        self.assertIn("/newsletter/img/person/donald-trump.jpg", html)
        self.assertNotIn("Not specified", html)
        for u in re.findall(r'href="([^"]+/wire/[^"]+)"', html): self.assertNotIn("#", u)   # story links open at the top
        # brand, compliance footer, wording
        self.assertIn("BLACKOUT.NETWORK", html); self.assertIn(N.TAGLINE, html)
        self.assertIn("newsletter/unsubscribe?token=x", html); self.assertIn("Unsubscribe", html)
        vis = re.sub(r"<[^>]+>", " ", html)
        self.assertNotRegex(vis, r"(?i)\bverified\b|meshtastic|\blora\b")
        qa = QA.check(subj, html, text, QA.sources_from_issue(issue), QA.titles_from_issue(issue))
        self.assertTrue(qa["ok"], qa["blockers"])
        self.assertIn("Read the full brief: https://blackout.network/wire/aaaaaaaaaaaaaaa1", text)
        self.assertIn("Unsubscribe (one click)", text)

    def test_v2_failure_falls_back_to_v1(self):
        os.environ["BN_NL_V2"] = "1"
        orig = V2.render
        V2.render = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            subj, html, text = N.render(_issue(), LINKS)
        finally:
            V2.render = orig
        self.assertNotIn("TOP 3 RIGHT NOW", html)
        self.assertIn("/wire/aaaaaaaaaaaaaaa1", html)

    def test_place_only_when_headline_names_it(self):
        it = {"title": "A colonel is killed by a car bomb in St. Petersburg", "where": "Ukraine"}
        self.assertFalse(V2._place_named("Ukraine", it))
        self.assertTrue(V2._place_named("Hualien, Taiwan", {"title": STORIES[0][1]}))

    def test_card_graphic_and_routes(self):
        st, body, ct = NI.handle_get("/newsletter/img/card/aaaaaaaaaaaaaaa1.png")
        self.assertEqual((st, ct), (200, "image/png"))
        from PIL import Image
        im = Image.open(io.BytesIO(body)); self.assertEqual(im.size, (1200, 675)); self.assertFalse(im.info.get("exif"))
        self.assertEqual(NI.handle_get("/newsletter/img/card/ffffffffffffffff.png")[0], 404)        # unknown story
        self.assertEqual(NI.handle_get("/newsletter/img/lead/0123456789abcdef0123.jpg")[0], 404)   # not in the signed allowlist
        self.assertEqual(NI.handle_get("/newsletter/img/../../etc/passwd")[0], 404)
        st, body, ct = NI.handle_get("/newsletter/img/person/donald-trump.jpg")
        self.assertEqual((st, ct), (200, "image/jpeg"))
        self.assertEqual(Image.open(io.BytesIO(body)).size, (160, 160))

    def test_image_route_never_starts_worker(self):
        calls = []
        orig = N.ensure_worker; N.ensure_worker = lambda *a, **k: calls.append(1)
        try: N.handle_get("/newsletter/img/card/aaaaaaaaaaaaaaa1.png", {})
        finally: N.ensure_worker = orig
        self.assertEqual(calls, [])

    def test_v2_quiet_issue_keeps_matters_line_and_invents_nothing(self):
        os.environ["BN_NL_V2"] = "1"
        issue = _issue()
        for sec in ("near", "follow", "main", "politics", "updates", "notable", "developing", "watchlist", "featured", "videos"):
            issue[sec] = []
        issue["quiet"] = True
        subj, html, text = N.render(issue, LINKS)
        self.assertIn("Here's what matters right now", html)
        self.assertIn("Here's what matters right now", text)
        for bad in ("no confirmed high-severity", "nothing to report", "all quiet", "nothing new to report"):
            self.assertNotIn(bad, html.lower()); self.assertNotIn(bad, text.lower())
        self.assertIn("Unsubscribe", html)

    def test_v2_links_open_at_top(self):
        os.environ["BN_NL_V2"] = "1"
        links = dict(LINKS); links.pop("sources")          # the shared footer falls back to site (/#wire)
        subj, html, text = N.render(_issue(), links)
        hrefs = re.findall(r'href="([^"]+)"', html)
        self.assertTrue(hrefs)
        self.assertEqual([h for h in hrefs if "#" in h], [])
        self.assertNotIn("#wire", text)
        self.assertIn("Find new sources", html)

if __name__ == "__main__":
    unittest.main()
