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
    finally:
        d.close()
        s.close()
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
