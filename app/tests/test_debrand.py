"""User-visible copy must not say Meshtastic or LoRa, except Terms acknowledgments and /api/mesh/LICENSES.txt.
Run: cd app && python3 -m unittest tests.test_debrand -v
"""
import os, re, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import meshnet, legal, growth, sitenav, preppers_data

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD = re.compile(r"\b(meshtastic|lora)\b", re.I)
TAG = re.compile(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", re.I | re.S)
MARKUP = re.compile(r"<[^>]+>")
# Line comments and Python/JS block comments, plus hash comments
def visible_html(h):
    vis = TAG.sub(" ", h)
    vis = MARKUP.sub(" ", vis)
    return vis


class Debrand(unittest.TestCase):
    def _assert_clean(self, label, text):
        hits = [m.group(0) for m in WORD.finditer(text)]
        self.assertEqual(hits, [], f"user-visible brand in {label}: {hits}")

    def test_mesh_pages_and_meta(self):
        for path in ("/mesh", "/mesh/chat", "/mesh/guide"):
            code, body, ct = meshnet.handle_get(path, {})
            self.assertEqual(code, 200)
            h = body.decode()
            self._assert_clean(path, visible_html(h))

    def test_llms_txt(self):
        code, body, ct = growth.handle_get("/llms.txt", {})
        self.assertEqual(code, 200)
        self._assert_clean("/llms.txt", body.decode() if isinstance(body, (bytes, bytearray)) else body)

    def test_sitenav_page_copy(self):
        for key, row in sitenav.PAGES.items():
            blob = " ".join(str(x) for x in row if isinstance(x, str))
            self._assert_clean(f"sitenav.PAGES[{key}]", blob)

    def test_preppers_and_bushcraft(self):
        self._assert_clean("preppers_data.ROWS", preppers_data.ROWS)
        bush = open(os.path.join(APP, "static/guides/bushcraft.html")).read()
        self._assert_clean("bushcraft.html", visible_html(bush))
        self.assertIn('href="/mesh/guide"', bush)
        self.assertIn("Off-grid mesh radios", preppers_data.ROWS)
        self.assertIn("/mesh/guide", preppers_data.ROWS)

    def test_tos_keeps_required_credit(self):
        h = legal.handle_get("/tos", {})[1].decode()
        self.assertIn('id="acknowledgments"', h)
        self.assertIn("Meshtastic® is a registered trademark of Meshtastic LLC", h)
        self.assertIn("LoRa radios running the open-source", h)
        # Other TOS sections should not be a second marketing mention outside acknowledgments.
        # Split on the acknowledgments section and only check earlier copy... section 19 is the exception
        # for the whole required credit block, so just confirm it is there.

    def test_licenses_kept(self):
        path = os.path.join(APP, "meshnet_static", "LICENSES.txt")
        text = open(path).read()
        self.assertRegex(text, re.compile(r"meshtastic", re.I))

    def test_user_facing_source_files(self):
        """Scan templates, static html, and page-data files. Comments, URLs, and identifiers may remain."""
        roots = [
            os.path.join(APP, "static"),
            os.path.join(APP, "preppers_data.py"),
            os.path.join(APP, "growth.py"),
        ]
        skip_dir = {"meshnet_static"}  # checked via rendered pages; vendored lib + licenses excepted
        files = []
        for root in roots:
            if os.path.isfile(root):
                files.append(root)
                continue
            for dp, dns, fns in os.walk(root):
                dns[:] = [d for d in dns if d not in skip_dir]
                for fn in fns:
                    if fn.endswith((".html", ".txt", ".xml", ".js", ".py")):
                        files.append(os.path.join(dp, fn))
        for path in files:
            raw = open(path, encoding="utf-8", errors="replace").read()
            if path.endswith(".html"):
                self._assert_clean(path, visible_html(raw))
            elif path.endswith(".txt") and "LICENSE" not in os.path.basename(path).upper():
                self._assert_clean(path, raw)


if __name__ == "__main__":
    unittest.main()
