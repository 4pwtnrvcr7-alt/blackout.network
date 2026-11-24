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
    def test_static_geo_served(self):
        st, body, ct = netmap.handle_get("/api/netmap/inet.json")
        self.assertEqual((st, ct), (200, "application/json")); self.assertIn(b'"S:Florida"', body); self.assertIn(b'"C:PR"', body)

if __name__ == "__main__": unittest.main()
