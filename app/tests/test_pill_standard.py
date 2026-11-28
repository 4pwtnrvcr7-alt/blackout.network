"""One shared pill standard (Matt, Nov 28 2026): same height, padding, type and border everywhere."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEETS = {
    "sitenav.css": (ROOT / "static" / "sitenav.css").read_text(encoding="utf-8"),
    "theme_static/theme.css": (ROOT / "theme_static" / "theme.css").read_text(encoding="utf-8"),
    "wire_v2_static/wire2.css": (ROOT / "wire_v2_static" / "wire2.css").read_text(encoding="utf-8"),
}


class PillStandard(unittest.TestCase):
    def test_tokens_and_rule_in_every_shared_sheet(self):
        for label, css in SHEETS.items():
            with self.subTest(sheet=label):
                self.assertIn("--bn-pill-h:40px", css)
                self.assertIn("--bn-pill-px:14px", css)
                self.assertIn("--bn-pill-fs:11px", css)
                self.assertIn("--bn-pill-ls:.14em", css)
                self.assertIn("height:var(--bn-pill-h)!important", css)
                for sel in (".bnt-btn", ".bng-btn", ".nx-more-btn", ".nx-f button", ".tl-b", ".bn-ref", "#tl_ref", "button.pri"):
                    self.assertIn(sel, css)

    def test_home_intro_button_uses_the_standard(self):
        # /  loads sitenav.css and /bnt/theme.css (not wire2.css); the intro's .sx-btn was 50px.
        for label in ("sitenav.css", "theme_static/theme.css"):
            with self.subTest(sheet=label):
                self.assertIn(".bnt-btn,.sx-btn,.bng-btn", SHEETS[label])

    def test_standard_rule_has_zero_specificity_selector_list(self):
        # :where() keeps page sheets with their own !important hide rules (specificity) in charge.
        for label, css in SHEETS.items():
            with self.subTest(sheet=label):
                self.assertIn(".bng-btn,.bng-sb", css)

    def test_round_icon_controls_share_one_size(self):
        for label, css in SHEETS.items():
            with self.subTest(sheet=label):
                self.assertIn(":where(.nx-b,.nx-x,.wx-b,.wx-x,.bnm-b,.wx-play){box-sizing:border-box!important;width:var(--bn-pill-h)!important", css)

    def test_refresh_fill_untouched(self):
        # The standard must not change how the shared Refresh fills or clips.
        for label, css in SHEETS.items():
            block = css[css.index("every button is the SAME pill"):]
            with self.subTest(sheet=label):
                self.assertNotIn("clip-path", block)
                self.assertNotIn("overflow", block)
                self.assertNotIn("--tl-ref-p", block)


if __name__ == "__main__":
    unittest.main()
