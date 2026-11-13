"""Top-bar "Refresh data" (refresh_all.py), the menu's Settings item and the phone menu accordion motion (Nov 13).
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_refresh_all -v"""
import os, re, sys, threading, time, unittest
from unittest import mock
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import refresh_all as RA
import sitenav
import sitenav_ui as UI

def src(*p):
    with open(os.path.join(APP, *p), encoding="utf-8") as f: return f.read()

def reset():
    RA._S.update(busy=False, started=0.0, finished=0.0, result=None, runs=0, taps=0); RA._S["inflight"].clear()

class Coalescing(unittest.TestCase):
    def setUp(self):
        reset(); self.calls = 0
        def fake_run():
            self.calls += 1; time.sleep(0.05); return {"sources": [{"id": "x", "ok": True}]}
        self.p = mock.patch.object(RA, "run", fake_run); self.p.start()
    def tearDown(self): self.p.stop(); reset()

    def test_two_taps_in_60s_make_one_backend_refresh(self):
        a = RA.request(); b = RA.request()
        self.assertEqual(self.calls, 1)
        self.assertFalse(a["coalesced"]); self.assertTrue(b["coalesced"])
        self.assertEqual(a["refreshed_at"], b["refreshed_at"])
        self.assertGreater(b["next_in_s"], 50)

    def test_concurrent_taps_share_the_running_refresh(self):
        out = []
        ts = [threading.Thread(target=lambda: out.append(RA.request())) for _ in range(8)]
        for t in ts: t.start()
        for t in ts: t.join(5)
        self.assertEqual(self.calls, 1)
        self.assertEqual(len(out), 8)
        self.assertEqual(sum(1 for r in out if not r["coalesced"]), 1)
        self.assertEqual(len({r["refreshed_at"] for r in out}), 1)

    def test_a_tap_after_the_window_runs_again(self):
        RA.request()
        RA._S["started"] -= RA.window_s() + 1          # pretend the last run started over 60 s ago
        r = RA.request()
        self.assertEqual(self.calls, 2); self.assertFalse(r["coalesced"])

    def test_window_is_60s_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BN_REFRESH_WINDOW_S", None)
            self.assertEqual(RA.window_s(), 60.0)

    def test_status_never_starts_a_refresh(self):
        code, body = RA.handle_get("/api/refresh-all", {})
        self.assertEqual(code, 200); self.assertEqual(self.calls, 0); self.assertFalse(body["busy"])

    def test_post_runs_and_kill_switch_404s(self):
        code, body = RA.handle_post("/api/refresh-all", {})
        self.assertEqual(code, 200); self.assertTrue(body["ok"])
        with mock.patch.dict(os.environ, {"BN_REFRESH_ALL": "0"}):
            self.assertEqual(RA.handle_post("/api/refresh-all", {})[0], 404)
            self.assertEqual(RA.handle_get("/api/refresh-all", {})[0], 404)
            self.assertNotIn("data-bn-refresh", UI.topbar(sitenav))
        self.assertEqual(self.calls, 1)

class Run(unittest.TestCase):
    def setUp(self): reset()
    def tearDown(self): reset()

    def test_stale_marking_keeps_values(self):
        import types
        m = types.ModuleType("weather"); m._C = {"k": (time.time(), {"v": 1}), "skip": (("db", 1), time.time(), [])}
        sl = types.ModuleType("solar_live"); sl._cache = {"img": {"t": time.time(), "b": b"x"}}; sl._memo = {"t": time.time(), "p": {}}
        with mock.patch.dict(sys.modules, {"weather": m, "solar_live": sl}):
            n = RA.stale_caches()
        self.assertEqual(n, 3); self.assertEqual(m._C["k"], (0.0, {"v": 1}))
        self.assertIsInstance(m._C["skip"][0], tuple)            # key-based entries are left alone
        self.assertEqual(sl._cache["img"], {"t": 0, "b": b"x"}); self.assertEqual(sl._memo["t"], 0)

    def test_warm_off_makes_no_upstream_calls(self):
        with mock.patch.dict(os.environ, {"BN_REFRESH_WARM": "0"}), mock.patch.object(RA, "_mod", side_effect=AssertionError("fetched")):
            r = RA.run()
        self.assertEqual(r["sources"], [])

    def test_slow_feed_is_bounded_and_skipped_next_time(self):
        ev = threading.Event()
        slow = [("slow", "Slow feed", lambda: ev.wait(5)), ("fast", "Fast feed", lambda: None)]
        with mock.patch.object(RA, "WARM", slow), mock.patch.dict(os.environ, {"BN_REFRESH_BUDGET_S": "1"}):
            t0 = time.time(); r1 = RA.run(); took = time.time() - t0
            r2 = RA.run()
        ev.set()
        self.assertLess(took, 3)
        s1 = {s["id"]: s for s in r1["sources"]}; s2 = {s["id"]: s for s in r2["sources"]}
        self.assertTrue(s1["fast"]["ok"]); self.assertTrue(s1["slow"].get("pending"))
        self.assertEqual(s2["slow"].get("skipped"), "still running")

    def test_scanner_core_untouched(self):
        s = src("refresh_all.py").split('"""', 2)[2]          # code only, not the docstring that names them
        for bad in ("import scanner", "import push", "import jets", "aviation_watch", "import scoring", "run_scan", "interval_minutes", "save_json"):
            self.assertNotIn(bad, s)

class Wiring(unittest.TestCase):
    def test_route_and_public_post_allow(self):
        import addons
        self.assertEqual(addons.ROUTES.get("/api/refresh-all"), "refresh_all")
        ra = src("render_app.py")
        m = re.search(r"POST_ALLOW = \[(.*?)\]", ra, re.S)
        self.assertIn('"/api/refresh-all"', m.group(1))
        self.assertIn('"/api/refresh": "Scans run on', ra)        # the box-only scan endpoint stays refused

    def test_refresh_button_sits_next_to_the_theme_icon(self):
        bar = UI.topbar(sitenav)
        i, j = bar.find('class="bn-ib bn-js-only bn-refresh"'), bar.find("bn-theme-bar")
        self.assertGreater(i, 0); self.assertGreater(j, i)
        self.assertIn('aria-label="Refresh data"', bar)
        self.assertIn('Refresh data</span>', bar)                # desktop tooltip text
        self.assertIn('role="status" aria-live="polite"', bar)   # "Updated just now"

    def test_client_posts_once_and_reloads(self):
        js = src("static", "sitenav.js")
        self.assertIn('fetch("/api/refresh-all",{method:"POST"', js)
        self.assertIn("if(rfRunning)return", js)
        self.assertIn("Updated just now", js)
        self.assertIn("location.reload()", js)

class SettingsLink(unittest.TestCase):
    def test_menu_settings_item_targets_the_panel_on_every_page(self):
        for active in ("", "threat", "sources", "@stats"):
            dr = UI.drawer(sitenav, active)
            self.assertRegex(dr, r'<button type="button" class="m3-tl bn-gear-row bn-js-only" aria-controls="bn_settings">Settings</button>')
        for bar in (UI.topbar(sitenav, "sources"), sitenav.dashboard_top()):
            self.assertIn('id="bn_settings"', bar)
            self.assertIn('class="bn-pop-x" aria-label="Close settings"', bar)
            self.assertIn("bn-pop-theme", bar)                    # never an empty panel
        self.assertIn('id="status"', sitenav.dashboard_top())     # dashboard keeps scan status + interval

    def test_settings_click_opens_the_panel(self):
        js = src("static", "sitenav.js")
        self.assertIn('if(t.matches(".bn-gear-row")){e.preventDefault();e.stopPropagation();bnMenuClose(true,{noHist:true});openPop(t);return}', js)
        self.assertIn('scrim.className="bn-pop-scrim"', js)
        self.assertIn('closest(".bn-pop-x")', js)
        css = src("static", "sitenav.css")
        self.assertIn("html.bn-settings-open .bn-pop", css)       # above the menu
        self.assertIn(".bn-pop-scrim{", css)

class MenuMotion(unittest.TestCase):
    def test_same_motion_as_homepage_drawer(self):
        home_css, v3_css, v3_js, home_js = src("static", "bn-apple.css"), src("static", "bn-v3.css"), src("static", "bn-v3.js"), src("static", "bn-apple-home.js")
        self.assertIn("--a-drw:cubic-bezier(.65,0,.35,1)", home_css)
        self.assertIn("--m3-drw:cubic-bezier(.65,0,.35,1)", v3_css)
        self.assertIn("transition:height .38s var(--m3-drw),padding .38s var(--m3-drw),opacity .3s var(--m3-drw)", v3_css)
        self.assertIn("var DMS=380", home_js); self.assertIn("var MDS=380", v3_js)
        self.assertIn(".m3-body.m3-dz0>*{transform:translateY(-10px)}", v3_css)

    def test_reduced_motion_and_collapsed_on_open(self):
        v3_css, v3_js, sn_js = src("static", "bn-v3.css"), src("static", "bn-v3.js"), src("static", "sitenav.js")
        self.assertRegex(v3_css, r"prefers-reduced-motion:reduce\)\{\.bn-m3 \.m3-body\.m3-dz")
        self.assertIn("if(RMQ.matches||DESK.matches", v3_js)
        self.assertIn('x.open=false;delete x.dataset.v3auto;x.classList.remove("m3-shut")', v3_js)
        self.assertIn('if(!desk())collapseMenu();', sn_js)
        self.assertNotRegex(UI.drawer(sitenav, "threat"), r"<details\b[^>]*\bopen\b")

if __name__ == "__main__":
    unittest.main()
