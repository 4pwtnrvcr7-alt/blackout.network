import os, sqlite3, tempfile, unittest
import handoff_db


class SlimCardsTest(unittest.TestCase):
    def test_slim_copy_keeps_choices_and_newest_blobs_within_budget(self):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "cards.db")
        k = sqlite3.connect(src)
        k.execute("PRAGMA journal_mode=WAL")
        k.executescript("""CREATE TABLE story_photos(cid TEXT PRIMARY KEY, src TEXT, credit TEXT, license TEXT, caption TEXT, kind TEXT,
                            label TEXT, link TEXT, jpg BLOB, none INTEGER DEFAULT 0, stored_at TEXT);
                           CREATE TABLE story_cards(cid TEXT PRIMARY KEY, png BLOB, v TEXT, src TEXT, built_at TEXT);
                           ALTER TABLE story_cards ADD COLUMN title_hash TEXT;
                           CREATE TABLE other(x INTEGER);""")
        mb = b"x" * (1024 * 1024)
        for i in range(10):
            k.execute("INSERT INTO story_photos VALUES(?,?,?,?,?,?,?,?,?,0,?)", (f"c{i}", f"https://s/{i}", "", "CC0", "", "", "", "", mb, f"2026-11-25T0{i}"))
            k.execute("INSERT INTO story_cards VALUES(?,?,?,?,?,?)", (f"c{i}", b"\x89PNG" + mb, "25M", f"https://s/{i}", f"2026-11-25T0{i}", "h"))
        k.execute("INSERT INTO other VALUES(7)")
        k.commit()   # left in WAL on purpose
        out = handoff_db.slim_cards_snapshot(src, d, 6.5)
        self.assertLess(os.path.getsize(out), 8 * 1024 * 1024)
        c = sqlite3.connect(out)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM story_photos").fetchone()[0], 10)
        jp = [r[0] for r in c.execute("SELECT cid FROM story_photos WHERE jpg IS NOT NULL ORDER BY cid")]
        self.assertEqual(jp, ["c4", "c5", "c6", "c7", "c8", "c9"])   # newest first, within budget
        self.assertEqual(c.execute("SELECT COUNT(*) FROM story_cards").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT x FROM other").fetchone()[0], 7)
        self.assertEqual(c.execute("PRAGMA quick_check").fetchone()[0], "ok")
        c.close(); k.close()

    def test_failed_slim_copy_leaves_nothing(self):
        d = tempfile.mkdtemp()
        with self.assertRaises(Exception):
            handoff_db.slim_cards_snapshot(os.path.join(d, "nope", "cards.db"), d, 10)
        self.assertEqual([f for f in os.listdir(d) if f.endswith(".db")], [])


if __name__ == "__main__":
    unittest.main()
