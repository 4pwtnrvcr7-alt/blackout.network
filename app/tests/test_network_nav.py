"""Network Status menu and leftover hashes go to /network (Nov 23 2026, pt1763u)."""
import os, sys, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as fh:
        return fh.read()

class NetworkStatusNav(unittest.TestCase):
    def test_menu_links_the_status_board(self):
        import sitenav, sitenav_ui
        rows = {k: (l, h) for _, _, _, rs in sitenav_ui.menu3_sections(sitenav) for k, l, h in rs}
        self.assertEqual(rows["net"], ("The Grid", "/network"))   # Nov 24 2026 (pt1795u): renamed, merged with The Grid
        html = sitenav.header_html("")
        self.assertIn('href="/network"', html)
        self.assertNotIn("Network Status", html)
        self.assertNotIn("/live#network", html)
        self.assertNotIn('href="/#network"', html)
        self.assertNotIn('href="/#net"', html)
        self.assertNotIn('data-tab="net"', html)

    def test_hash_redirect_and_click_trap(self):
        js = _read("static", "sitenav.js")
        self.assertIn('(_hm==="network"||_hm==="net")', js)
        self.assertIn('location.replace("/network"', js)
        self.assertIn('k==="net"||href==="/network"', js)

    def test_other_entry_points(self):
        theme = _read("theme.py")
        self.assertIn('"/network")', theme)
        self.assertNotIn("/live#network", theme)
        welcome = _read("welcome.py")
        self.assertIn('"/network")', welcome)
        self.assertNotIn('"/#network"', welcome)
        apple = _read("apple_v1.py")
        self.assertIn('"/network")', apple)
        js = _read("static", "bn-apple.js")
        self.assertIn('box.href="/network"', js)
        self.assertIn('location.href="/network"', js)
        self.assertNotIn("/live#network", js)
        self.assertNotIn("/#network", js)

    def test_provider_crumbs_point_at_the_board(self):
        for name in ("netpages.py", "netstarlink.py"):
            t = _read(name)
            self.assertIn('<a href="/network">The Grid</a>', t, name)
            self.assertNotIn('href="/#net"', t, name)


class BriefButtonContrast(unittest.TestCase):
    def test_dark_mode_primary_matches_other_follow_buttons(self):
        css = _read("static", "bn-apple.css")
        self.assertNotIn(".bng-btn.bng-p span{color:#1D1D1F!important}", css)
        self.assertIn("bng-btn.bng-p", css)
        self.assertIn("color:#F2F2F4!important", css)
        js = _read("growth_static", "app.js")
        start = js.find("function btns(camp)")
        self.assertGreater(start, -1)
        chunk = js[start:start + 220]
        self.assertIn('class="bng-btn" href="/newsletter', chunk)
        self.assertNotIn("bng-p", chunk)
        board = _read("netmap_static", "board.css")
        self.assertIn(".nb .bng-btn", board)
        self.assertIn("color:#F2F2F4!important", board)

if __name__ == "__main__":
    unittest.main()
