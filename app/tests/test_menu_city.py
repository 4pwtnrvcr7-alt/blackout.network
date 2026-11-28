"""Nov 27 2026: menu bump-style Earth loop (approved preview, shipped the same evening). Run: cd app && python3 -m unittest tests.test_menu_city -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import menu5

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(APP, "static", "pwa", "bn-menu-city.js")
PWA = os.path.join(APP, "static", "pwa")

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

    def test_route_serves_script_and_loops(self):
        import pwa, addons
        for path, ct, minlen in (
            ("/bn-menu-city.js", "application/javascript", 2000),
            ("/bn-menu-city-m.mp4", "video/mp4", 10000),
            ("/bn-menu-city-d.mp4", "video/mp4", 10000),
        ):
            self.assertEqual(addons.ROUTES.get(path), "pwa")
            code, body, got = pwa.handle_get(path, {})
            self.assertEqual((code, got), (200, ct), path)
            self.assertGreater(len(body), minlen, path)

    def test_script_rules(self):
        s = open(JS, encoding="utf-8").read()
        for needle in ("prefers-reduced-motion", "visibilitychange", "document.hidden", "devicePixelRatio",
                       "Math.min(window.devicePixelRatio || 1, 2",
                       "GRID DOWN", "blackout.network activated", "requestAnimationFrame", "cancelAnimationFrame",
                       "/bn-menu-city-m.mp4", "/bn-menu-city-d.mp4"):
            self.assertIn(needle, s)
        self.assertNotIn("NODES ", s)
        low = s.lower()
        for bad in ("meshtastic", "lora", "http://", "https://", "fetch(", "xmlhttprequest", "#ffc21a", "yellow"):
            self.assertNotIn(bad, low, bad)
        self.assertIsNone(re.search(r"\.(png|jpe?g|webp|gif)\b", low))

if __name__ == "__main__":
    unittest.main()
