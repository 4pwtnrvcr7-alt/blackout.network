"""Heat Map always opens the full-screen /map (Matt 5:25 PM). Run: cd app && python3 -m unittest tests.test_heatmap_nav -v"""
import os, re, sys, types, unittest
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sitenav, sitenav_ui as UI, theme, welcome, apple_v1, signal_map, server, growth


def _js(name):
    return open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", name), encoding="utf-8").read()


class HeatMapNav(unittest.TestCase):
    def test_menu_heat_map_is_plain_map_link(self):
        html = UI.drawer(sitenav, active="")
        m = re.search(r'<a href="([^"]+)"([^>]*)>Heat Map</a>', html)
        self.assertIsNotNone(m, html)
        self.assertEqual(m.group(1), "/map")
        self.assertNotIn("data-tab", m.group(2))
        self.assertNotIn("live#heatmap", html)
        home_menu = theme._menu() if hasattr(theme, "_menu") else ""
        if not home_menu:
            from theme import home_page
            home_menu = home_page()
        self.assertIn('href="/map"', home_menu)
        self.assertRegex(home_menu, r'href="/map"[^>]*>Heat Map')
        self.assertNotIn("/live#heatmap", home_menu)

    def test_home_live_map_ctas_and_hash_go_to_map(self):
        h = theme.home_page()
        self.assertIn('href="/map">Live map</a>', h)
        self.assertIn('href="/map">Open the live map</a>', h)
        self.assertNotIn("/live#heatmap", h)
        self.assertNotIn("/#heatmap", h)
        self.assertIn("if(h==='#heatmap'||h==='#map'){location.replace('/map'", theme.HEAD_JS)

    def test_welcome_and_apple_and_signal_map(self):
        src = Path(welcome.__file__).read_text(encoding="utf-8")
        self.assertIn('("Heat Map", "/map")', src)
        self.assertNotIn("/#heatmap", src)
        apple = open(apple_v1.__file__, encoding="utf-8").read()
        self.assertNotIn("/#heatmap", apple)
        self.assertIn('"/map"', apple)
        page = signal_map.handle_get("/map", {})
        body = page[1] if isinstance(page[1], str) else page[1].decode("utf-8", "replace")
        self.assertNotIn("/live#heatmap", body)
        self.assertNotIn("Heat map tab", body)

    def test_sitenav_and_dashboard_redirect_hashes(self):
        js = _js("sitenav.js")
        self.assertIn('location.replace("/map"+location.search)', js)
        self.assertIn('k==="heatmap"||href==="/map"', js)
        self.assertIn('pending==="heatmap"||pending==="map"', js)
        dash = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard.html"), encoding="utf-8").read()
        self.assertIn('src="/cohesion.js"', dash)
        coh = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "cohesion.js"), encoding="utf-8").read()
        self.assertIn('location.replace("/map"', coh)
        self.assertIn('"heatmap"', coh)
        self.assertIn('"map"', coh)

    def test_heatmap_path_redirects_to_map(self):
        self.assertNotIn("heatmap", server.H.TAB_PATHS)
        hits = []
        class H:
            path = "/heatmap?x=1"
            def send_response(self, c): hits.append(("status", c))
            def send_header(self, k, v): hits.append((k, v))
            def end_headers(self): hits.append("end")
        H.not_found_page = server.H.not_found_page
        h = H()
        self.assertTrue(server.H.not_found_page(h, "/heatmap"))
        self.assertIn(("status", 302), hits)
        self.assertIn(("Location", "/map?x=1"), hits)
        for path, loc in (("/heat-map", "/map"), ("/heat_map", "/map"), ("/HEATMAP", "/map")):
            hits.clear(); h.path = path
            self.assertTrue(server.H.not_found_page(h, path), path)
            self.assertIn(("Location", loc), hits, path)


class FollowAndFooter(unittest.TestCase):
    def test_follow_html_is_spacex_band(self):
        html = growth.follow_html()
        self.assertIn('id="bng_follow"', html)
        self.assertIn('class="bng-foot"', html)
        self.assertIn('class="bng-follow-k"', html)
        self.assertIn(">Follow<", html)
        self.assertIn("Ranked, sourced alerts as they happen.", html)
        self.assertNotIn("Follow BLACKOUT.NETWORK", html)
        self.assertNotIn("class=\"card", html)
        self.assertNotIn("#c8102e", html)
        self.assertNotIn("bng-p", html)
        # email first, then X, then YouTube
        i_mail = html.find('href="/newsletter"')
        i_x = html.find("BlkoutNtw")
        i_yt = html.lower().find("youtube")
        self.assertTrue(0 <= i_mail < i_x < i_yt, (i_mail, i_x, i_yt))

    def test_growth_assets_match_band(self):
        js = open(os.path.join(os.path.dirname(growth.__file__), "growth_static", "app.js"), encoding="utf-8").read()
        css = open(os.path.join(os.path.dirname(growth.__file__), "growth_static", "app.css"), encoding="utf-8").read()
        self.assertIn('class="bng-follow-k"', js)
        self.assertIn("Ranked, sourced alerts as they happen.", js)
        self.assertNotIn("Follow BLACKOUT.NETWORK", js)
        self.assertIn("background:none!important", css)
        self.assertIn("border:1px solid #F2F2F4", css)
        self.assertNotRegex(css, r"\.bng-foot[^{]*\{[^}]*#c8102e")
        self.assertIn("footer.h-foot .bn-legal-links,footer.h-foot .bn-cred-link{display:contents}", css)
        self.assertIn(".w2-foot .bn-legal-links,.w2-foot .bn-cred-link{display:inline;font-size:12px", css)
        # Matt 5:43 PM: newsletter kicker is grey/white, never red
        self.assertIn(".bng-cta-k{", css)
        k = css.split(".bng-cta-k{",1)[1].split("}",1)[0]
        self.assertNotRegex(k, r"#ff4d5e|#c8102e|#FF4D|200,16,46")
        self.assertRegex(k, r"rgba\(240,240,250|#[89A-Fa-f][0-9A-Fa-f]{5}|#F2F2F4|#C9CDD3")


    def test_home_shows_follow_above_footer(self):
        h = theme.home_page()
        self.assertIn('id="bng_follow"', h)
        self.assertGreater(h.find('id="bng_follow"'), h.find("</main>"))
        self.assertGreater(h.find('class="h-foot"'), h.find('id="bng_follow"'))
        self.assertNotIn("/live#heatmap", h)
        css = open(os.path.join(os.path.dirname(theme.__file__), "theme_static", "home.css"), encoding="utf-8").read()
        self.assertNotRegex(css, r"body\.bnt-home \.bng-foot\{display:none")

    def test_wire_footer_css_merges_legal_line(self):
        css = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wire_v2_static", "wire2.css"), encoding="utf-8").read()
        self.assertIn(".w2-legal{font-size:12px;color:#7E848C;display:inline;margin:0}", css)
        self.assertIn(".w2-foot .bn-legal-links,.w2-foot .bn-cred-link{display:inline;font-size:12px", css)
