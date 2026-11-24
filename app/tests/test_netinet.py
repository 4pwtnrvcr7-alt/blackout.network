import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BN_NETMAP_WARM", "0")
import netinet, netmap

def A(ds, lv, t, v=None, h=None): return {"datasource": ds, "level": lv, "time": t, "value": v, "historyValue": h}

class T(unittest.TestCase):
    def test_normal_when_no_alerts(self): self.assertEqual(netinet.judge([])[0], 0)
    def test_recovered(self): self.assertEqual(netinet.judge([A("bgp", "critical", 1, 10, 100), A("bgp", "normal", 2)])[0], 0)
    def test_bgp_big_drop_is_outage(self):
        l, d, since, n = netinet.judge([A("bgp", "critical", 100, 20, 100)])
        self.assertEqual((l, d[0]["pct"], since), (3, 20, "1970-01-01T00:01:40Z"))
    def test_tiny_dip_ignored(self): self.assertEqual(netinet.judge([A("bgp", "critical", 1, 99, 100)])[0], 0)
    def test_telescope_only_is_degraded(self): self.assertEqual(netinet.judge([A("merit-nt", "critical", 1, 5, 25)])[0], 2)
    def test_two_signals_outage(self): self.assertEqual(netinet.judge([A("merit-nt", "warning", 1, 50, 100), A("ping-slash24", "warning", 1, 85, 100)])[0], 3)
    def test_build_grey_when_feed_fails(self):
        def jget(url, **k):
            if "entities" in url and "region" in url: return {"data": [{"code": "4400", "name": "Florida"}]}
            if "entities" in url: return {"data": [{"code": "PR", "name": "Puerto Rico"}, {"code": "US", "name": "United States"}]}
            raise OSError("down")
        r = netinet.build(jget)
        self.assertEqual(set(r["places"]), {"C:PR", "S:Florida"})
        self.assertTrue(all(p["level"] == -1 for p in r["places"].values()))
    def test_recovered_by_current_value(self):
        self.assertEqual(netinet.judge([A("bgp", "critical", 1, 20, 100)], {"bgp": 97})[0], 0)
    def test_current_value_still_down(self):
        l, d, _, _ = netinet.judge([A("bgp", "critical", 1, 20, 100)], {"bgp": 50})
        self.assertEqual((l, d[0]["pct"], d[0]["live"]), (3, 50, True))
    def test_build_rechecks_down_signals(self):
        def jget(url, **k):
            if "entities" in url and "region" in url: return {"data": []}
            if "entities" in url: return {"data": [{"code": "IQ", "name": "Iraq"}]}
            if "alerts" in url and "country" in url: return {"data": [dict(A("bgp", "critical", 1, 10, 100), entity={"code": "IQ"})]}
            if "alerts" in url: return {"data": []}
            if "signals/raw/country/IQ" in url: return {"data": [[{"values": [None, 40, 99, None]}]]}
            raise OSError(url)
        r = netinet.build(jget)
        self.assertEqual(r["places"]["C:IQ"]["level"], 0)
    def test_ioda_down_gives_grey_not_error(self):
        netinet._ENTS.clear()
        def jget(url, **k): raise OSError("IODA unreachable")
        r = netinet.build(jget)
        self.assertIn("S:Florida", r["places"]); self.assertIn("C:PR", r["places"]); self.assertNotIn("C:US", r["places"])
        self.assertTrue(all(p["level"] == -1 for p in r["places"].values()))
    def test_ioda_backoff_fails_fast(self):
        import time as _t
        calls = []
        orig = netmap._http
        def boom(url, timeout=12, cap=0): calls.append(url); raise OSError("refused")
        netmap._http = boom
        try:
            netmap._IB.update(n=0, until=0.0)
            with self.assertRaises(OSError): netmap.http(netmap.IODA + "/x")
            with self.assertRaises(OSError): netmap.http(netmap.IODA + "/y")
            self.assertEqual(len(calls), 1); self.assertGreater(netmap.ioda_state()["backoff_s"], 50)
        finally:
            netmap._http = orig; netmap._IB.update(n=0, until=0.0)
    def test_serve_uses_relay_and_defaults_green(self):
        import json, tempfile, time as _t
        netinet._LG.clear()
        snap = {"generated": netinet._iso(_t.time() - 300), "feeds": {"country": True, "region": True},
                "places": {"C:PR": {"k": "C:PR", "name": "Puerto Rico", "level": 0}, "S:Florida": {"k": "S:Florida", "name": "Florida", "level": -1}}}
        d = tempfile.mkdtemp(); netinet.RELAY = d + "/r.json"; json.dump(snap, open(netinet.RELAY, "w"))
        dead = {"generated": netinet._iso(_t.time()), "feeds": {"country": False, "region": False}, "places": {"C:PR": {"k": "C:PR", "name": "Puerto Rico", "level": -1}}}
        o = netinet.serve(dead, [{"t": "Internet outage hits Puerto Rico after storm", "src": "X", "url": "https://x"}])
        self.assertEqual((o["via"], o["all_down"]), ("box-relay", False))
        self.assertEqual(o["places"]["S:Florida"]["level"], 0); self.assertEqual(o["places"]["C:PR"]["level"], 2)
        self.assertGreaterEqual(o["age_s"], 299)
    def test_serve_all_down_after_an_hour(self):
        import time as _t
        netinet._LG.clear(); netinet.RELAY = "/nonexistent"
        dead = {"generated": netinet._iso(_t.time()), "feeds": {"country": False, "region": False}, "places": {"C:PR": {"k": "C:PR", "name": "Puerto Rico", "level": -1}}}
        o = netinet.serve(dead, [])
        self.assertTrue(o["all_down"]); self.assertEqual(o["counts"]["no_data"], 1)
    def test_news_disambiguation(self):
        P = {k: {"name": n} for k, n in [("S:Georgia", "Georgia"), ("C:GE", "Georgia"), ("C:MX", "Mexico"), ("S:New Mexico", "New Mexico"),
             ("C:PG", "Papua New Guinea"), ("C:GN", "Guinea"), ("S:Virginia", "Virginia"), ("S:West Virginia", "West Virginia")]}
        H = lambda t: set(netinet._news_hits([{"t": t}], P))
        self.assertEqual(H("Internet outage hits Atlanta, Georgia"), {"S:Georgia"})
        self.assertEqual(H("Georgia: internet shutdown in Tbilisi"), {"C:GE"})
        self.assertEqual(H("Georgia internet outage"), set())
        self.assertEqual(H("New Mexico internet outage"), {"S:New Mexico"})
        self.assertEqual(H("Papua New Guinea internet outage"), {"C:PG"})
        self.assertEqual(H("West Virginia internet outage"), {"S:West Virginia"})
    def test_data_relay_fallback(self):
        import json, tempfile, time as _t
        d = tempfile.mkdtemp(); netmap.RELAY_DATA = d + "/r.json"
        json.dump({"generated": netinet._iso(_t.time() - 60), "cev": [{"x": 1}]}, open(netmap.RELAY_DATA, "w"))
        def bad(): raise OSError("403")
        self.assertEqual(netmap._relayed("cev", bad), [{"x": 1}])
        json.dump({"generated": netinet._iso(_t.time() - 9000), "cev": [{"x": 1}]}, open(netmap.RELAY_DATA, "w"))
        with self.assertRaises(OSError): netmap._relayed("cev", bad)
    def test_static_geo_served(self):
        st, body, ct = netmap.handle_get("/api/netmap/inet.json")
        self.assertEqual((st, ct), (200, "application/json")); self.assertIn(b'"S:Florida"', body); self.assertIn(b'"C:PR"', body)

if __name__ == "__main__": unittest.main()
