"""Pulse intro (live instrument on "/"). Run: cd app && python3 -m unittest tests.test_pulse_v2 -v"""
import os, re, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pulse_v2, theme

def _read(n):
    with open(os.path.join(pulse_v2.STATIC, n), encoding="utf-8") as f: return f.read()

class PulseHome(unittest.TestCase):
    def setUp(self): os.environ["BN_INTRO_PULSE"] = "1"; os.environ["BN_INTRO_SX"] = "0"   # the panel intro (intro_sx) wins when on
    def tearDown(self): os.environ.pop("BN_INTRO_PULSE", None); os.environ.pop("BN_INTRO_SX", None)

    def test_home_is_the_instrument_with_menu_brief_follow_and_footer(self):
        h = theme.home_page()
        self.assertIn('<section class="pl" id="s1"', h)
        self.assertEqual(len(re.findall(r'<button type="button" class="pl-pill"', h)), 4)
        self.assertIn('<span class="bnt-wm">blackout.network</span>', h)
        self.assertIn('id="h_menu"', h); self.assertIn("data-h-menu", h)
        self.assertIn('id="s6"', h); self.assertIn('id="nl_app"', h)   # the free-brief signup stays on "/"
        self.assertIn('id="bng_follow"', h)
        self.assertEqual(h.count("<footer"), 1)
        self.assertIn("/api/pulse/pulse.js", h); self.assertIn("/api/pulse/pulse.css", h)
        self.assertNotIn("home.js", h)                                  # the old section script is not loaded
        self.assertNotIn('class="h-sec" id="s2"', h)                    # the six video sections are gone
        self.assertNotIn("hero-d.jpg", h)

    def test_kill_switch_restores_previous_intro(self):
        os.environ["BN_INTRO_PULSE"] = "0"
        try:
            h = theme.home_page()
            self.assertNotIn('class="pl"', h); self.assertIn('id="s2"', h); self.assertIn("home.js", h)
        finally: os.environ.pop("BN_INTRO_PULSE", None)

    def test_default_is_the_previous_intro(self):
        os.environ.pop("BN_INTRO_PULSE", None)
        h = theme.home_page()
        self.assertNotIn('class="pl"', h); self.assertIn('id="s2"', h); self.assertIn("home.js", h)

    def test_markup_drift_falls_back_to_previous_intro(self):
        orig = pulse_v2.transform
        try:
            pulse_v2.transform = lambda h: (_ for _ in ()).throw(ValueError("drift"))
            h = theme.home_page()
            self.assertIn('id="s2"', h); self.assertNotIn('class="pl"', h)
        finally: pulse_v2.transform = orig

    def test_credits_row(self):
        rows = dict((k, r) for k, _, r in theme._ledger())["intro"]
        self.assertIn("Original", rows[0][2]); self.assertEqual(len(rows), 1)
        os.environ["BN_INTRO_PULSE"] = "0"
        try: self.assertIs(theme._ledger(), theme.CREDITS_LEDGER)
        finally: os.environ.pop("BN_INTRO_PULSE", None)

    def test_route_serves_files_and_404(self):
        import addons
        self.assertEqual(addons.ROUTES.get("/api/pulse"), "pulse_v2")
        for n in ("pulse.css", "pulse.js"):
            r = pulse_v2.handle_get("/api/pulse/" + n, {}); self.assertEqual(r[0], 200); self.assertTrue(r[1])
        self.assertEqual(pulse_v2.handle_get("/api/pulse/nope", {})[0], 404)

class PulseRules(unittest.TestCase):
    def test_buttons_are_pills_and_no_square_buttons(self):
        css = _read("pulse.css")
        for sel in (".pl-pill{", ".pl-btn{"):
            body = css[css.index(sel):].split("}", 1)[0]
            self.assertIn("border-radius:999px", body, sel)
        self.assertNotRegex(css, r"\.pl-(pill|btn)[^{}]*\{[^}]*border-radius:(0|2px)")

    def test_no_yellow_no_metric_no_banned_words(self):
        for n in ("pulse.css", "pulse.js"):
            s = _read(n)
            self.assertNotRegex(s, r"(?i)#F[CDE][0-9A-F]{4}\b|#FFC21A|#FFE|rgba?\(\s*255\s*,\s*(1[5-9]\d|2[0-4]\d)\s*,\s*\d{1,2}\b|\byellow\b|\bamber\b")
            self.assertNotRegex(s, r"(?i)peer-to-peer|\bkm\b|°C|\bkph\b")
        self.assertNotRegex(_read("pulse.css"), r"#FF4D4F[^;}]*;[^}]*\.pl-pill")   # red only for the level dot
        self.assertEqual(len(re.findall(r"#FF4D4F", _read("pulse.css"))), 1)

    def test_live_not_frozen_and_scroll_rules(self):
        js = _read("pulse.js")
        self.assertIn('fetch("/api/pulse/live"', js); self.assertIn("setInterval(load,60000)", js)
        self.assertNotIn("window.D=", js); self.assertNotIn("localStorage", js)
        self.assertNotIn("wheel", js); self.assertNotIn("preventDefault();t.scrollIntoView", js)
        self.assertNotIn("scroll-snap", _read("pulse.css"))
        self.assertIn("prefers-reduced-motion", js); self.assertIn("prefers-reduced-motion", _read("pulse.css"))
        self.assertIn("requestAnimationFrame", js); self.assertIn("d.hidden", js)   # pauses off screen / in a hidden tab

    def test_no_refresh_button_here(self):
        self.assertNotIn("data-bn-refresh", pulse_v2._section("/wire", "Open The Wire"))

class PulseLive(unittest.TestCase):
    def setUp(self): pulse_v2._C.update(t=0, v=None, busy=False, good={})
    def tearDown(self): pulse_v2._C.update(t=0, v=None, busy=False, good={})

    def test_failed_section_is_hidden_not_faked(self):
        orig = pulse_v2.BUILDERS
        try:
            pulse_v2.BUILDERS = (("wire", lambda: (_ for _ in ()).throw(RuntimeError("x"))),
                                 ("grid", lambda: {"regions": [{"id": "A", "status": "online", "mw": 1}], "series": [], "g": 0}),
                                 ("space", lambda: {"space": {"kp": [1.0], "now": 1.0, "g": 0}, "quakes": [[int(time.time()), 3.0]]}))
            v = pulse_v2._build()
            self.assertIsNone(v["wire"]); self.assertIn("wire", v["errors"]); self.assertIsNotNone(v["grid"]); self.assertIsNotNone(v["quakes"])
        finally: pulse_v2.BUILDERS = orig

    def test_last_good_kept_for_ten_minutes_then_dropped(self):
        orig = pulse_v2.BUILDERS
        ok = {"level": 7.1, "level_n": 25, "level_hi": True, "n": 150, "ranks": {"7": 25}, "scan_et": "1:00 AM ET", "scan": ""}
        try:
            pulse_v2.BUILDERS = (("wire", lambda: ok), ("grid", lambda: None), ("space", lambda: None))
            pulse_v2._build(); pulse_v2._C["v"] = pulse_v2._build()
            pulse_v2.BUILDERS = (("wire", lambda: (_ for _ in ()).throw(RuntimeError("x"))), ("grid", lambda: None), ("space", lambda: None))
            self.assertEqual(pulse_v2._build()["wire"]["n"], 150)                       # a blip keeps it
            pulse_v2._C["good"]["wire"] = time.time() - pulse_v2.MAX_AGE - 5
            self.assertIsNone(pulse_v2._build()["wire"])                                 # too old: hidden
        finally: pulse_v2.BUILDERS = orig

    def test_grid_series_only_full_hours(self):
        def reg(i, s): return {"id": i, "status": "online", "demand_mw": 10, "series": s}
        G = {"regions": [reg("A", [["2026-11-28T03:00:00Z", 10], ["2026-11-28T04:00:00Z", 10]]), reg("B", [["2026-11-28T03:00:00Z", 20]])], "swpc": {"g": 1}}
        orig = pulse_v2._call
        try:
            pulse_v2._call = lambda m, p: G
            g = pulse_v2._b_grid()
            self.assertEqual(len(g["series"]), 1); self.assertEqual(g["series"][0][1], 30); self.assertEqual(g["g"], 1)
        finally: pulse_v2._call = orig

    def test_space_skips_partial_bins_and_old_quakes(self):
        now = time.time(); iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
        S = {"bins": [{"kp": 2.0, "partial": 0}, {"kp": 0.7, "partial": 1}], "now": {"kp": {"value": 2.67, "g": 0}},
             "map": [{"t": iso(now - 3600), "mag": 4.2}, {"t": iso(now - 3 * 86400), "mag": 6.0}]}
        orig = pulse_v2._call
        try:
            pulse_v2._call = lambda m, p: S
            r = pulse_v2._b_space()
            self.assertEqual(r["space"]["kp"], [2.0]); self.assertEqual(r["space"]["now"], 2.67); self.assertEqual([q[1] for q in r["quakes"]], [4.2])
        finally: pulse_v2._call = orig

if __name__ == "__main__": unittest.main()
