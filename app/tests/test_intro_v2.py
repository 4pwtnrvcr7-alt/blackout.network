"""Intro v2 (spacex.com-style panels). Run: cd app && python3 -m unittest tests.test_intro_v2 -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import intro_v2, theme, menu5

class IntroV2(unittest.TestCase):
    def setUp(self): os.environ.pop("BN_INTRO_V2", None)

    def test_one_panel_per_menu_item_with_one_link(self):
        h = theme.home_page()
        keys = [k for k, _, _ in menu5.items() if k in intro_v2.PANELS]
        secs = re.findall(r'<section class="ix-p[^"]*" id="([a-z]+)"', h)
        self.assertEqual(len(secs), len(keys))
        for body in re.findall(r'<section class="ix-p.*?</section>', h, re.S):
            self.assertEqual(body.count('class="ix-cta"'), 1)
        self.assertIn('<span class="bnt-wm">blackout.network</span>', h)
        self.assertIn('id="bng_follow"', h)

    def test_kill_switch_restores_previous_intro(self):
        os.environ["BN_INTRO_V2"] = "0"
        try: self.assertNotIn('class="ix-p', theme.home_page())
        finally: os.environ.pop("BN_INTRO_V2", None)

    def test_media_exists_for_every_panel(self):
        m = os.path.join(os.path.dirname(theme.__file__), "theme_static", "media")
        names = os.listdir(m)
        for k, (pid, mk, *_r) in intro_v2.PANELS.items():
            for sfx in ("d.jpg", "m.jpg", "d.mp4", "m.mp4"):
                self.assertTrue(any(n.startswith(f"{mk}-{sfx}.b64") for n in names), f"{mk}-{sfx}")

    def test_no_yellow_outside_loader(self):
        css = open(os.path.join(intro_v2.STATIC, "intro.css"), encoding="utf-8").read()
        outside = "\n".join(l for l in css.splitlines() if ".ix-ld" not in l)
        self.assertNotRegex(outside, r"#FF[CDE][0-9A-F]{3}\b|#FFC21A|#FFE")

    def test_live_overlay_failure_is_hidden_not_faked(self):
        orig = intro_v2.BUILDERS
        try:
            intro_v2.BUILDERS = (("wire", lambda: (_ for _ in ()).throw(RuntimeError("x"))), ("brief", intro_v2._b_brief))
            intro_v2._C.update(t=0, v=None, good={})
            v = intro_v2._build()
            self.assertIsNone(v["wire"]); self.assertIn("wire", v["errors"]); self.assertTrue(v["brief"]["next"].endswith("Z"))
        finally:
            intro_v2.BUILDERS = orig; intro_v2._C.update(t=0, v=None)

    def test_scroll_rules_in_js(self):
        js = open(os.path.join(intro_v2.STATIC, "intro.js"), encoding="utf-8").read()
        self.assertIn("passive:true", js)
        self.assertNotIn("preventDefault();t.scrollIntoView({behavior:\"smooth\"", js)
        self.assertNotIn("wheel", js)

if __name__ == "__main__": unittest.main()
