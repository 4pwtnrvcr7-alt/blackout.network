"""Consistent sqlite snapshot and install used by the Render deploy handoff.

The old instance snapshots each Render-owned DB (including cards.db) with the
sqlite backup API so WAL commits are included; the new instance installs that
copy and reopens any live cards.db writer on the new file.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile


def snapshot_sqlite(src_path, dest_dir):
    """Consistent copy of a sqlite DB (WAL inclusive), returned as a temp file path."""
    os.makedirs(dest_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest_dir, suffix=".db")
    os.close(fd)
    # Open read-write so uncheckpointed WAL commits are visible. A mode=ro
    # connection can miss WAL pages when it cannot take the shm write lock.
    ok = False
    try:   # Nov 25 2026: a failed snapshot must not leave its partial copy in /tmp (cards.db is ~600 MB)
        s = sqlite3.connect(src_path, timeout=20)
        d = sqlite3.connect(tmp)
        try:
            try:
                s.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
            s.backup(d)
            d.execute("PRAGMA journal_mode=DELETE")
            d.commit()
            ok = True
        finally:
            d.close()
            s.close()
    finally:
        if not ok:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return tmp


def slim_cards_snapshot(src_path, dest_dir, budget_mb):
    """Nov 25 2026 (Matt: a restart must not wipe our images): a cards.db copy that fits budget_mb.

    The full cards.db is 0.6-1.3 GB (built PNG cards are ~1 MB each), too big for the box mirror (BN_SYNC_MAX_MB)
    and slow for the deploy handoff. The copy keeps every table and every photo choice, the licensed photo JPEGs
    newest first, then the newest built PNG cards with what is left of the budget. Anything left out is rebuilt
    from its JPEG (or looked up again) by the boot photo rebuild, newest first. Returns a temp file path."""
    os.makedirs(dest_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest_dir, suffix=".db")
    os.close(fd)
    left = int(float(budget_mb) * 1024 * 1024)
    ok = False
    try:
        d = sqlite3.connect(tmp, timeout=20)
        try:
            d.execute("ATTACH DATABASE ? AS s", (src_path,))   # read-write attach: uncheckpointed WAL commits are visible
            objs = d.execute("SELECT type, name, sql FROM s.sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
                             "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END").fetchall()
            tables = [n for t, n, _ in objs if t == "table"]
            for t, n, sql in objs:
                if t == "table":
                    d.execute(sql)
            def cols(n):
                return [r[1] for r in d.execute(f'PRAGMA s.table_info("{n}")').fetchall()]
            for n in tables:
                if n in ("story_photos", "story_cards"):
                    continue
                d.execute(f'INSERT INTO main."{n}" SELECT * FROM s."{n}"')
            if "story_photos" in tables:
                c = cols("story_photos")
                sel = ", ".join("NULL" if x == "jpg" else f'"{x}"' for x in c)
                d.execute(f'INSERT INTO main.story_photos({", ".join(chr(34) + x + chr(34) for x in c)}) SELECT {sel} FROM s.story_photos')
                if "jpg" in c:
                    order = "stored_at" if "stored_at" in c else "rowid"
                    for cid, n in d.execute(f"SELECT cid, length(jpg) FROM s.story_photos WHERE jpg IS NOT NULL ORDER BY {order} DESC").fetchall():
                        if n and n <= left:
                            d.execute("UPDATE main.story_photos SET jpg=(SELECT jpg FROM s.story_photos WHERE cid=?) WHERE cid=?", (cid, cid))
                            left -= n
            if "story_cards" in tables:
                c = cols("story_cards")
                order = "built_at" if "built_at" in c else "rowid"
                for cid, n in d.execute(f"SELECT cid, length(png) FROM s.story_cards ORDER BY {order} DESC").fetchall():
                    if n and n <= left:
                        d.execute('INSERT OR REPLACE INTO main.story_cards SELECT * FROM s.story_cards WHERE cid=?', (cid,))
                        left -= n
            for t, n, sql in objs:
                if t != "table":
                    try:
                        d.execute(sql)
                    except Exception:
                        pass
            d.commit()
            d.execute("DETACH DATABASE s")
            d.execute("PRAGMA journal_mode=DELETE")
            ok = True
        finally:
            d.close()
    finally:
        if not ok:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return tmp


def install_sqlite(dest_path, tmp_path):
    """Atomically replace dest_path with a verified snapshot; drop stale WAL/SHM."""
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    try:
        c = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        c.close()
    except Exception:
        ok = False
    if not ok:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise ValueError(f"{os.path.basename(dest_path)}: failed sqlite quick_check")
    os.chmod(tmp_path, 0o644)
    os.replace(tmp_path, dest_path)
    for suf in ("-wal", "-shm"):
        try:
            os.unlink(dest_path + suf)
        except FileNotFoundError:
            pass
    reopen_cards(dest_path)


def reopen_cards(dest_path=""):
    """If this install replaced cards.db, reopen the in-process writer on the new file."""
    try:
        import story_photo
        if dest_path and os.path.abspath(dest_path) not in (
            os.path.abspath(story_photo._db_path()),
            os.path.abspath(os.path.join(os.path.dirname(story_photo._db_path()), "cards.db")),
        ) and os.path.basename(dest_path) != "cards.db":
            return
        story_photo.reopen()
    except Exception:
        pass


def err_is_timeout(ex):
    """True when a peer GET failed because the old instance was too busy to answer, not absent."""
    if isinstance(ex, TimeoutError):
        return True
    reason = getattr(ex, "reason", None)
    if isinstance(reason, TimeoutError):
        return True
    msg = str(ex).lower()
    if reason is not None:
        msg = msg + " " + str(reason).lower()
    return "timed out" in msg or "timeout" in msg


def allow_public_without_data(handoff):
    """Cold start may go public empty so the box can fill the node.

    A deploy that already saw a live peer must not: Render would cut over and the Wire would empty.
    """
    return not bool((handoff or {}).get("peer_boot"))
