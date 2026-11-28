"""Global pill buttons (Matt, Nov 28 2026): every button-like control is fully rounded."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITENAV = (ROOT / "static" / "sitenav.css").read_text(encoding="utf-8")
THEME = (ROOT / "theme_static" / "theme.css").read_text(encoding="utf-8")
REFRESH = (ROOT / "static" / "bn-refresh.css").read_text(encoding="utf-8")

# Selectors that may keep a square radius (cards, fields, typography, map vendor, row headers).
_ALLOWED_SQUARE = re.compile(
    r"(\.pill\b|\.card\b|stale|select\b|textarea\b|input\[type=(text|search|email|password|number)"
    r"|\.hw-i\b|ul\.tl>li|\.sr-sec|\.sr-side|\.tl-hd\b|\.tl-search\b|\.tl-loc input|\.tl-fbadge\b"
    r"|maplibre|leaflet|\.bn-dsearch|\.bns-go\b|\.pn\b|banner)",
    re.I,
)


def _css_files():
    for p in ROOT.rglob("*.css"):
        if "maplibre" in p.name or "MarkerCluster" in p.name:
            continue
        yield p


class PillToken(unittest.TestCase):
    def test_token_is_9999px_on_sitenav(self):
        self.assertRegex(SITENAV, r"--bn-radius-pill\s*:\s*9999px")

    def test_global_rule_uses_the_token(self):
        for label, css in (("sitenav.css", SITENAV), ("theme_static/theme.css", THEME)):
            with self.subTest(sheet=label):
                self.assertIn("every button-like control is a pill", css)
                self.assertIn("border-radius:var(--bn-radius-pill, 9999px)!important", css)
                # core button-like selectors
                for sel in ("button", ".btn", "input[type=\"submit\"]", "input[type=\"button\"]",
                            "[role=\"button\"]", ".bn-ref", "#tl_ref", "a.bn-follow", ".bng-sb"):
                    self.assertIn(sel, css, f"{label} global rule missing {sel}")

    def test_excludes_map_vendor_and_row_headers_and_text_fields(self):
        # The shared rule itself must name the exclusions so a later sheet cannot
        # accidentally pill a Leaflet control or a Wire row header.
        self.assertIn(".leaflet-control *", SITENAV)
        self.assertIn(".maplibregl-ctrl-group *", SITENAV)
        self.assertIn(".tl-hd", SITENAV)
        self.assertIn(".wt-it>button", SITENAV)
        self.assertIn(".wt-it>button", THEME)
        self.assertIn(".bn-mrow", SITENAV)
        self.assertIn(".bns-go", SITENAV)
        # Story typography .pill stays an underline, not a capsule.
        self.assertIn("html body:has(#bn_story) .pill{border-radius:0!important}", SITENAV)
        self.assertIn("html body:has(#bn_story) .pill{border-radius:0!important}", THEME)


class RefreshPill(unittest.TestCase):
    def test_fill_and_clip_follow_the_pill(self):
        # all:unset would drop a later global radius, so the shared #293 button
        # must set overflow:hidden and the pill token in the same rule.
        m = re.search(r"\.bn-ref,#tl_ref\{([^}]+)\}", REFRESH)
        self.assertIsNotNone(m, ".bn-ref,#tl_ref rule missing")
        body = m.group(1)
        self.assertIn("overflow:hidden", body)
        self.assertRegex(body, r"border-radius\s*:\s*var\(--bn-radius-pill")


class NoSquareButtonOverrides(unittest.TestCase):
    def test_no_square_important_on_button_like_controls(self):
        rx = re.compile(r"border-radius\s*:\s*0\s*!important")
        hits = []
        for path in _css_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            # Walk rules
            parts = re.split(r"}", text)
            for part in parts:
                if "{" not in part or not rx.search(part):
                    continue
                sel, body = part.rsplit("{", 1)
                sel = re.sub(r"/\*.*?\*/", "", sel, flags=re.S)
                sel = re.sub(r"\s+", " ", sel).strip()
                if not sel or not rx.search(body):
                    continue
                if _ALLOWED_SQUARE.search(sel) or _ALLOWED_SQUARE.search(body):
                    continue
                if re.search(r"button|\.btn\b|chip|\[role=['\"]button['\"]\]|bng-sb|bng-btn|w2-btn|cta-btn|\.pri\b|bn-follow|bn-fbm|subscribe", sel, re.I):
                    rel = path.relative_to(ROOT)
                    hits.append(f"{rel}: {sel[:180]}")
        self.assertEqual(hits, [], "square !important still on button-like selectors:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
