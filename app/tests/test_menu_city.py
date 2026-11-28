"""Nov 27 2026 (Matt pt1984u): menu city blackout + mesh animation. Run: cd app && python3 -m unittest tests.test_menu_city -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import menu5

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(APP, "static", "pwa", "bn-menu-city.js")

class MenuCity(unittest.TestCase):
    def test_menu_uses_canvas_not_svg(self):
        os.environ.pop("BN_MENU_CITY", None)
        h = menu5.html_block("/wire")
        self.assertIn('<canvas class="m5-art m5-city"', h)
        self.assertNotIn("m5a-sweep", h.split("</style>")[1].split("<script")[0])
        self.assertIn("/bn-menu-city.js?v=", h)
        self.assertNotIn("__CITYV__", h)
        for label in ("Intro", "The Wire", "Heat Map", "Weather", "The Grid", "Markets", "Comms", "Newsletter"):
            self.assertIn(label, h)
        self.assertIn("pointer-events:none", h)

    def test_kill_switch_restores_svg(self):
        os.environ["BN_MENU_CITY"] = "0"
        try:
            h = menu5.html_block("/wire")
            self.assertIn("m5a-sweep", h); self.assertNotIn("<canvas", h)
        finally:
            os.environ.pop("BN_MENU_CITY", None)

    def test_route_serves_script(self):
        import pwa, addons
        self.assertEqual(addons.ROUTES.get("/bn-menu-city.js") if hasattr(addons, "ROUTES") else "pwa", "pwa")
        code, body, ct = pwa.handle_get("/bn-menu-city.js", {})
        self.assertEqual((code, ct), (200, "application/javascript")); self.assertGreater(len(body), 10000)

    def test_script_rules(self):
        with open(JS, encoding="utf-8") as f:
            s = f.read()
        for needle in ("prefers-reduced-motion", "visibilitychange", "document.hidden", "devicePixelRatio", "Math.min(window.devicePixelRatio || 1, 2",
                       "GRID DOWN", "blackout.network activated", "requestAnimationFrame", "cancelAnimationFrame"):
            self.assertIn(needle, s)
        self.assertNotIn("NODES ", s)
        low = s.lower()
        for bad in ("meshtastic", "lora", "http://", "https://", "fetch(", "xmlhttprequest", "#ffc21a", "yellow"):
            self.assertNotIn(bad, low, bad)
        self.assertIsNone(re.search(r"\.(png|jpe?g|webp|gif|mp4)\b", low))
        self.assertNotIn("d.rotate(rot)", s)
        self.assertIn("bAng", s)

class MenuThumbLayout(unittest.TestCase):
    def test_actions_are_plain_text_at_top(self):
        h = menu5.html_block("/wire")
        body = h.split("</style>", 1)[1].split("<script", 1)[0]
        self.assertIn('class="m5-txt"', body)
        self.assertNotIn('class="m5-btn"', body)
        self.assertLess(body.find("m5-acts"), body.find("m5-nav"))
        self.assertIn("Install on home screen", body)
        self.assertIn("Turn on notifications", body)
        css = h.split("</style>", 1)[0]
        self.assertNotIn("border:1px solid rgba(255,255,255,.45)", css)
        self.assertIn("margin-top:auto", css)
        self.assertIn("flex-direction:column", css)

    def test_eight_links_stay_in_order(self):
        """#314 added Comms; the bottom stack must list all eight page links."""
        labels = ("Intro", "The Wire", "Heat Map", "Weather", "The Grid", "Markets", "Comms", "Newsletter")
        self.assertEqual([x[1] for x in menu5.ORDER], list(labels))
        h = menu5.html_block("/wire")
        body = h.split("</style>", 1)[1].split("<script", 1)[0]
        for label in labels:
            self.assertIn(">" + label + "</a>", body)
        self.assertEqual(body.count('<li class="m5-r"'), 8)

class MenuBlankShell(unittest.TestCase):
    """Matt 11:44 PM ET Nov 27: empty black menu (Alerts + Report status footer) after a tap."""

    def _js(self):
        return menu5.html_block("/wire").split("<script", 1)[1]

    def test_same_page_tap_closes_instead_of_sticking(self):
        js = self._js()
        self.assertIn("function m5shut()", js)
        self.assertIn("if(same){e.preventDefault();m5shut();return}", js)
        self.assertIn("window.bnMenuClose", js)

    def test_navigation_starts_immediately(self):
        """Do not wait 140-400ms after emptying the menu; that is the stuck shell."""
        js = self._js()
        self.assertIn("location.assign(u.pathname+u.search+u.hash)", js)
        self.assertNotIn("setTimeout(function(){location.href=a.href}", js)
        self.assertNotIn("RM?140:400", js)


class MenuChrome(unittest.TestCase):
    """Matt 12:32-12:33 AM ET Nov 28: drop ALERTS band, icon-only close, fill bottom gap."""

    def test_alerts_band_and_divider_hidden(self):
        css = menu5.html_block("/wire").split("</style>", 1)[0]
        self.assertIn("#bn-menu:has(.m5) .m3-alerts", css)
        self.assertIn("#bn-menu:has(.m5) .bn-ph", css)
        self.assertIn("#bn-menu:has(.m5) .m3-grid", css)
        self.assertIn("border-bottom:0", css)

    def test_close_is_icon_only(self):
        css = menu5.html_block("/wire").split("</style>", 1)[0]
        self.assertIn("#bn-menu:has(.m5) .bn-close span{display:none", css)
        self.assertIn("min-width:44px", css)
        self.assertIn("min-height:44px", css)

    def test_nav_sits_on_safe_area(self):
        css = menu5.html_block("/wire").split("</style>", 1)[0]
        self.assertIn("max(8px,env(safe-area-inset-bottom,0px))", css)
        self.assertNotIn("padding-bottom:max(20px,2vh)", css)
        self.assertNotIn("max(16px,env(safe-area-inset-bottom,0px))", css)

    def test_desktop_legacy_grid_hidden_so_stack_can_fill(self):
        css = menu5.html_block("/wire").split("</style>", 1)[0]
        self.assertIn("#bn-menu:has(.m5) .m3-grid", css)
        self.assertIn("flex:1 1 0%", css)


if __name__ == "__main__":
    unittest.main()
