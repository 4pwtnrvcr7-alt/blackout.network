"""Wire list speed layer (Nov 25 2026). Run: cd app && python3 -m unittest tests.test_wire_speed -v

Proves: (1) the in-memory public gate answers exactly like story_writer.allow(); (2) concurrent list calls while a writer
holds the story_writer database never raise 'database is locked', never open a story_writer connection or take its
lock on the request path, and stay under 1 s; (3) rows with fewer than 3 tags are cached, not recomputed.
"""
import json, os, sqlite3, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

D = tempfile.mkdtemp()
import story_writer as SW
import wire_timeline as W


def build():
    db = os.path.join(D, "blackout.db"); c = sqlite3.connect(db)
    c.execute("""CREATE TABLE clusters (cluster_id TEXT, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT,
                 updated TEXT, score INT, confidence TEXT, n_items INT, n_families INT, families TEXT, links TEXT, watchlist INT, brief TEXT, rank INT)""")
    for i in range(400):
        c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (f"c{i:015x}", f"Quake number {i} hits Japan near Tokyo", "natural disaster", "Japan", None, None, None,
                   f"2026-11-{1 + i % 28:02d}T{i % 24:02d}:{i % 60:02d}:00Z", None, 10, "High", 1, 1, '["official"]',
                   '[{"source":"USGS","url":"https://usgs.gov/x"}]', 0, "WHAT: A quake.", i % 11))
    c.commit(); c.close()
    k = SW.db()
    for i in range(400):
        cid = f"c{i:015x}"
        m = i % 8
        if m == 0:   k.execute("INSERT INTO briefs(cid, note) VALUES(?,?)", (cid, json.dumps({"file": "x", "writer": {"model": "grok"}})))
        elif m == 1: k.execute("INSERT INTO briefs(cid, note) VALUES(?,?)", (cid, json.dumps({"file": "story_writer_template", "writer": {"model": "template"}})))
        elif m == 2: k.execute("INSERT INTO briefs(cid, note) VALUES(?,?)", (cid, json.dumps({"file": "x", "writer": {"model": "template"}})))
        elif m == 3: k.execute("INSERT INTO briefs(cid, note, alias_of) VALUES(?,?,?)", (cid, None, f"c{(i - 3):015x}"))
        elif m == 4: k.execute("INSERT INTO briefs(cid, note) VALUES(?,?)", (cid, "not json{"))
        elif m == 5: k.execute("INSERT INTO briefs(cid, note) VALUES(?,?)", (cid, "null"))
        if i % 5 == 0: k.execute("INSERT OR REPLACE INTO needs_paid(cid, since, rank, title) VALUES(?,?,?,?)", (cid, "2026-11-25T00:00:00Z", 6, "t"))
        if i % 3 == 0: k.execute("INSERT OR REPLACE INTO ready(cid, kind, tags, card_ok, ready_at, title, rank) VALUES(?,?,?,?,?,?,?)",
                                 (cid, "template", json.dumps(["#Japan", "#Tokyo", "#Earthquake", "#News"]), 1, "x", "t", 5))
    k.commit(); k.close()
    return db


class Speed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # other test modules (same process) change these env vars and cached config: pin ours again
        cls.env = {k: os.environ.get(k) for k in ("BN_WRITER_DB", "BN_XTAGS_DB", "BN_CARD_GATE", "BN_PUBLISH_GATE")}
        os.environ.update({"BN_WRITER_DB": os.path.join(D, "story_writer.db"), "BN_XTAGS_DB": os.path.join(D, "xtags.db"), "BN_CARD_GATE": "0", "BN_PUBLISH_GATE": "1"})
        cls.db = build()
        SW._NC.update(t=0, v={})      # story_writer.notes() keeps a 5 s cache that another test module may have filled
        cls.old = (W.DB, W.HDB, SW._desk_maps, SW.STATE.get("gate_on"))
        W.DB = cls.db; W.HDB = os.path.join(D, "none.db")
        SW._desk_maps = lambda: ({"c00000000000000a": {"x": 1}}, {"c000000000000003": "c00000000000000a"}, {"c00000000000000b": {}})
        SW.STATE["gate_on"] = True
        W._reset_caches()
        W._snap_refresh(block=True)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls.env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        W.DB, W.HDB, SW._desk_maps, SW.STATE["gate_on"] = cls.old

    def test_gate_snapshot_matches_story_writer_allow(self):
        SW._NC.update(t=0, v={}); W._snap_refresh(block=True)
        cids = [f"c{i:015x}" for i in range(400)] + ["c00000000000000a", "c00000000000000b", "nope"]
        diffs = [c for c in cids if W._gate_ok(c) != SW.allow(c)]
        self.assertEqual(diffs, [])
        self.assertTrue(any(W._gate_ok(c) for c in cids) and not all(W._gate_ok(c) for c in cids))

    def test_list_stays_fast_and_never_locks_while_a_writer_holds_the_database(self):
        W._reset_caches(); W._snap_refresh(block=True); W.start_warm()
        calls = {"db": [], "lk": []}
        real_db, real_lk = SW.db, SW._LK

        class LK:
            def __enter__(s):
                calls["lk"].append(threading.current_thread().name); return real_lk.__enter__()
            def __exit__(s, *a): return real_lk.__exit__(*a)
            def acquire(s, *a, **k): calls["lk"].append(threading.current_thread().name); return real_lk.acquire(*a, **k)
            def release(s): return real_lk.release()
        def spy_db():
            calls["db"].append(threading.current_thread().name); return real_db()
        SW.db = spy_db; SW._LK = LK()
        stop = time.time() + 6
        errs, lat, bad = [], [], []

        def writer():                       # holds the story_writer database exclusively, again and again (like package_one)
            k = sqlite3.connect(os.environ["BN_WRITER_DB"], timeout=0.2, isolation_level=None)
            n = 0
            while time.time() < stop:
                try:
                    k.execute("BEGIN EXCLUSIVE")
                    time.sleep(0.15)
                    k.execute("INSERT OR REPLACE INTO ready(cid, kind, tags, card_ok) VALUES(?,?,?,1)", (f"w{n}", "t", "[]")); n += 1
                    k.execute("COMMIT")
                except sqlite3.Error:
                    pass
                time.sleep(0.02)
            k.close()

        qsets = [{"limit": ["100"]}, {"limit": ["100"], "sev": ["hi"]}, {"limit": ["200"], "sev": ["mid"]}, {"limit": ["100"], "sev": ["lo"]},
                 {"limit": ["50"], "cats": ["quake"]}, {"limit": ["20"], "regs": ["as"]}, {"limit": ["100"], "q": ["Quake"]}]

        def reader(n):
            i = n
            while time.time() < stop:
                q = dict(qsets[i % len(qsets)])
                if i % 3 == 0 and "before" not in q:
                    q["before"] = [f"2026-11-{10 + i % 15:02d}T12:00:00Z|zzzz"]
                t = time.time()
                try:
                    code, body = W.handle_get("/api/wire_tl", q)[:2]
                    if code != 200 or "locked" in json.dumps(body):
                        bad.append((code, str(body)[:120]))
                    if i % 5 == 0:
                        code, body = W.handle_get("/api/wire_tl/xu", {"id": [f"c{(i * 7) % 400:015x}"]})[:2]
                        if code != 200: bad.append((code, str(body)[:120]))
                except Exception as ex:
                    errs.append(repr(ex))
                lat.append(time.time() - t); i += 7
                time.sleep(0.01)

        ths = [threading.Thread(target=writer, name="writer")] + [threading.Thread(target=reader, args=(n,), name=f"req-{n}") for n in range(16)]
        try:
            for t in ths: t.start()
            for t in ths: t.join()
        finally:
            SW.db = real_db; SW._LK = real_lk
        self.assertEqual(errs, [])
        self.assertEqual(bad, [])
        self.assertGreater(len(lat), 100)
        req_db = [n for n in calls["db"] if n.startswith("req")]; req_lk = [n for n in calls["lk"] if n.startswith("req")]
        self.assertEqual((req_db, req_lk), ([], []), "request threads touched story_writer's connection or lock")
        lat.sort()
        p95 = lat[int(len(lat) * 0.95)]
        self.assertLess(p95, 1.0, f"p95 {p95:.2f}s max {lat[-1]:.2f}s over {len(lat)} calls")

    def test_short_tag_rows_are_cached_not_recomputed(self):
        W._reset_caches(); W._snap_refresh(block=True)
        n = {"c": 0}
        real = W._xu_build
        def counting(*a, **k):
            n["c"] += 1; return real(*a, **k)
        W._xu_build = counting
        try:
            row = {"id": "c000000000000001", "title": "Zzz qqq", "category": "", "brief": "", "watchlist": 0, "hidden": 0}
            for _ in range(5):
                W._xu_for(row, 1, "Zzz qqq", "Zzz qqq", "", [], "", "", False, True)
            self.assertEqual(n["c"], 1)
            self.assertEqual(W._xu_for(row, 1, "Zzz qqq", "Zzz qqq", "", [], "", "", False, False), W._XC["c000000000000001"][1])
        finally:
            W._xu_build = real

    def test_request_path_does_not_compute_tags_but_the_warm_pass_fills_the_cache(self):
        W._reset_caches(); W._snap_refresh(block=True)
        a = W._page_build(limit=30)
        live = [x for x in a["items"] if not x["a"]]
        self.assertTrue(live and all(x["xu"] == "" for x in live))
        W._TL.warm = True
        try:
            W._warm_rows(40)
        finally:
            W._TL.warm = False
        b = W._page_build(limit=30)
        got = [x for x in b["items"] if x["xu"]]
        self.assertTrue(got)
        import urllib.parse
        for x in got:
            text = urllib.parse.parse_qs(urllib.parse.urlparse(x["xu"]).query)["text"][0]
            tags = [t for t in text.split() if t.startswith("#")]
            self.assertTrue(3 <= len(tags) <= 5, text)
            self.assertFalse({t.lower() for t in tags} & {"#news", "#blackoutnetwork", "#health", "#alerts"}, text)

    def test_client_fetches_xu_for_rows_without_one(self):
        js = open(os.path.join(W.STATIC, "app.js"), encoding="utf-8").read()
        self.assertIn("/api/wire_tl/xu?id=", js)
        self.assertIn('data-xid="', js)

    def test_standard_pages_stay_warm_with_no_recent_request(self):
        """Live miss (Nov 25): limit=100 took 4.7 s because the warm thread only refreshed pages asked for in the last 3 minutes."""
        W._reset_caches(); W._snap_refresh(block=True); W._PA.clear()
        W._warm_cycle()
        for sev in (None, "hi", "mid", "lo"):
            key = W._pkey(None, None, 100, "", False, None, None, None, sev, None, None, None)
            self.assertIn(key, W._PC["v"], sev)
        t0 = time.time(); W.page(limit=100, sev="hi"); self.assertLess(time.time() - t0, 0.05)


if __name__ == "__main__":
    unittest.main()
