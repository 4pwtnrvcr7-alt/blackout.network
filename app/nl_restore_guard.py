"""Guard for newsletter.db restores (Nov 24 2026, pt1847u).

After a Render restart the box may push its render_mirror/newsletter.db copy. That mirror can go stale
(it last refreshed Nov 9 while Render had newer signups). Never overwrite the live subscriber list with
an older or smaller copy. Comparison is read-only (file:?mode=ro) on both files; this module never writes
a subscriber row. Used by render_app._apply_tar when installing an "owned" newsletter.db (box restore or
deploy handoff). A missing or empty live file still accepts the copy (first boot / wiped disk).
"""
import os, sqlite3
from datetime import datetime, timezone

TS_COLS = ("updated", "created", "confirmed_at", "unsubscribed_at", "last_sent_at",
           "confirm_sent_at", "tracking_consent_at")

def _parse_ts(v):
    if not v: return None
    s = str(v).strip()
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    try: return datetime.fromisoformat(s)
    except Exception:
        return None

def stats(path):
    """Read-only: {rows, active, newest} for a newsletter.db. Missing or unreadable -> zeros (treat as empty)."""
    out = {"rows": 0, "active": 0, "newest": None, "newest_raw": ""}
    if not path or not os.path.exists(path): return out
    try:
        k = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=15)
        try:
            out["rows"] = int(k.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0])
            out["active"] = int(k.execute("SELECT COUNT(*) FROM subscribers WHERE status='active'").fetchone()[0])
            cols = {r[1] for r in k.execute("PRAGMA table_info(subscribers)")}
            use = [c for c in TS_COLS if c in cols]
            if use:
                union = " UNION ALL ".join(f"SELECT {c} AS t FROM subscribers WHERE {c} IS NOT NULL AND TRIM({c})!=''" for c in use)
                raw = k.execute(f"SELECT t FROM ({union})").fetchall()
                best, best_raw = None, ""
                for (t,) in raw:
                    p = _parse_ts(t)
                    if p is None: continue
                    if p.tzinfo is None: p = p.replace(tzinfo=timezone.utc)
                    if best is None or p > best: best, best_raw = p, str(t)
                out["newest"], out["newest_raw"] = best, best_raw
        finally:
            k.close()
    except Exception:
        return {"rows": 0, "active": 0, "newest": None, "newest_raw": ""}
    return out

def should_restore(live_path, incoming_path):
    """-> (ok, reason). ok=False means keep the live file and skip the incoming copy.

    Skip when the live list exists and is non-empty AND the copy has fewer active subscribers,
    fewer subscriber rows, or an older newest timestamp. Equal-or-better copies (deploy handoff
    from the still-running instance) are allowed.
    """
    live = stats(live_path)
    inc = stats(incoming_path)
    live_desc = f"live {live['active']} active/{live['rows']} rows, newest {live['newest_raw'] or 'none'}"
    inc_desc = f"copy {inc['active']} active/{inc['rows']} rows, newest {inc['newest_raw'] or 'none'}"
    if live["rows"] == 0 and live["active"] == 0:
        return True, f"no live subscriber list; installing the copy ({inc_desc})"
    why = []
    if inc["active"] < live["active"]:
        why.append(f"fewer active subscribers ({inc['active']} < {live['active']})")
    if inc["rows"] < live["rows"]:
        why.append(f"fewer subscriber rows ({inc['rows']} < {live['rows']})")
    if inc["newest"] is not None and live["newest"] is not None and inc["newest"] < live["newest"]:
        why.append(f"older (newest {inc['newest_raw']} < {live['newest_raw']})")
    if why:
        return False, "skipping restore of newsletter.db: copy is " + " and ".join(why) + f"; keeping the live list ({live_desc}; {inc_desc})"
    return True, f"copy is not older or smaller ({live_desc}; {inc_desc})"
