"""Matt 7:39 AM ET Nov 28: /setup install + alerts page. Run: cd app && python3 -m unittest tests.test_setup_page -v"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import addons, growth, menu5, setup_page, sitenav_ui as UI

class SetupPage(unittest.TestCase):
    def _body(self):
        code, body, ct = setup_page.handle_get("/setup", {})
        self.assertEqual((code, ct), (200, "text/html"))
        return body.decode("utf-8") if isinstance(body, bytes) else body

    def test_route_and_content(self):
        self.assertEqual(addons.ROUTES.get("/setup"), "setup_page")
        body = self._body()
        # anchors the menu links to, and the working buttons
        self.assertIn('id="install"', body)
        self.assertIn('id="notifications"', body)
        self.assertIn('data-su="install"', body)
        self.assertIn('data-su="notify"', body)
        self.assertIn("Install App", body)
        self.assertIn("Turn On Alerts", body)
        for k in ("installApp", "showNotifyGuide", "enableAlerts"):
            self.assertIn(k, body)
        self.assertNotIn("peer-to-peer", body.lower())
        self.assertNotIn("peer to peer", body.lower())
        self.assertEqual(UI.refresh_mode("/setup"), "off")
        self.assertIn("/sitenav.css", body)
        self.assertIn('id="bn-menu"', body)
        self.assertEqual(body.count("<h1"), 1, "the site page head h1 must not double the hero h1")

    def test_redesign_sections_and_steps(self):
        body = self._body()
        for t in ("on your home screen", "What you get", "Know first.", "Rank 7 or higher", "Two or more sources",
                  "Add to Home Screen", "Install app", "iOS 16.4", "Chrome", "Edge", "Safari", "Firefox"):
            self.assertIn(t, body)
        for os_key in ("ios", "android", "desktop"):
            self.assertIn(f'data-os="{os_key}"', body)
            self.assertIn(f'id="su_p_{os_key}"', body)
        self.assertIn('role="tablist"', body)
        self.assertIn("detect()", body)                       # OS auto-detect
        self.assertIn("/api/new_high?mode=alert", body)       # sample notification is the real latest rank 7+ story
        self.assertIn("get(2)", body)                         # small 48 h window first, fetched lazily near the phone
        self.assertIn("Sample", body)                         # clearly labelled sample
        # features: only things that exist
        for href in ("/wire", "/map", "/weather", "/grid", "/markets", "/newsletter"):
            self.assertIn(f'href="{href}"', body)

    def test_images_licensed_lazy_and_no_maps(self):
        body = self._body()
        import intro_sx
        credited = " ".join(" ".join(r) for r in intro_sx.credit_rows())
        for f in (setup_page.HERO, setup_page.ALERT, setup_page.CLOSE):
            for name in f:
                self.assertIn(name, body)
        for bad in ("hero-d.jpg", "hero-m.jpg", "tvvid", "tvhero", "maps/", "satellite", "mapbox", "openstreetmap"):
            self.assertNotIn(bad, body.lower(), "no map or satellite imagery on /setup")
        self.assertIn('fetchpriority="high"', body)          # hero only
        self.assertEqual(body.count('fetchpriority="high"'), 1)
        self.assertGreaterEqual(body.count('loading="lazy"'), 4)
        self.assertIn("Image credits", body)

    def test_buttons_are_40px_pills_no_yellow(self):
        css = setup_page.CSS
        self.assertIn("height:40px", css)
        self.assertIn("border-radius:9999px", css)
        self.assertEqual(css.count("height:40px;min-height:40px"), 2)   # .su-btn and .su-tab
        low = css.lower()
        for y in ("yellow", "gold", "#ff0", "#fc0", "#ffd", "#fe0", "#f5c", "#ffc", "#facc"):
            self.assertNotIn(y, low)

    def test_sitemap_and_menu(self):
        self.assertIn("/setup", [p[0] for p in growth.STATIC_PAGES])
        hrefs = [h for _, _, h in menu5.ORDER]
        self.assertIn("/setup#install", hrefs)
        self.assertIn("/setup#notifications", hrefs)
