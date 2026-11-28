"""Network Status menu and leftover hashes go to /grid (Nov 23 2026, pt1763u)."""
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
        self.assertEqual(rows["net"], ("The Grid", "/grid"))   # Nov 24 2026 (pt1795u): renamed, merged with The Grid
        html = sitenav.header_html("")
        self.assertIn('href="/grid"', html)
        self.assertNotIn("Network Status", html)
        self.assertNotIn("/live#network", html)
        self.assertNotIn('href="/#network"', html)
        self.assertNotIn('href="/#net"', html)
        self.assertNotIn('data-tab="net"', html)

    def test_hash_redirect_and_click_trap(self):
        js = _read("static", "sitenav.js")
        self.assertIn('(_hm==="network"||_hm==="net")', js)
        self.assertIn('location.replace("/grid"', js)
        self.assertIn('k==="net"||href==="/grid"', js)

    def test_other_entry_points(self):
        theme = _read("theme.py")
        self.assertIn('"/grid")', theme)
        self.assertNotIn("/live#network", theme)
        welcome = _read("welcome.py")
        self.assertIn('"/grid")', welcome)
        self.assertNotIn('"/#network"', welcome)
        apple = _read("apple_v1.py")
        self.assertIn('"/grid")', apple)
        js = _read("static", "bn-apple.js")
        self.assertIn('box.href="/grid"', js)
        self.assertIn('location.href="/grid"', js)
        self.assertNotIn("/live#network", js)
        self.assertNotIn("/#network", js)

    def test_provider_crumbs_point_at_the_board(self):
        for name in ("netpages.py", "netstarlink.py"):
            t = _read(name)
            self.assertIn('<a href="/grid">The Grid</a>', t, name)
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

    def test_follow_hover_inks_label_on_fine_pointers_only(self):
        """Desktop invert-hover used to leave span/svg at #F2F2F4 on a #F2F2F4 fill (contrast 1).
        Hover stays gated so a phone tap still follows the link on the first tap. No yellow."""
        apple = _read("static", "bn-apple.css")
        growth = _read("growth_static", "app.css")
        board = _read("netmap_static", "board.css")
        gate = "@media (hover:hover) and (pointer:fine)"
        ink = "color:#05060a!important;fill:currentColor"
        self.assertIn("html .bng-btn:hover span", apple)
        self.assertIn("html .bng-btn:hover svg", apple)
        self.assertIn("html .bng-foot .bng-btn:hover span", growth)
        self.assertIn("html .bng-foot .bng-btn:hover svg", growth)
        self.assertIn(".nb .bng-btn:hover span", board)
        self.assertIn(".nb .bng-btn:hover svg", board)
        for css, label in ((apple, "apple"), (growth, "growth"), (board, "board")):
            self.assertIn(gate, css, label)
            self.assertIn(ink, css, label)
            i = css.find(".bng-btn:hover span")
            self.assertGreaterEqual(i, 0, label)
            media = css.rfind(gate, 0, i)
            self.assertGreaterEqual(media, 0, f"{label} hover span is not after a fine-pointer gate")
            chunk = css[media:i+220]
            self.assertIn("#05060a", chunk, label)
            self.assertNotRegex(chunk, r"#FFC21A|#ffc21a|\byellow\b", label)
        pre, sep, post = board.partition(gate)
        self.assertTrue(sep, "board hover must be pointer-gated")
        self.assertNotIn(".nb .bng-btn:hover", pre)
        self.assertIn(".nb .bng-btn:hover span", post)
        self.assertIn('html:not([data-theme="light"]) .bng-btn span', apple)
        self.assertIn("color:#F2F2F4!important", apple)


if __name__ == "__main__":
    unittest.main()
