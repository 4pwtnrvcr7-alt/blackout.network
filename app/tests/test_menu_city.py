"""Nov 27 2026 (Matt pt1984u): menu city blackout + peer-to-peer animation. Run: cd app && python3 -m unittest tests.test_menu_city -v"""
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
        for label in ("Intro", "The Wire", "Heat Map", "Weather", "The Grid", "Markets", "Newsletter"):
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
        s = open(JS, encoding="utf-8").read()
        for needle in ("prefers-reduced-motion", "visibilitychange", "document.hidden", "devicePixelRatio", "Math.min(window.devicePixelRatio || 1, 2",
                       "GRID DOWN", "PEER-TO-PEER LINK ESTABLISHED", "requestAnimationFrame", "cancelAnimationFrame"):
            self.assertIn(needle, s)
        low = s.lower()
        for bad in ("meshtastic", "lora", "http://", "https://", "fetch(", "xmlhttprequest", "#ffc21a", "yellow"):
            self.assertNotIn(bad, low, bad)
        self.assertIsNone(re.search(r"\.(png|jpe?g|webp|gif|mp4)\b", low))

if __name__ == "__main__":
    unittest.main()
