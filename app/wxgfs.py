"""Global forecast precipitation and cloud cover for /weather (Nov 22 2026, pt1744u).

Source: NOAA GFS 1-degree forecast via the NOMADS grib filter (US government work, public domain, no key).
Only two fields are pulled per forecast hour (precipitation rate at the surface, total cloud cover), so one
forecast hour is ~250 KB. A pure-Python GRIB2 decoder (data representation template 5.3, complex packing with
spatial differencing, which is what GFS uses) turns them into 360 x 181 grids. The page gets two small greyscale
PNG "atlases" (precipitation rate on a log scale at 1 degree, cloud cover at 2 degrees) with every frame stacked vertically.
"""
import io, math, struct, threading, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (compatible; blackout.network weather map; +https://blackout.network/weather)"
NOMADS = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_1p00.pl"
NX, NY = 360, 181
STEP_H, MAX_H = 3, 168                       # every 3 hours out to 7 days
R_LO, R_HI = 0.05, 100.0                     # mm per hour, log-scaled into 1..255
_LR = math.log(R_HI / R_LO)

# ------------------------------------------------------------------ GRIB2 (template 5.3) decoder
def _bits(buf, pos, n, count):
    """count unsigned n-bit integers starting at bit pos. Returns (list, new_pos)."""
    out = []
    if n == 0: return [0] * count, pos
    mask = (1 << n) - 1
    fb = int.from_bytes
    for _ in range(count):
        i = pos >> 3; sh = pos & 7
        nb = (sh + n + 7) >> 3
        v = fb(buf[i:i + nb], "big")
        out.append((v >> (nb * 8 - sh - n)) & mask)
        pos += n
    return out, pos

def _smag(v, nbits):
    s = 1 << (nbits - 1)
    return -(v & (s - 1)) if v & s else v

def _sec(msg):
    """{section number: bytes} for one GRIB2 message (sections 1..7)."""
    out = {}; j = 16; end = len(msg) - 4
    while j < end:
        L = struct.unpack(">I", msg[j:j + 4])[0]; out.setdefault(msg[j + 4], msg[j:j + L]); j += L
    return out

def _decode(msg):
    s = _sec(msg)
    s3, s4, s5, s6, s7 = s[3], s[4], s[5], s[6], s[7]
    npts = struct.unpack(">I", s5[5:9])[0]
    tmpl = struct.unpack(">H", s5[9:11])[0]
    if tmpl != 3: raise ValueError(f"GRIB2 packing template {tmpl} is not supported")
    R = struct.unpack(">f", s5[11:15])[0]
    E = _smag(struct.unpack(">H", s5[15:17])[0], 16); D = _smag(struct.unpack(">H", s5[17:19])[0], 16)
    nb = s5[19]; miss = s5[22]
    NG = struct.unpack(">I", s5[31:35])[0]; wref = s5[35]; wbits = s5[36]
    lref = struct.unpack(">I", s5[37:41])[0]; linc = s5[41]; llast = struct.unpack(">I", s5[42:46])[0]; lbits = s5[46]
    order = s5[47]; ostep = s5[48]
    d = s7[5:]; pos = 0
    def sint(nby):
        nonlocal pos
        v = int.from_bytes(d[pos >> 3:(pos >> 3) + nby], "big"); pos += nby * 8
        return _smag(v, nby * 8)
    iv = [sint(ostep) for _ in range(order)]
    minsd = sint(ostep)
    refs, pos = _bits(d, pos, nb, NG); pos = (pos + 7) & ~7
    wid, pos = _bits(d, pos, wbits, NG); pos = (pos + 7) & ~7
    lns, pos = _bits(d, pos, lbits, NG); pos = (pos + 7) & ~7
    X = []; mv = []
    for g in range(NG):
        w = wref + wid[g]; L = lref + lns[g] * linc if g < NG - 1 else llast
        if w == 0:
            if miss and refs[g] == (1 << nb) - 1: X.extend([None] * L)
            else: X.extend([refs[g]] * L)
        else:
            vals, pos = _bits(d, pos, w, L); r = refs[g]; top = (1 << w) - 1
            if miss: X.extend([None if v == top else v + r for v in vals])
            else: X.extend([v + r for v in vals])
    # undo spatial differencing (skipping missing points)
    if order:
        idx = [k for k, v in enumerate(X) if v is not None]
        for k, j in enumerate(idx):
            if k < order: X[j] = iv[k]; continue
            if order == 1: X[j] = X[j] + minsd + X[idx[k - 1]]
            else: X[j] = X[j] + minsd + 2 * X[idx[k - 1]] - X[idx[k - 2]]
    sc = 2.0 ** E; dd = 10.0 ** -D
    vals = [None if v is None else (R + v * sc) * dd for v in X]
    if s6[5] == 0:   # bitmap present
        bm = s6[6:]; out = []; it = iter(vals)
        for k in range(struct.unpack(">I", s3[6:10])[0]):
            out.append(next(it) if bm[k >> 3] >> (7 - (k & 7)) & 1 else None)
        vals = out
    if len(vals) != NX * NY: raise ValueError("unexpected GFS grid size")
    return {"cat": s4[9], "num": s4[10], "tmpl": struct.unpack(">H", s4[7:9])[0], "vals": vals}

def _messages(b):
    i = 0
    while i + 16 <= len(b) and b[i:i + 4] == b"GRIB":
        tot = struct.unpack(">Q", b[i + 8:i + 16])[0]; yield b[i:i + tot]; i += tot

# ------------------------------------------------------------------ fetch + encode
def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read(8_000_000)

def _url(day, cyc, fh):
    return (f"{NOMADS}?dir=%2Fgfs.{day}%2F{cyc:02d}%2Fatmos&file=gfs.t{cyc:02d}z.pgrb2.1p00.f{fh:03d}"
            "&var_PRATE=on&var_TCDC=on&lev_surface=on&lev_entire_atmosphere=on")

def _fields(day, cyc, fh):
    b = _get(_url(day, cyc, fh))
    if b[:4] != b"GRIB": raise ValueError("NOMADS returned no GRIB data")
    pr = cl = None
    for m in _messages(b):
        f = _decode(m)
        if f["cat"] == 1 and f["num"] == 7 and (pr is None or f["tmpl"] == 0): pr = f["vals"]       # precipitation rate, kg m-2 s-1
        if f["cat"] == 6 and f["num"] == 1 and (cl is None or f["tmpl"] == 0): cl = f["vals"]       # total cloud cover, %
    return pr, cl

def _enc_rate(v):
    if v is None: return 0
    r = v * 3600.0
    if r < R_LO: return 0
    return max(1, min(255, int(round(1 + 254 * math.log(r / R_LO) / _LR))))

def _latest_cycle():
    """Newest GFS cycle whose 1-degree files are on NOMADS (they appear ~3.5-5 h after the cycle time)."""
    t = datetime.now(timezone.utc) - timedelta(hours=3, minutes=30)
    t = t.replace(hour=t.hour - t.hour % 6, minute=0, second=0, microsecond=0)
    for k in range(4):
        c = t - timedelta(hours=6 * k)
        day, cyc = c.strftime("%Y%m%d"), c.hour
        try:
            b = _get(_url(day, cyc, MAX_H), timeout=30)   # the last hour lands last, so it proves the run is complete
            if b[:4] == b"GRIB": return c, day, cyc
        except Exception: pass
        time.sleep(0.5)
    raise ValueError("no complete GFS run found on NOMADS")

P_MIN = 0.15        # mm per hour; lighter than this does not show on the map anyway (below ~10 dBZ)
P_Q, C_Q = 6, 20    # quantisation steps (code units) so the PNGs compress well

def build(pause=0.4):
    from PIL import Image
    run, day, cyc = _latest_cycle()
    hours = list(range(STEP_H, MAX_H + 1, STEP_H))   # f000 has no precipitation rate, so start at +3 h
    cmin = 1 + 254 * math.log(P_MIN / R_LO) / _LR
    times, prow, crow, bad = [], [], [], 0
    for fh in hours:
        time.sleep(pause)   # stay far below NOMADS' request limit
        try:
            pr, cl = _fields(day, cyc, fh)
        except Exception:
            try: time.sleep(2); pr, cl = _fields(day, cyc, fh)
            except Exception: bad += 1; continue
        if cl is None or pr is None: bad += 1; continue
        P = bytearray(NX * NY); C = bytearray(NX * NY)
        for k in range(NX * NY):
            # GFS grid: north to south, 0..359 E. The page wants west to east starting at 180 W.
            y, x = divmod(k, NX); src = y * NX + ((x + 180) % NX)
            c = _enc_rate(pr[src]); P[k] = 0 if c < cmin else c // P_Q * P_Q + P_Q // 2
            v = cl[src]; C[k] = 0 if v is None else max(0, min(255, int(round(v * 2.55))))
        prow.append(bytes(P)); crow.append(bytes(C))
        times.append((run + timedelta(hours=fh)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if not times: raise ValueError("GFS returned no usable forecast hours")
    n = len(times)
    pim = Image.frombytes("L", (NX, NY * n), b"".join(prow))
    cw, ch = NX // 2, NY // 2 + 1   # clouds at 2 degrees: they are soft anyway
    cim = Image.new("L", (cw, ch * n))
    for i, row in enumerate(crow):
        cim.paste(Image.frombytes("L", (NX, NY), row).resize((cw, ch), Image.BILINEAR), (0, ch * i))
    cim = cim.point(lambda v: min(255, int(round(v / C_Q)) * C_Q))
    def enc(im): o = io.BytesIO(); im.save(o, "PNG", optimize=True); return o.getvalue()
    pp, cp = enc(pim), enc(cim)
    meta = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "run": run.strftime("%Y-%m-%dT%H:%M:%SZ"), "times": times,
            "p": {"nx": NX, "ny": NY, "lat0": 90, "lon0": -180, "step": 1, "bytes": len(pp)},
            "c": {"nx": NX // 2, "ny": NY // 2 + 1, "lat0": 90, "lon0": -180, "step": 2, "bytes": len(cp)},
            "rate": {"lo": R_LO, "hi": R_HI}, "missing": bad, "source": "NOAA GFS 1-degree forecast (NOMADS)"}
    return meta, {"p": pp, "c": cp}

# ------------------------------------------------------------------ cache (refresh in the background, never block a page)
_LOCK = threading.Lock()
_STATE = {"meta": None, "png": None, "at": 0.0, "err": None, "busy": False, "tried": 0.0}
TTL = 3 * 3600

def _refresh():
    try:
        meta, png = build()
        with _LOCK: _STATE.update(meta=meta, png=png, at=time.time(), err=None)
    except Exception as ex:
        msg = f"the source answered HTTP {ex.code}" if isinstance(ex, urllib.error.HTTPError) else ("the source did not answer in time" if "timed out" in str(ex) else "the source could not be reached just now")
        with _LOCK: _STATE["err"] = msg
    finally:
        with _LOCK: _STATE["busy"] = False

def kick():
    with _LOCK:
        stale = time.time() - _STATE["at"] > TTL
        if not stale or _STATE["busy"] or time.time() - _STATE["tried"] < 300: return
        _STATE["busy"] = True; _STATE["tried"] = time.time()
    threading.Thread(target=_refresh, name="wxgfs", daemon=True).start()

def meta():
    kick()
    with _LOCK: return _STATE["meta"], _STATE["err"]

def png(kind):
    kick()
    with _LOCK: return (_STATE["png"] or {}).get(kind)
