"""pt1758u /network status board: reports (rate limits, ZIP only), timeline, hourly history, chain reactions, page, newsletter lines. Offline, temp DB."""
import os, sys, re, json, tempfile, unittest, time
from datetime import datetime, timezone, timedelta
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"
os.environ["BN_NETBOARD_DB"] = os.path.join(tempfile.mkdtemp(prefix="nb_"), "votes.db")
import netboard as NB, netmap

def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")

class Board(unittest.TestCase):
    def setUp(self):
        NB._RL.clear(); NB._AGG["t"] = 0
        c = NB.db(); c.executescript("DELETE FROM net_reports; DELETE FROM net_timeline; DELETE FROM net_hours; DELETE FROM net_open;"); c.commit(); c.close()

    def test_zip_state(self):
        for z, st in (("10001", "NY"), ("02139", "MA"), ("02903", "RI"), ("94103", "CA"), ("60601", "IL"), ("75201", "TX"), ("99501", "AK"), ("20500", "DC"), ("00901", "PR")):
            self.assertEqual(NB.zip_state(z), st, z)
        for z in ("", "1234", "abcde", "123456", "00000"): self.assertIsNone(NB.zip_state(z))

    def test_report_limits_and_zip(self):
        valid = {"aws", "verizonwireless"}
        self.assertEqual(NB.post({"svc": "nope"}, "1.1.1.1", valid)[0], 400)
        self.assertEqual(NB.post({"svc": "aws", "zip": "12ab5"}, "1.1.1.1", valid)[0], 400)
        code, r = NB.post({"svc": "aws"}, "1.1.1.1", valid); self.assertEqual(code, 200); self.assertRegex(r["tok"], r"^[a-f0-9]{16}$")
        self.assertEqual(NB.post({"svc": "aws"}, "1.1.1.1", valid)[0], 429)            # same service, same connection, 15 min
        self.assertEqual(NB.post({"svc": "aws"}, "2.2.2.2", valid)[0], 200)            # someone else counts
        self.assertEqual(NB.post({"tok": r["tok"], "zip": "10001"}, "1.1.1.1", valid), (200, {"status": "ok", "st": "NY"}))
        self.assertEqual(NB.post({"tok": r["tok"], "zip": "60601"}, "1.1.1.1", valid)[0], 404)   # a ZIP is added once
        for i in range(11): NB._RL.setdefault(NB._ipk("3.3.3.3"), []).append((time.time(), "x%d" % i))
        self.assertEqual(NB.post({"svc": "verizonwireless"}, "3.3.3.3", valid)[0], 200)
        self.assertEqual(NB.post({"svc": "aws"}, "3.3.3.3", valid)[0], 429)            # 12 an hour per connection
        c = NB.db(); cols = [r[1] for r in c.execute("PRAGMA table_info(net_reports)")]; c.close()
        self.assertEqual(cols, ["id", "svc", "ts", "zip", "st", "tok"])                 # no IP, no user agent, nothing else
        rep = NB.reports(); self.assertEqual(rep["aws"]["h1"], 2); self.assertEqual(rep["aws"]["states"], {"NY": 1}); self.assertEqual(sum(rep["aws"]["hrs"]), 2)
        self.assertFalse(rep["aws"]["surge"])

    def test_write_gate(self):
        import types
        fake = types.SimpleNamespace(FREEZE={"until": time.time() + 60}, SYNC={"restored": True}, SYNC_SECRET="x" * 40, BOOTED=time.time())
        real = sys.modules["__main__"]; sys.modules["__main__"] = fake
        try:
            self.assertFalse(NB.writable()); self.assertEqual(NB.post({"svc": "aws"}, "7.7.7.7", {"aws"})[0], 503)
            fake.FREEZE = {"until": 0}; fake.SYNC = {"restored": False}; self.assertFalse(NB.writable())
            fake.SYNC = {"restored": True}; self.assertTrue(NB.writable())
        finally: sys.modules["__main__"] = real

    def test_surge(self):
        c = NB.db(); t = int(time.time())
        for i in range(8): c.execute("INSERT INTO net_reports(svc, ts) VALUES('tmobile', ?)", (t - i * 60,))
        c.commit(); c.close(); r = NB.reports()["tmobile"]
        self.assertTrue(r["surge"]); self.assertEqual(r["h1"], 8)

    def test_record_timeline_and_hours(self):
        n0 = datetime.now(timezone.utc)
        nets = [dict(id="aws", name="AWS", level=2, kind="np", basis="provider incident reports", recent_ok=True,
                     recent=[dict(t="Increased error rates in US-EAST-1", s=iso(n0 - timedelta(hours=2)), e=None, lv=2)]),
                dict(id="stripe", name="Stripe", level=2, kind="stripe", status="Issues reported", incidents=[dict(t="api: degraded")]),
                dict(id="fedres", name="Fed", level=-1, link_only=True)]
        NB.record(nets)
        tl = NB.timeline(); self.assertEqual({t["svc"] for t in tl}, {"aws", "stripe"})
        self.assertTrue(all(t["end"] is None for t in tl))
        nets[0]["recent"][0]["e"] = iso(n0); nets[1]["level"] = 0
        NB.record(nets); tl = {t["svc"]: t for t in NB.timeline()}
        self.assertIsNotNone(tl["aws"]["end"]); self.assertIsNotNone(tl["stripe"]["end"]); self.assertGreaterEqual(tl["aws"]["mins"], 119)
        self.assertEqual(len(NB.timeline()), 2)                                          # updated in place, not duplicated
        h = NB.hours({"aws", "stripe"}); self.assertEqual(h["aws"][-1], 2); self.assertEqual(h["stripe"][-1], 2); self.assertEqual(len(h["aws"]), 24)

    def test_hrs_and_recent_helpers(self):
        n = datetime.now(timezone.utc)
        h = netmap._hrs([(n - timedelta(hours=3, minutes=10), n - timedelta(hours=2, minutes=50), 3)])
        self.assertEqual(len(h), 24); self.assertEqual(max(h), 3); self.assertEqual(h[-1], 0)
        r = netmap._recent([("old", n - timedelta(days=9), n - timedelta(days=9), 2), ("new", n - timedelta(hours=1), None, 2)])
        self.assertEqual([x["t"] for x in r], ["new"])

    def test_deps_documented_and_valid(self):
        ids = {x[0] for x in netmap.NETS}
        for d in NB.DEPS:
            self.assertIn(d["up"], ids); self.assertTrue(d["src"].startswith("https://")); self.assertTrue(d["why"])
            for k in d["down"]: self.assertIn(k, ids, k)

    def test_board_endpoint_and_page(self):
        code, b = netmap.handle_get("/api/netmap/board")[:2]
        self.assertEqual(code, 200); self.assertIn("deps", b); self.assertIn("st_pt", b); self.assertIn("NY", b["st_pt"])
        for f in ("board.js", "board.css"): self.assertEqual(netmap.handle_get("/api/netmap/" + f)[0], 200)
        import netpages
        h = netpages.handle_get("/network", {})[1]
        for s in ('id="nb"', 'id="nb_q"', 'data-m="status"', 'data-m="map"', 'data-m="sky"', 'class="nx nx-board"', "/api/netmap/board.js", "/api/netmap/board.css", 'data-s="rep"'):
            self.assertIn(s, h)
        self.assertLess(h.index("/api/netmap/net.js"), h.index("/api/netmap/board.js"))

    def test_no_yellow_and_red_only_for_major(self):
        import colorsys
        for f in ("board.js", "board.css"):
            t = open(os.path.join(APP, "netmap_static", f), encoding="utf-8").read()
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S).lower())
            for h in set(re.findall(r"#([0-9A-Fa-f]{6})\b", t)):
                r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)); hue, l, sat = colorsys.rgb_to_hls(r, g, b)
                if sat > 0.4 and l > 0.25: self.assertFalse(0.1 < hue < 0.2, f + " #" + h)
        css = open(os.path.join(APP, "netmap_static", "board.css"), encoding="utf-8").read()
        reds = [m.group(0) for m in re.finditer(r"[^{}]*\{[^}]*(?:var\(--rd\)|#FF3B3B)[^}]*\}", css)]
        self.assertTrue(reds and all(re.search(r"out|--rd:", r) for r in reds), reds)

    def test_vote_route(self):
        import votes
        code, r = votes.handle_post("/api/vote/netdown", {"svc": "aws"}, ip="9.9.9.9"); self.assertEqual(code, 200)
        self.assertEqual(votes.handle_post("/api/vote/netdown", {"svc": "fedres"}, ip="9.9.9.8")[0], 400)   # link-only entries take no reports

    def test_newsletter_log_lines(self):
        import newsletter_net as NET
        n0 = datetime.now(timezone.utc)
        d = {"generated": iso(n0), "summary": {"networks": 2, "ok": 2, "power_customers": 0}, "nets": [dict(id="aws", name="AWS", level=0)],
             "outages": {"countries": []}, "timeline": [dict(svc="aws", name="AWS", title="Increased error rates", start=iso(n0 - timedelta(hours=3)), end=iso(n0 - timedelta(hours=1)), level=2),
                                                         dict(svc="kraken", name="Kraken", title="Minor thing", start=iso(n0 - timedelta(hours=2)), end=iso(n0), level=1)]}
        s = NET.build(d); self.assertEqual(len(s["lines"]), 1); self.assertTrue(s["lines"][0].startswith("Recovered: AWS, Increased error rates ("))
        self.assertTrue(s["lines"][0].endswith(" ET)."))

if __name__ == "__main__": unittest.main()
