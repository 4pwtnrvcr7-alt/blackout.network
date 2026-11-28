"""Nov 17 2026 (Matt 7:23 PM, "Ugly"): story brief in the SpaceX language. Run: cd app && python3 -m unittest tests.test_story_spacex -v"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import story_report as SR

class SpaceX(unittest.TestCase):
    def test_scale_is_thin_ticks_red_only_at_7(self):
        hi, mid = SR.scale(8), SR.scale(5)
        self.assertEqual(hi.count('class="sr-tk'), 11)
        self.assertIn("--mk:#FF3B3B", hi); self.assertNotIn("#FF3B3B", mid)
        self.assertNotIn("<rect", hi + mid)

    def test_snapshot_open_grid_no_green_no_icon(self):
        h = SR.snapshot(8, [{}] * 3, ["FAA"], 7)
        for bad in ("#3fa66a", "sr-snap\"", "<svg", "rx="): self.assertNotIn(bad, h)
        self.assertIn('class="sr-stats"', h); self.assertIn("Signal snapshot", h)

    def test_risk_colours_option_a(self):
        self.assertEqual(SR.risk(3)[1], "#8E8E93"); self.assertEqual(SR.risk(5)[1], "#E5E5EA"); self.assertEqual(SR.risk(8)[1], "#FF3B3B")

    def test_css_has_no_yellow_green(self):
        css = SR.CSS.lower()
        for bad in ("#ffc21a", "#3fa66a", "#c97b00"): self.assertNotIn(bad, css)

    def test_file_hero_shows_full_image_on_tablet_desktop(self):
        css = SR.CSS
        self.assertIn(".sr2 .sr-fig.sr-file img{", css)
        self.assertNotIn("object-fit:cover;object-position:50% 25%;max-height:380px", css)
        # The file-photo rule itself must contain, not cover, so portraits are not sliced.
        start = css.find(".sr2 .sr-fig.sr-file img{")
        end = css.find("}", start)
        rule = css[start:end+1]
        self.assertIn("object-fit:contain", rule)
        self.assertNotIn("object-fit:cover", rule)
        self.assertIn("object-position:50% 20%", rule)
        self.assertIn("max-height:min(70vh,720px)", rule)
        self.assertIn("@media(max-width:767px){.sr2 .sr-fig.sr-file img{", css)

if __name__ == "__main__":
    unittest.main()
