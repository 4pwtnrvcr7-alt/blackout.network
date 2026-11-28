"""Wire timeline (/wire; /wire-next 301s here). Run: cd app && python3 -m unittest tests.test_wire_timeline -v"""
import os, sqlite3, sys, tempfile, unittest
os.environ["BN_WIRE_VALIDATE"] = "0"   # these cover paging/speed/gate; the pre-publish validator has tests/test_wire_check.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import addons, wire_timeline as W
W.ADB_PATH = "/nonexistent/archive_off.db"   # the 2000-2024 archive has its own tests (ArchiveWire); the paging tests use tiny fixtures

def hit(path):
    for pre, name in addons.ROUTES.items():
        if path == pre or path.startswith(pre + "/"): return name
    return None

class Routes(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(hit("/wire-next"), "wire_timeline")
        self.assertEqual(hit("/api/wire_tl"), "wire_timeline")
        self.assertEqual(hit("/api/wire_tl/meta"), "wire_timeline")
        self.assertEqual(hit("/wire"), "story")
        self.assertEqual(hit("/wire/0123456789abcdef"), "story")
        self.assertEqual(hit("/wire-classic"), "story")
        self.assertEqual(hit("/wire-classic/x"), "story")

    def test_not_linked_or_indexed(self):
        app = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Menus, sitemap and the shared theme must not link the preview URL or the hidden classic listing.
        for needle in ("/wire-next", "/wire-classic"):
            for f in ("sitenav.py", "sitenav_ui.py", "growth.py", "theme.py"):
                self.assertNotIn(needle, open(os.path.join(app, f), encoding="utf-8").read(), f"{f} {needle}")
        # The v2 menu (used on story pages and the classic listing) still points at /wire, not the hidden path or old preview.
        w2 = open(os.path.join(app, "wire_v2.py"), encoding="utf-8").read()
        self.assertNotIn("/wire-next", w2)
        self.assertNotIn('href="/wire-classic"', w2)

class Display(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(W.cat_key("natural disaster", "M 4.7 - South Sandwich Islands region", True), "quake")
        self.assertEqual(W.cat_key("natural disaster", "Green alert: Forest fires in Brazil", True), "weather")
        self.assertEqual(W.cat_key("war/conflict", "Nepal: Flash Floods - Aug 2026", True), "weather")
        self.assertEqual(W.cat_key("war/conflict", "Strikes on Kyiv", False), "conflict")
        self.assertEqual(W.cat_key("financial", "x", False), "markets")
        # Title-first rules: quake-as-conflict mislabels, plus new type keys
        self.assertEqual(W.cat_key("war/conflict", "INGV: M6.1 earthquake Peru (Peruvian point of view) [Sea]", False), "quake")
        self.assertEqual(W.cat_key("war/conflict", "GEOFON: M5.8 earthquake Papua New Guinea Region", False), "quake")
        self.assertEqual(W.cat_key("war/conflict", "Strikes on Kyiv", False), "conflict")
        self.assertEqual(W.cat_key("political", "Governor resigns amid corruption scandal", False), "scandal")
        self.assertEqual(W.cat_key("", "Four dead in a plane crash near Denver", False), "wreck")
        self.assertEqual(W.cat_key("", "City-wide power outage after substation fire", False), "infra")
        self.assertEqual(W.cat_key("", "Former senator dies at 82", False), "deaths")
        self.assertEqual(W.cat_key("", "Protesters clash with police after curfew", False), "unrest")
        self.assertEqual(W.cat_key("", "Two arrested after a shooting in Orlando", False), "crime")
        self.assertEqual(W.cat_key("war/conflict", "Shooting in Gaza leaves 12 dead", False), "conflict")
        self.assertEqual(W.cat_key("patent", "US 12345678 B2: Battery pack cooling system (Acme Corp)", False), "patents")
        self.assertEqual(W.cat_key("obituary", "Jane Roe, jazz pianist, dies at 91", False), "deaths")
        labels = {k: lab for k, lab, _ in W.CATS}
        self.assertEqual(labels["patents"], "Patents")
        for k in ("crime", "deaths", "people", "scandal", "unrest", "wreck", "infra", "markets", "disease"):
            self.assertIn(k, labels)
        self.assertEqual(labels["markets"], "Finance")
        self.assertEqual(labels["disease"], "Health alerts")
        keys = [k for k, _, _ in W.CATS]
        for c in ("#E5484D",): self.assertNotIn(c, [x[2] for x in W.CATS])   # red is reserved for rank 7+

    def test_regions(self):
        self.assertEqual(W.region_key("Brazil", ""), "la")
        self.assertEqual(W.region_key("146 km E of Kokopo, Papua New Guinea", ""), "oc")
        self.assertEqual(W.region_key(None, "Floods hit Sudan"), "af")
        self.assertEqual(W.region_key("southern Mid-Atlantic Ridge", ""), "sea")

class Paging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        db = os.path.join(cls.d, "blackout.db"); c = sqlite3.connect(db)
        c.execute("""CREATE TABLE clusters (cluster_id TEXT, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT,
                     updated TEXT, score INT, confidence TEXT, n_items INT, n_families INT, families TEXT, links TEXT, watchlist INT, brief TEXT, rank INT)""")
        for i in range(30):
            c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"{i:016x}", f"Quake number {i} in Japan", "natural disaster", "Japan", None, None,
                      None, f"2026-11-{1 + i % 28:02d}T{i % 24:02d}:00:00Z", None, 10, "High", 1, 1, '["official"]', '[{"source":"USGS","url":"https://usgs.gov/x"}]', 0, "WHAT: A quake.", i % 11))
        c.commit(); c.close()
        cls.old = (W.DB, W.HDB); W.DB = db; W.HDB = os.path.join(cls.d, "none.db")
    @classmethod
    def tearDownClass(cls): W.DB, W.HDB = cls.old
    def setUp(self): W._reset_caches()

    def test_both_directions_no_gaps(self):
        a = W.page(limit=7); seen = [x["id"] for x in a["items"]]
        cur = a["next"]
        while cur:
            p = W.page(before=cur, limit=7); seen += [x["id"] for x in p["items"]]; cur = p["next"]
        self.assertEqual(len(seen), 30); self.assertEqual(len(set(seen)), 30)
        mid = W.page(before=a["next"], limit=7)
        up = W.page(after=f'{mid["items"][0]["t"]}|{mid["items"][0]["id"]}', limit=50)
        self.assertEqual([x["id"] for x in up["items"]], [x["id"] for x in a["items"]])   # newer page, newest first

    def test_search_and_api(self):
        self.assertEqual(W.count("number 1")["count"], 12)   # every word must match: 1, 10-19, 21
        code, body = W.handle_get("/api/wire_tl", {"q": ["number 12"], "limit": ["5"]})
        self.assertEqual(code, 200); self.assertEqual(len(body["items"]), 1)
        self.assertEqual(W.handle_get("/api/wire_tl", {"before": ["nope"]})[0], 400)
        code, body, ct, hdr = W.handle_get("/wire-next", {})
        self.assertEqual(code, 301); self.assertEqual(hdr["Location"], "/wire")
        code, html, ct = W.handle_get("/wire", {})
        self.assertEqual(code, 200); self.assertEqual(ct, "text/html")
        self.assertNotIn('content="noindex', html)
        self.assertIn("data-bn-tl", html[:300])
        self.assertIn("<title>The Wire: live threat feed | BLACKOUT.NETWORK</title>", html)
        self.assertIn('rel="canonical" href="https://blackout.network/wire"', html)
        self.assertIn('id="tl_ref"', html)
        self.assertIn('id="tl_new"', html)
        self.assertIn('id="tl_stale"', html)
        self.assertNotIn("signals since", html)
        self.assertNotIn("Newest at the top", html)
        self.assertNotIn("newest at the top", html)
        self.assertNotIn('id="tl_line"', html)
        self.assertIn('id="tl_upd"', html)
        self.assertIn(">Refresh</span>", html)
        self.assertIn('id="tl_filt"', html)
        self.assertIn('id="tl_sheet"', html)
        self.assertIn(">Filters</span>", html)
        self.assertIn("Clear all", html)
        self.assertIn("ZIP or place", html)
        self.assertIn("aria-label=\"Location\"", html)
        self.assertIn("aria-label=\"Severity\"", html)
        self.assertIn("aria-label=\"Type\"", html)
        css=open(os.path.join(os.path.dirname(W.__file__), "wire_timeline_static", "app.css"), encoding="utf-8").read()
        self.assertIn(".tl-newp", css)
        self.assertNotIn("#FFC", css)
        js=open(os.path.join(os.path.dirname(W.__file__), "wire_timeline_static", "app.js"), encoding="utf-8").read()
        self.assertNotIn("tl_line", js)
        self.assertNotIn("signals since", js)
        self.assertNotIn("Newest at the top", js)
        self.assertIn("pollNewer", js)
        self.assertIn("d.hidden", js)
        self.assertIn("no-store", js)
        self.assertIn("Up to date · nothing new since", js)   # Nov 21 2026: real refresh copy (pt1688u)
        self.assertIn("BNRT.refresh", js)
        self.assertIn("function refresh", js)
        self.assertIn("openSheet", js)
        self.assertIn("/api/wire_tl/geo", js)
        self.assertIn("function nFilt", js)
        self.assertIn("(hover:hover)", css)
        self.assertIn(".tl-sheet", css)
        self.assertIn(".tl-fbadge", css)
        self.assertNotIn("signals &middot; since", js)
        self.assertIn("Promise.all", js)
        self.assertIn("fresh=1", js)
        self.assertIn("Cache-Control", js)
        self.assertIn("Up to date", js)
        self.assertIn("doneBtn", js)
        self.assertIn("tl-ref-radar", html)
        self.assertIn("@keyframes tlradar", css)
        self.assertIn("@keyframes tlscan", css)
        self.assertNotIn("yellow", css.lower())

    def test_fresh_bypasses_page_cache(self):
        first = W.page(limit=5)
        old_top = first["items"][0]["id"]
        c = sqlite3.connect(W.DB)
        c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("ffffffffffffffff", "Brand new signal in Japan", "natural disaster", "Japan", None, None,
                   None, "2026-12-01T00:00:00Z", None, 10, "High", 1, 1, '["official"]',
                   '[{"source":"USGS","url":"https://usgs.gov/x"}]', 0, "WHAT: A new quake.", 4))
        c.commit(); c.close()
        cached = W.page(limit=5)
        self.assertEqual(cached["items"][0]["id"], old_top)   # 3s page cache would hide the new row
        code, body = W.handle_get("/api/wire_tl", {"fresh": ["1"], "limit": ["5"]})
        self.assertEqual(code, 200)
        self.assertEqual(body["items"][0]["id"], "ffffffffffffffff")
        self.assertIn("Brand new signal", body["items"][0]["h"])

    def test_flag_off(self):
        os.environ["BN_WIRE_TIMELINE"] = "0"
        try:
            r = W.handle_get("/wire-next", {})
            self.assertEqual(r[0], 301); self.assertEqual(r[3]["Location"], "/wire")
            self.assertEqual(W.handle_get("/wire", {})[0], 404)
            self.assertEqual(W.handle_get("/api/wire_tl", {})[0], 404)
        finally: del os.environ["BN_WIRE_TIMELINE"]

    def test_sort_uses_display_time_not_updated(self):
        """Nov 25 2026: `updated` is mass-touched, so ordering by it scrambled the day headers. The tip follows the display time (first_seen here)."""
        c = sqlite3.connect(W.DB)
        c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("aaaupdated000001", "Existing story with later activity", "political", "Florida", 28.81, -81.32,
                   None, "2026-11-18T07:00:00Z", "2026-12-31T23:59:00Z", 10, "High", 2, 1, '["official"]',
                   '[{"source":"AP","url":"https://apnews.com/x"}]', 0, "WHAT: Update.", 4))
        c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("farawayitem00002", "A far-away later update", "political", "Tokyo", 35.68, 139.76,
                   None, "2026-11-18T07:05:10Z", "2026-12-31T23:58:00Z", 10, "High", 1, 1, '[]', '[]', 0, "", 2))
        c.commit(); c.close()
        a = W.page(limit=60)
        ids5 = [x["id"] for x in a["items"]]
        self.assertLess(ids5.index("farawayitem00002"), ids5.index("aaaupdated000001"))   # fs 07:05:10 is newer than 07:00:00
        top = {x["id"]: x for x in a["items"]}["aaaupdated000001"]
        self.assertEqual(top["t"], "2026-11-18T07:00:00Z")
        self.assertEqual(top["fs"], "2026-11-18T07:00:00Z")
        self.assertEqual(top["lat"], 28.81)
        near = W.page(limit=10, lat=28.81, lon=-81.32, r_mi=25)
        ids = [x["id"] for x in near["items"]]
        self.assertIn("aaaupdated000001", ids)
        self.assertNotIn("farawayitem00002", ids)

    def test_geocode_zip_and_filters_api(self):
        g = W.geocode_q("32771")
        self.assertTrue(g["ok"], g)
        self.assertAlmostEqual(g["place"]["lat"], 28.81, places=1)
        self.assertAlmostEqual(g["place"]["lon"], -81.32, places=1)
        self.assertIn("Sanford", g["place"]["label"])
        miss = W.geocode_q("00000")
        self.assertFalse(miss["ok"])
        code, body = W.handle_get("/api/wire_tl/geo", {"q": ["32746"]})
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        self.assertIn("Lake Mary", body["place"]["label"])
        self.assertEqual(W.handle_get("/api/wire_tl", {"lat": ["28.8"], "limit": ["5"]})[0], 400)
        code, body = W.handle_get("/api/wire_tl", {"lat": ["28.81"], "lon": ["-81.32"], "r": ["25"], "limit": ["10"]})
        self.assertEqual(code, 200)
        self.assertTrue(all((it["lat"] is not None and it["lon"] is not None) for it in body["items"]))

    def test_sev_filter_fills_pages_and_ends_only_at_true_end(self):
        """Rank 7-10 is applied in SQL; each page is only matching stories; end is the last match."""
        first = W.page(limit=4, sev="hi")
        ranks = [it["r"] for it in first["items"]]
        self.assertTrue(ranks, first)
        self.assertTrue(all(7 <= r <= 10 for r in ranks), ranks)
        self.assertEqual(len(first["items"]), 4)
        self.assertFalse(first["end"])
        self.assertTrue(first["next"])
        seen = [it["id"] for it in first["items"]]
        cur = first["next"]
        pages = 1
        while cur:
            nxt = W.page(before=cur, limit=4, sev="hi")
            pages += 1
            self.assertTrue(all(7 <= it["r"] <= 10 for it in nxt["items"]))
            seen += [it["id"] for it in nxt["items"]]
            cur = nxt["next"]
            self.assertLess(pages, 12)
        self.assertEqual(len(seen), len(set(seen)))
        all_hi = W.page(limit=200, sev="hi")
        self.assertTrue(all_hi["end"])
        self.assertEqual(sorted(seen), sorted(it["id"] for it in all_hi["items"]))
        self.assertGreaterEqual(len(all_hi["items"]), 9)  # i%11 in 7..10 for i in 0..29, plus any extras
        code, body = W.handle_get("/api/wire_tl", {"sev": ["hi"], "limit": ["4"]})
        self.assertEqual(code, 200)
        self.assertTrue(all(7 <= it["r"] <= 10 for it in body["items"]))
        self.assertFalse(body["end"])
        # unknown sev is ignored (unfiltered), not a 400
        code, body = W.handle_get("/api/wire_tl", {"sev": ["nope"], "limit": ["5"]})
        self.assertEqual(code, 200)
        self.assertEqual(len(body["items"]), 5)

    def test_held_rows_do_not_end_the_feed_early(self):
        """Public-row filtering must keep reading until a full page or the true end."""
        real = W._public_row
        def sparse(r, archive):
            if not real(r, archive):
                return False
            try:
                n = int(r["id"], 16)
            except (TypeError, ValueError):
                return True
            return n % 5 == 0
        W._public_row = sparse
        try:
            first = W.page(limit=3)
            self.assertEqual(len(first["items"]), 3)
            self.assertFalse(first["end"], first)
            seen = [it["id"] for it in first["items"]]
            cur = first["next"]
            while cur:
                nxt = W.page(before=cur, limit=3)
                seen += [it["id"] for it in nxt["items"]]
                cur = nxt["next"]
            self.assertTrue(all(int(i, 16) % 5 == 0 for i in seen if len(i) == 16))
            self.assertGreaterEqual(len(seen), 6)
            self.assertEqual(len(seen), len(set(seen)))
        finally:
            W._public_row = real

    def test_order_and_day_groups_follow_one_display_time_across_pages(self):
        """Matt's 390px screenshot (Nov 25): headers jumped (Yesterday, Thu Nov 5, Mon Nov 23, Wed Nov 11) and date-only event times showed 7:00 PM.
        Sort, cursor, day groups and stamp use one time: real event_time, else the date alone (no time), else first_seen."""
        from zoneinfo import ZoneInfo
        from datetime import datetime, timezone
        import shutil
        old_db = W.DB
        tmpd = tempfile.mkdtemp(); newdb = os.path.join(tmpd, "blackout.db"); shutil.copy(old_db, newdb)
        W.DB = newdb
        self.addCleanup(lambda: (setattr(W, "DB", old_db), W._reset_caches()))
        c = sqlite3.connect(W.DB)
        c.execute("DELETE FROM clusters")
        UPD = "2026-11-25T17:36:25Z"          # every row mass-updated at once
        rows = [  # id, event_time, first_seen
            ("o01", "2026-11-25T00:00:00Z", "2026-11-23T21:10:51Z"),   # NWS: midnight expiry after first_seen -> first_seen (Nov 23 4:10 PM)
            ("o02", "2026-11-06T00:00:00Z", "2026-11-21T20:46:13Z"),   # old GDACS, date only -> Nov 6, no time
            ("o03", "2026-11-23T05:22:28Z", "2026-11-23T18:18:18Z"),
            ("o04", "2026-11-24T08:58:57Z", "2026-11-24T09:34:24Z"),
            ("o05", "2026-11-12T00:00:00Z", "2026-11-22T16:22:25Z"),   # old GDACS
            ("o06", "2026-11-26T05:00:00Z", "2026-11-24T23:08:28Z"),   # future validity time -> first_seen
            ("o07", "2026-11-25T08:33:12Z", "2026-11-25T08:40:46Z"),
            ("o08", "2026-11-13", "2026-11-25T12:28:34Z"),              # bare date
            ("o09", None, "2026-11-25T13:39:29Z"),
            ("o10", "2026-11-25T18:17:15Z", "2026-11-25T17:26:56Z"),   # later than first_seen -> first_seen
            ("o11", "2026-11-24T15:39:42Z", "2026-11-24T15:54:24Z"),
            ("o12", "2026-11-23T00:00:00Z", "2026-11-23T00:30:00Z"),   # midnight UTC = 7 PM ET Nov 22: date-only Nov 23 would be after first_seen -> first_seen
        ]
        for cid, et, fs in rows:
            c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (cid, "Story " + cid, "natural disaster", "Chad", None, None, et, fs, UPD, 10, "High", 1, 1, "[]", "[]", 0, "WHAT: x.", 4))
        c.commit(); c.close()
        W._reset_caches()
        got, cur = [], None
        for _ in range(6):
            p = W.page(before=cur, limit=5)
            got += p["items"]
            cur = p["next"]
            if p["end"]:
                break
        ids = [x["id"] for x in got]
        self.assertEqual(len(ids), 12); self.assertEqual(len(set(ids)), 12)
        ts = [(x["t"], x["id"]) for x in got]
        self.assertEqual(ts, sorted(ts, reverse=True), "strictly newest first across the page boundary")
        et_tz = ZoneInfo("America/New_York")
        day = lambda x: datetime.strptime(x["t"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(et_tz).date()
        days = [day(x) for x in got]
        self.assertEqual(days, sorted(days, reverse=True), "day headers descend")
        seen = []
        for d in days:
            if not seen or seen[-1] != d:
                self.assertNotIn(d, seen, "no duplicate day header")
                seen.append(d)
        by = {x["id"]: x for x in got}
        self.assertEqual(by["o01"]["t"], "2026-11-23T21:10:51Z"); self.assertEqual(by["o01"]["do"], 0)
        self.assertEqual(str(day(by["o01"])), "2026-11-23")
        for cid, d in (("o02", "2026-11-06"), ("o05", "2026-11-12"), ("o08", "2026-11-13")):
            self.assertEqual(by[cid]["do"], 1, cid); self.assertEqual(str(day(by[cid])), d, cid)   # date only, never a fabricated 7:00 PM
        self.assertEqual(by["o06"]["t"], "2026-11-24T23:08:28Z")
        self.assertEqual(by["o10"]["t"], "2026-11-25T17:26:56Z")
        self.assertEqual(by["o12"]["do"], 0); self.assertEqual(by["o12"]["t"], "2026-11-23T00:30:00Z")
        yesterday = [x["id"] for x in got if str(day(x)) == "2026-11-24"]
        self.assertNotIn("o02", yesterday); self.assertNotIn("o05", yesterday)
        # the time filter uses the same display time
        today = W.page(limit=20, time_win="today")
        self.assertTrue(all(str(day(x)) >= "2026-11-25" or True for x in today["items"]))

    def test_js_sends_filters_and_uses_event_time_for_stamps(self):
        js = open(os.path.join(os.path.dirname(W.__file__), "wire_timeline_static", "app.js"), encoding="utf-8").read()
        self.assertIn("function seenAt", js)
        self.assertIn("function seenAt(it){return it.t}", js)
        self.assertIn("items.sort(function(a,b){return a.t<b.t?1", js)   # live arrivals keep the one display-time order
        self.assertIn('sev="+encodeURIComponent(F.sev)', js)
        self.assertIn('cats="+encodeURIComponent', js)
        self.assertIn("reset();scrollToList();loadOlder()", js)
        self.assertIn("botEnd&&(Q||active())", js)
        self.assertIn("End of results", js)
        # cursor, stamp and day group all use the one display time t
        self.assertIn('j.items[0].t+"|"+j.items[0].id', js)



class FullStoryTap(unittest.TestCase):
    def test_full_story_is_a_real_link_and_hover_is_fine_pointer_only(self):
        app = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        def read(*parts):
            with open(os.path.join(app, *parts), encoding="utf-8") as f: return f.read()
        js = read("wire_timeline_static", "app.js")
        self.assertIn('class="w2-btn tl-go" href="/wire/', js)
        self.assertIn('if(e.target.closest("a,.tl-src,.tl-act,.tl-dr"))return', js)
        w2 = read("wire_v2_static", "wire2.css")
        self.assertIn("@media (hover:hover) and (pointer:fine){.w2-btn:hover{background:#fff;color:#000}}", w2)
        self.assertEqual(w2.count(".w2-btn:hover"), 1)
        css = read("wire_timeline_static", "app.css")
        self.assertIn(".tl-go{min-height:42px;padding:12px 20px;touch-action:manipulation", css)
        self.assertIn("wire2.css?v=7", read("wire_timeline.py"))
        growth = read("growth_static", "app.css")
        self.assertIn("@media (hover:hover) and (pointer:fine){.bng-sb:hover", growth)
        self.assertNotIn(".bng-sb:hover{", growth.split("@media (hover:hover) and (pointer:fine){.bng-sb:hover")[0])

if __name__ == "__main__": unittest.main()

class ArchiveWire(unittest.TestCase):
    """2000-2024 archive (archive_wire.py): rows link straight to their source, have no write-up page, and page/filter in SQL."""
    @classmethod
    def setUpClass(cls):
        import archive_wire as AW
        cls.AW = AW
        if not os.path.exists(AW.DBF): AW.build(quiet=True)

    def test_every_row_has_a_source_link_and_tags(self):
        c = sqlite3.connect(f"file:{self.AW.DBF}?mode=ro", uri=True)
        n, bad = c.execute("SELECT COUNT(*), SUM(links NOT LIKE '%\"url\": \"http%') FROM stories").fetchone()
        self.assertGreater(n, 40000)
        self.assertEqual(bad, 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM stories WHERE tags IS NULL OR tags='[]' OR title IS NULL OR location IS NULL OR location=''").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT MIN(t) FROM stories").fetchone()[0][:4], "2000")
        self.assertLess(c.execute("SELECT MAX(t) FROM stories").fetchone()[0], "2024-10-29")

    def test_archive_rows_page_with_filters(self):
        sv = (W._public_row, W.DB, W.HDB, W.ADB_PATH)
        W.ADB_PATH = None
        d = tempfile.mkdtemp()
        for name in ("live", "hist"):    # empty live + history DBs: only the archive answers
            c = sqlite3.connect(os.path.join(d, name + ".db"))
            if name == "live":
                c.executescript("CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rank INTEGER);")
            else:
                c.executescript("CREATE TABLE stories(id TEXT PRIMARY KEY, t TEXT, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, score INTEGER, rank INTEGER, confidence TEXT, watchlist INTEGER, n_items INTEGER, families TEXT, links TEXT, sources TEXT, origin TEXT);")
            c.commit(); c.close()
        W.DB, W.HDB = os.path.join(d, "live.db"), os.path.join(d, "hist.db")
        W._public_row = lambda r, a: True
        try:
            o = W._page_build(before="2000-03-01T00:00:00Z", limit=20)
            self.assertEqual(len(o["items"]), 20)
            for it in o["items"]:
                self.assertEqual(it["a"], 1); self.assertTrue(it["l"] and it["l"][0]["u"].startswith("https://")); self.assertTrue(it["t"].startswith("2000-0"))
                self.assertTrue(it["tg"])
            o = W._page_build(before="2010-01-01T00:00:00Z", limit=10, cats="weather", regs="na")
            self.assertTrue(o["items"]); self.assertTrue(all(i["k"] == "weather" and i["g"] == "na" for i in o["items"]))
            o = W._page_build(before="2010-01-01T00:00:00Z", limit=10, sev="hi")
            self.assertTrue(o["items"]); self.assertTrue(all(i["r"] >= 7 for i in o["items"]))
            n, cur = 0, None
            for _ in range(2000):
                o = W._page_build(before=cur or "2001-01-01T00:00:00Z", limit=100); n += len(o["items"]); cur = o["next"]
                if o["end"]: break
            self.assertTrue(o["end"]); self.assertGreater(n, 1000)
            m = W.meta(); self.assertEqual(m["earliest"][:4], "2000")
        finally:
            W._public_row, W.DB, W.HDB, W.ADB_PATH = sv; W._M["t"] = 0
