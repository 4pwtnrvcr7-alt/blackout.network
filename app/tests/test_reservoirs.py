import os, sys, json, unittest, urllib.parse, tarfile, io
from datetime import datetime, timedelta, timezone, date
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
os.environ.setdefault("BN_NETMAP_WARM", "0")
import reservoirs, netmap, gwmlevels

def fake(mead, powell, age=1, cw=None):
    def jget(url, **k):
        if "cwms-data" in url:
            c = next(c for c in reservoirs.CW if urllib.parse.quote(c[4]) in url or c[4] in urllib.parse.unquote(url))
            ft = cw(c) if cw else c[6]
            t0 = datetime.now(timezone.utc).timestamp() - age * 86400
            return {"values": [[int((t0 - h * 3600) * 1000), ft, 0] for h in range(200, -1, -1)]}
        v = mead if "sdi=1930" in url else powell
        days = [datetime.utcnow() - timedelta(days=age + i) for i in range(9)]
        return {"Series": [{"Data": [{"t": d.strftime("%m/%d/%Y 12:00:00 AM"), "v": str(v)} for d in reversed(days)]}]}
    return jget

class Reservoirs(unittest.TestCase):
    def test_thresholds(self):
        L = reservoirs.build(fake(1041.3, 3600))["levels"]
        self.assertEqual(L["USA-HOOVER"]["status"], "low"); self.assertEqual(L["USA0000153"]["status"], "ok")
        L = reservoirs.build(fake(970, 3520, cw=lambda c: c[5] + 1))["levels"]
        self.assertEqual({v["status"] for v in L.values()}, {"out"})
        self.assertEqual(L["USA-HOOVER"]["min_pool"], 950); self.assertEqual(L["USA0000153"]["min_pool"], 3490)

    def test_stale_or_failed_is_grey(self):
        self.assertEqual({v["status"] for v in reservoirs.build(fake(1100, 3600, age=10))["levels"].values()}, {"na"})
        def boom(url, **k): raise OSError("down")
        self.assertEqual({v["status"] for v in reservoirs.build(boom)["levels"].values()}, {"na"})

    def test_cwms_bands(self):
        gcl = next(c for c in reservoirs.CW if c[0] == "USA0006163")
        self.assertEqual(reservoirs.band(gcl[5], gcl[6]), (1228.5, 1216.2))
        L = reservoirs.build(fake(1100, 3600, cw=lambda c: c[5] + .2 * (c[6] - c[5])))["levels"]
        for c in reservoirs.CW:
            v = L[c[0]]; self.assertEqual(v["status"], "low"); self.assertEqual(v["method"], "pool"); self.assertIn("Army", v["src"])
        L = reservoirs.build(fake(1100, 3600, cw=lambda c: c[6]))["levels"]
        self.assertEqual({L[c[0]]["status"] for c in reservoirs.CW}, {"ok"})
        self.assertEqual({v["status"] for v in reservoirs.build(fake(1100, 3600, age=6))["levels"].values()}, {"na"})

    def test_gwm_rating(self):
        today = date(2026, 11, 24)
        pts = [(date(y, 11, 10), 0.0 + (y % 3) * .1) for y in range(1995, 2026)]
        self.assertEqual(gwmlevels.rate(pts + [(date(2026, 11, 15), .1)], today)["status"], "ok")
        self.assertEqual(gwmlevels.rate(pts + [(date(2026, 11, 15), -1.2)], today)["status"], "out")
        lowish = [(date(y, 11, 10), -1.0 if y % 6 == 0 else 0.0) for y in range(1995, 2026)]   # 20th pct below median, 5th not
        self.assertEqual(gwmlevels.rate(lowish + [(date(2026, 11, 15), -.6)], today)["status"], "low")
        self.assertEqual(gwmlevels.rate(pts + [(date(2026, 11, 15), -.15)], today)["status"], "ok")   # tiny dip: not "well below"
        self.assertEqual(gwmlevels.rate(pts + [(date(2026, 8, 1), -5)], today)["status"], "na")       # stale satellite pass
        self.assertEqual(gwmlevels.rate(pts[-3:] + [(date(2026, 11, 15), -5)], today)["status"], "na") # too short a record

    def test_gwm_build_and_route(self):
        m = gwmlevels.match(netmap.STATIC); self.assertGreater(len(m["lakes"]), 100)
        ids = {r[7] for r in json.load(open(os.path.join(netmap.STATIC, "hydro.json")))["p"]}
        self.assertTrue(set(m["lakes"].values()) <= ids)
        lid, pid = next(iter(m["lakes"].items()))
        rows = ["c"] * 40 + ["TOPEX   1 %s  18 11   %.2f  0.046  12.76 TMR DOR ERA 4 0 0   217.74   0" % ((date.today() - timedelta(days=365 * y + 3)).strftime("%Y%m%d"), 0.0) for y in range(1, 12)]
        rows.append("SEN6A 221 %s  17 19   -3.00  0.042  11.54 AMR GIM ECM 1 2 0   217.69   1" % (date.today() - timedelta(days=3)).strftime("%Y%m%d"))
        txt = ("TPJOJS.2.5 : v\n%s Test_Lake : id\n  1.0  2.0 : ll\n" % lid + "\n".join(rows)).encode()
        b = io.BytesIO(); t = tarfile.open(fileobj=b, mode="w:gz"); ti = tarfile.TarInfo("lake%s.10d.2.txt" % lid); ti.size = len(txt); t.addfile(ti, io.BytesIO(txt)); t.close()
        out = gwmlevels.build(lambda u, timeout: b.getvalue(), netmap.STATIC)
        self.assertEqual(out[pid]["status"], "out"); self.assertEqual(out[pid]["method"], "satellite, relative to usual level")
        snap = gwmlevels.snapshot(netmap.STATIC); self.assertTrue(snap)
        self.assertTrue(all(v["method"] == "satellite, relative to usual level" and v.get("date") for v in snap.values() if v["status"] != "na"))
        netmap._C["reservoirs"] = (__import__("time").time(), reservoirs.build(fake(1041.3, 3600)))
        netmap._C["gwm"] = (__import__("time").time(), {pid: out[pid], "USA0006163": dict(out[pid])})
        code, r = netmap.handle_get("/api/netmap/reservoirs")
        self.assertEqual(code, 200); self.assertEqual(r["levels"][pid]["status"], "out")
        self.assertEqual(r["levels"]["USA0006163"]["method"], "pool")   # U.S. gauge rating wins over satellite
        netmap._C.pop("reservoirs", None); netmap._C.pop("gwm", None)

    def test_hydro_layer(self):
        d = json.load(open(os.path.join(netmap.STATIC, "hydro.json")))
        self.assertIn("CC BY 4.0", d["credit"]); self.assertGreater(len(d["p"]), 3000)
        ids = {r[7] for r in d["p"]}
        for r in reservoirs.RES: self.assertIn(r["id"], ids)   # every rated reservoir has its dam on the map
        for c in reservoirs.CW: self.assertIn(c[0], ids)
        self.assertEqual(netmap.handle_get("/api/netmap/hydro.json")[0], 200)
        self.assertIn('data-k="hydro"', netmap.page({}))
        js = open(os.path.join(netmap.STATIC, "net.js"), encoding="utf-8").read()
        self.assertIn('"rgba(124,129,144,.35)"', js)   # no level data = grey, never green by default

if __name__ == "__main__": unittest.main()
