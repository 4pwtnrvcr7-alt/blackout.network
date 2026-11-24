"""U.S. grid-operator sections, rebuilt on the public node when the synced gridstatus.db lacks them (Nov 24 2026, Matt).
Why: the box -> Render sync scrubs owner-local strings from every outbound DB copy (render_sync.scrub_db) and drops a whole row on a match.
The 'eia' and 'sections' rows are long lists of megawatt numbers, so whenever one hourly value happens to equal a private 5-digit
string the row is dropped and /grid (The Grid) shows no U.S. operators until that hour ages out (about 40 h).
Fix: if those rows are missing, this module fetches the same keyless EIA-930 feed here (www.eia.gov/electricity/930-api) and runs the
same gridstatus.compute_sections() with the ODIN / NWS / SWPC rows that did sync. Cached 10 min (failures 2 min), one refresh at a time,
no threads, no writes, no keys. Box collector, scanner, scoring and the sync itself are untouched."""
import time, threading

TTL_OK, TTL_ERR = 600, 120
_C = {"t": 0.0, "v": None, "eia_ts": None, "err": None}
_L = threading.Lock()

def sections(G, conn=None):
    """Return (sections dict or None, eia fetch time ISO or None). G is the gridstatus module."""
    now = time.time()
    if _C["t"] and now - _C["t"] < (TTL_OK if _C["v"] else TTL_ERR): return _C["v"], _C["eia_ts"]
    if not _L.acquire(blocking=False): return _C["v"], _C["eia_ts"]      # someone else is refreshing: serve what we have
    try:
        try:
            eia = G.fetch_eia()
            odin = nws = swpc = None
            try:
                c = conn or G.gdb(ro=True)
                try:
                    odin, _ = G.sget(c, "odin", []); nws, _ = G.sget(c, "nws", []); swpc, _ = G.sget(c, "swpc", {})
                finally:
                    if conn is None: c.close()
            except Exception:
                pass
            try:
                cut = G.iso(G.now() - G.timedelta(hours=12))
                ga = [g for g in G.grid_matches() if (g.get("first_seen") or "") >= cut]
            except Exception:
                ga = []
            secs = G.compute_sections(eia or {}, odin or [], nws or [], swpc or {}, G.util_meta()["odin_eia"], ga)
            if not any(s.get("demand_mw") for s in secs.values()): raise ValueError("EIA-930 returned no demand")
            _C.update(t=time.time(), v=secs, eia_ts=G.iso(), err=None)
        except Exception as e:
            _C.update(t=time.time(), err=repr(e)[:200])
        return _C["v"], _C["eia_ts"]
    finally:
        _L.release()

def status():
    return {"cached": bool(_C["v"]), "age_s": round(time.time() - _C["t"]) if _C["t"] else None, "error": _C["err"]}
