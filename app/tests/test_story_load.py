"""story.load must work against the real clusters schema, which has no `hidden` column."""
import os, sqlite3, sys, tempfile, types, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# story.py imports site_page at module load; stub it for this isolated test.
if "site_page" not in sys.modules:
    S = types.ModuleType("site_page")
    S.clean_title = lambda t: t or ""
    S.page = lambda *a, **k: "page"
    S.E = lambda s: str(s or "")
    S.SITE = "https://blackout.network"
    S.BRAND = "BLACKOUT.NETWORK"
    sys.modules["site_page"] = S


SCHEMA = """
CREATE TABLE clusters(
  cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
  event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER,
  n_families INTEGER, families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT,
  rising INTEGER DEFAULT 0, mentions_3h INTEGER DEFAULT 0, eff_families INTEGER DEFAULT 0,
  rank INTEGER DEFAULT 0, pushed_at TEXT
);
CREATE TABLE alerts(
  id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT,
  event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT,
  first_seen TEXT, last_seen TEXT, cluster_id TEXT
);
"""

class LoadWithoutHiddenColumn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        c = sqlite3.connect(self.tmp.name)
        c.executescript(SCHEMA)
        c.execute(
            "INSERT INTO clusters(cluster_id,title,brief,rank,location,category,watchlist,confidence,families,n_items,first_seen,updated,event_time,lat,lon,links)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("dec0cddbd508e929", "Burnham launches inquiry", "UK Prime Minister Andy Burnham opened an inquiry.",
             6, "", "political", 0, "high", "news", 3, "2026-11-25T01:00:00Z", "2026-11-25T01:00:00Z",
             None, None, None, "[]"),
        )
        c.commit(); c.close()
        import story
        self._prev = story.DB
        story.DB = self.tmp.name

    def tearDown(self):
        import story
        story.DB = self._prev
        try: os.unlink(self.tmp.name)
        except OSError: pass

    def test_load_returns_row_when_clusters_has_no_hidden_column(self):
        import story
        cols = {r[1] for r in sqlite3.connect(story.DB).execute("PRAGMA table_info(clusters)")}
        self.assertNotIn("hidden", cols)
        # Asking for hidden must fail on this schema — the bug #217 shipped.
        c = sqlite3.connect(story.DB)
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("SELECT hidden FROM clusters").fetchone()
        c.close()
        row, alerts = story.load("dec0cddbd508e929")
        self.assertIsNotNone(row)
        self.assertEqual(row["cluster_id"], "dec0cddbd508e929")
        self.assertIn("Burnham", row["title"])
        self.assertEqual(alerts, [])

    def test_slim_select_does_not_ask_for_hidden(self):
        import story
        self.assertNotIn("hidden", story._LOAD_COLS)
        self.assertNotIn("hidden", story._LOAD_COLS_MIN)

    def test_known_held_item_is_not_treated_as_missing(self):
        import story
        r, al = story._known_row("dec0cddbd508e929")
        self.assertIsNotNone(r)
        self.assertEqual(r["cluster_id"], "dec0cddbd508e929")
        missing, _ = story._known_row("ffffffffffffffff")
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
