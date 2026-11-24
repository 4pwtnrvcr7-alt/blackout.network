"""pt1785u Network page v2 stage 1: banks/cards/payments tracked, honest signals, flip-card tiles, on-site detail pages. Offline."""
import os, sys, re, tempfile, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"
os.environ.setdefault("BN_NETBOARD_DB", os.path.join(tempfile.mkdtemp(prefix="nw_"), "votes.db"))
import netmap, netwatch as W, netboard as NB

class Watch(unittest.TestCase):
    def test_matt_list_is_tracked(self):
        ids = {n[0] for n in netmap.NETS}
        for k in ("wellsfargo", "chase", "bofa", "citi", "capitalone", "usbank", "pnc", "truist", "td", "navyfederal", "usaa", "schwab", "fidelity", "robinhood",
                  "zelle", "venmo", "cashapp", "paypal", "visa", "mastercard", "amex", "discover", "stripe", "square", "applepay", "googlepay"):
            self.assertIn(k, ids)
        for n in netmap.NETS:
            if n[3] == "watch": self.assertIn(n[4], W.W)

    def test_headline_matching(self):
        yes = [("chase", "Customers report Chase, US Bank, others are down"), ("wellsfargo", "Wells Fargo outage leaves customers unable to log in"),
               ("schwab", "Is Charles Schwab Down? Users Report Problems"), ("zelle", "Zelle outage impacting some customers trying to pay rent")]
        no = [("wellsfargo", "Worried about another bank outage? 5 simple things you can do to prepare now"), ("citi", "Citi Sees a 12% DRAM Hit at Worst; Micron Is Down 51%"),
              ("visa", "Visa Is Down 14% This Year While Analysts See 33% Upside"), ("chase", "Flock of wild turkeys chase down woman taking a walk"),
              ("wellsfargo", "Man arrested after armed robbery at Hampton Wells Fargo"), ("visa", "Foreign Student Visa Issuance Is Down Over 40 Percent")]
        for s, t in yes: self.assertTrue(W.match(s, t), t)
        for s, t in no: self.assertFalse(W.match(s, t), t)

    def test_watch_levels_never_invent(self):
        fake = lambda news, web: (lambda key, ttl, fn, wait=True: news if key == "watch:news" else [] if key == "watch:wire" else web)
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc); W._FAILS.clear()
        r = W.watch_one("wellsfargo", fake([], ("reachable", 200, 50)))
        self.assertEqual(r["level"], -1); self.assertIn("No live signal", r["status"]); self.assertNotIn("affected", r); self.assertTrue(r["watch"])   # never green without a real signal
        hot = [dict(t="Wells Fargo outage: customers can't log in", src="X", url="https://e.com", at=(now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))]
        self.assertEqual(W.watch_one("wellsfargo", fake(hot, ("reachable", 200, 50)))["level"], 2)
        old = [dict(hot[0], at=(now - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ"))]
        r = W.watch_one("wellsfargo", fake(old, ("reachable", 200, 50))); self.assertEqual(r["level"], -1); self.assertEqual(r["sig"]["news48"], 1)
        W._FAILS.clear(); W.watch_one("wellsfargo", fake([], ("unreachable", None, None)))
        self.assertEqual(W.watch_one("wellsfargo", fake([], ("unreachable", None, None)))["level"], 2)   # two failed sign-in checks in a row
        self.assertEqual(W.watch_one("wellsfargo", fake(hot, ("unreachable", None, None)))["level"], 3)
        W._FAILS.clear()

    def test_snapshot_round_trip(self):
        NB.save_snapshot("t", '{"a":1}'); self.assertEqual(NB.load_snapshot("t"), '{"a":1}')

    def test_detail_page_and_route(self):
        orig = netmap.data
        try:
            netmap.data = lambda: dict(generated="2026-11-23T20:00:00Z", nets=[dict(id="wellsfargo", name="Wells Fargo", group="bank", kind="watch", level=-1, watch=True,
                                       status="No live signal", sig=dict(news=0, news48=0, web="reachable"), news=[], h24=[0] * 24,
                                       status_url=None, support="https://www.wellsfargo.com/help/", basis="no public status page")])
            code, html, ct = netmap.handle_get("/grid/status/wellsfargo")
            self.assertEqual(code, 200); h = html.decode() if isinstance(html, bytes) else html
            for s in ("Wells Fargo", "Uptime, last 90 days", "Incident history", "Not published", "sd_down", "None published", "No live signal", "Website reachable"): self.assertIn(s, h)
            self.assertNotIn("No outage reported", h)
            self.assertNotIn("#F5A524", h)
            self.assertEqual(netmap.handle_get("/grid/status/nope")[0], 404)
            import netpages
            self.assertEqual(netpages.handle_get("/grid/status/wellsfargo", {})[0], 200)
        finally: netmap.data = orig

    def test_accordion_cards(self):
        js = open(os.path.join(APP, "netmap_static", "board.js"), encoding="utf-8").read()
        css = open(os.path.join(APP, "netmap_static", "board.css"), encoding="utf-8").read()
        # Nov 24 2026 (Matt): inline accordion instead of the flip; Full details keeps the bookmarkable /grid/status/<id> page
        for s in ("data-flip", "/grid/status/", "Expand", "Hide details", "nb-fb", "wells fargo", "Full details", "Official status", "No active incidents", "Last checked", "aria-expanded", "nb-lg", "nb-key"): self.assertIn(s, js)
        for s in (".nb-fc.open", ".nb-fb[hidden]", ".nb-lg", ".nb-key", "prefers-reduced-motion"): self.assertIn(s, css)
        self.assertNotIn("rotateY", css); self.assertNotIn("location.href", js)   # no flip, no auto-navigation
        self.assertNotIn("nb-grid", js)   # bnt/theme.css forces every *-grid to one column on phones

    def test_history_keeps_90_days(self):
        h = NB.service_history("wellsfargo", 90); self.assertEqual(len(h["days"]), 90)

if __name__ == "__main__":
    unittest.main()
