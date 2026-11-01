#!/usr/bin/env python3
"""blackout.network — Solar–earthquake correlation lab: offline precompute.

EXPLORATORY ANALYSIS, NOT ESTABLISHED SCIENCE. Every number written to the output JSON is computed here
from public, keyless data; nothing is typed in by hand.

Inputs (cached under $SQ_DATA, default /workspace/solarquake_data; re-download with --fetch):
  * GFZ Potsdam definitive/nowcast Kp (3-hourly) since 1932   https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt
  * NOAA NCEI GOES XRS flare event reports 2010–2017 (legacy GOES-15 lists)
  * NOAA NCEI GOES-R XRS flare summaries (GOES-16 2017-02-09..2025-04-07, GOES-19 after), netCDF4
  * NOAA SWPC 7-day GOES flare list (fills the last few days)
  * USGS ComCat FDSN event API, M4.5+ worldwide, one request per calendar year
Outputs: app/solar_quake_data/solar_quake.json (stats + charts) and solar_quake_map.json (map points).

Needs numpy, scipy and netCDF4 (python3 -m venv venv && venv/bin/pip install numpy scipy netCDF4).
"""
import csv, glob, json, math, os, re, sys, time, urllib.request
from datetime import datetime, timezone, timedelta
import numpy as np
from scipy import stats

DATA = os.environ.get("SQ_DATA", "/workspace/solarquake_data")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "solar_quake_data")
START = datetime(2010, 1, 1, tzinfo=timezone.utc)
SEED = 20261031
NPERM = 4000
WIN_H = 72                       # impact window: 0–72 h after onset / flare peak
G1, G3 = 14 / 3, 20 / 3          # Kp 5- (G1) and Kp 7- (G3), NOAA scale thresholds in thirds
QUIET_H = 48                     # an onset needs 48 h without G1+ before it
DIPOLE = (80.65, -72.68)         # IGRF-13 (epoch 2020) north geomagnetic (dipole) pole, approx.
UA = "BlackoutNetwork-SolarQuakeLab/1.0 (research; contact via blackout.network)"
URLS = {
    "kp": "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt",
    "goes_legacy": "https://www.ngdc.noaa.gov/stp/space-weather/solar-data/solar-features/solar-flares/x-rays/goes/xrs/",
    "goes16": "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes16/l2/data/xrsf-l2-flsum_science/",
    "goes19": "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes19/l2/data/xrsf-l2-flsum_science/",
    "swpc7": "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json",
    "usgs": "https://earthquake.usgs.gov/fdsnws/event/1/query",
}

def utc(s): return datetime.fromisoformat(s.replace("Z", "+00:00"))
def hrs(d): return (d - START).total_seconds() / 3600.0
def et(d):
    from zoneinfo import ZoneInfo
    return d.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %Y %-I:%M %p %Z")

def get(url, path, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path, "wb") as fh: fh.write(r.read())
    time.sleep(1)

def fetch(now):
    os.makedirs(os.path.join(DATA, "usgs"), exist_ok=True); os.makedirs(os.path.join(DATA, "goes"), exist_ok=True)
    get(URLS["kp"], os.path.join(DATA, "kp_gfz.txt"))
    for y in list(range(2010, 2017)) + ["2017-ytd"]:
        p = os.path.join(DATA, "goes", f"goes-xrs-report_{y}.txt")
        if not os.path.exists(p): get(URLS["goes_legacy"] + f"goes-xrs-report_{y}.txt", p)
    for k in ("goes16", "goes19"):
        idx = urllib.request.urlopen(urllib.request.Request(URLS[k], headers={"User-Agent": UA}), timeout=60).read().decode()
        names = sorted(set(re.findall(r'href="(sci_xrsf-l2-flsum_g\d+_s\d+_e\d+_v[\d-]+\.nc)"', idx)))
        for p in glob.glob(os.path.join(DATA, "goes", f"sci_xrsf-l2-flsum_g{k[-2:]}_*.nc")):
            if os.path.basename(p) != names[-1]: os.remove(p)
        if not os.path.exists(os.path.join(DATA, "goes", names[-1])): get(URLS[k] + names[-1], os.path.join(DATA, "goes", names[-1]), 600)
    get(URLS["swpc7"], os.path.join(DATA, "goes", "swpc_flares_7d.json"))
    for y in range(2010, now.year + 1):
        p = os.path.join(DATA, "usgs", f"eq_{y}.csv")
        if os.path.exists(p) and y < now.year - 1: continue        # older years are stable; refresh the last two
        q = f"?format=csv&starttime={y}-01-01&endtime={y+1}-01-01&minmagnitude=4.5&orderby=time-asc&eventtype=earthquake"
        get(URLS["usgs"] + q, p)

# ------------------------------------------------------------------ loaders
def load_kp(end):
    t, kp, defin = [], [], []
    for ln in open(os.path.join(DATA, "kp_gfz.txt")):
        if ln.startswith("#") or not ln.strip(): continue
        f = ln.split()
        d = datetime(int(f[0]), int(f[1]), int(f[2]), tzinfo=timezone.utc)
        if d < START or d >= end: continue
        for i in range(8):
            v = float(f[7 + i]); t.append(d + timedelta(hours=3 * i)); kp.append(v if v >= 0 else np.nan); defin.append(int(f[-1]))
    return t, np.array(kp), np.array(defin)

def load_flares(end):
    out = []          # (peak datetime, class letter, class string, source)
    g16_start = datetime(2017, 2, 9, tzinfo=timezone.utc)
    rx = re.compile(r"^31777(\d{6})\s+(\d{4}) (\d{4}) (\d{4})\s.{20,40}?\s([ABCMX]) ?(\d{2,3})\s+(?:G\d\d|GOES)")
    for p in sorted(glob.glob(os.path.join(DATA, "goes", "goes-xrs-report_*.txt"))):
        if "modified" in p: continue
        for ln in open(p, errors="replace"):
            m = rx.match(ln)
            if not m: continue
            d = datetime.strptime(m.group(1), "%y%m%d").replace(tzinfo=timezone.utc)
            hh, mm = int(m.group(4)[:2]), int(m.group(4)[2:])
            if hh > 23: continue
            pk = d + timedelta(hours=hh, minutes=mm)
            if int(m.group(4)) < int(m.group(2)): pk += timedelta(days=1)      # peak after midnight
            if START <= pk < g16_start: out.append((pk, m.group(5), f"{m.group(5)}{int(m.group(6))/10:.1f}", "GOES-15 legacy report"))
    import netCDF4
    e0 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    g16_end = None
    for sat in ("16", "19"):
        fs = sorted(glob.glob(os.path.join(DATA, "goes", f"sci_xrsf-l2-flsum_g{sat}_*.nc")))
        if not fs: continue
        ds = netCDF4.Dataset(fs[-1]); st = ds.variables["status"][:]; cl = ds.variables["flare_class"][:]; tt = ds.variables["time"][:]
        for s, c, x in zip(st, cl, tt):
            if s != "EVENT_PEAK" or not c: continue
            pk = e0 + timedelta(seconds=float(x))
            if sat == "16":
                if pk < g16_start: continue
                g16_end = max(g16_end or pk, pk)
            elif g16_end and pk <= g16_end: continue
            out.append((pk, c[0], c, f"GOES-{sat} XRS flare summary"))
    last = max(f[0] for f in out)
    try:
        for r in json.load(open(os.path.join(DATA, "goes", "swpc_flares_7d.json"))):
            if r.get("max_time") and r.get("max_class"):
                pk = utc(r["max_time"])
                if pk > last and pk < end: out.append((pk, r["max_class"][0], r["max_class"], "NOAA SWPC 7-day list"))
    except Exception: pass
    out = [f for f in out if f[0] < end]
    out.sort(key=lambda f: f[0])
    return out

def load_quakes(end):
    rows = {}
    for p in sorted(glob.glob(os.path.join(DATA, "usgs", "eq_*.csv"))):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            try:
                d = utc(r["time"]); m = float(r["mag"]); la = float(r["latitude"]); lo = float(r["longitude"]); de = float(r["depth"] or 0)
            except Exception: continue
            if START <= d < end and m >= 4.5: rows[r["id"]] = (d, m, la, lo, de, r["place"], r["magType"])
    return sorted(rows.values(), key=lambda q: q[0])

# ------------------------------------------------------------------ physics helpers
def subsolar(dts):
    """Subsolar latitude/longitude (deg) for an array of datetimes (NOAA solar position approximation)."""
    jd = np.array([(d - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0 for d in dts])
    g = np.radians((357.529 + 0.98560028 * jd) % 360); q = (280.459 + 0.98564736 * jd) % 360
    L = np.radians((q + 1.915 * np.sin(g) + 0.020 * np.sin(2 * g)) % 360); e = np.radians(23.439 - 0.00000036 * jd)
    dec = np.degrees(np.arcsin(np.sin(e) * np.sin(L)))
    ra = np.degrees(np.arctan2(np.cos(e) * np.sin(L), np.cos(L))) % 360
    gmst = (280.46061837 + 360.98564736629 * jd) % 360
    lon = ((ra - gmst + 180) % 360) - 180
    return dec, lon

def cos_zenith(lat, lon, slat, slon):
    la, lo, sa, so = map(np.radians, (lat, lon, slat, slon))
    return np.sin(la) * np.sin(sa) + np.cos(la) * np.cos(sa) * np.cos(lo - so)

def mag_lat(lat, lon):
    pl, po = map(np.radians, DIPOLE); la, lo = np.radians(lat), np.radians(lon)
    return np.degrees(np.arcsin(np.sin(la) * np.sin(pl) + np.cos(la) * np.cos(pl) * np.cos(lo - po)))

def haversine_km(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.minimum(1, a)))

def gardner_knopoff(t_days, mag, lat, lon):
    """Gardner & Knopoff (1974) space–time windows. Returns boolean mask of mainshocks (True = keep)."""
    n = len(mag); keep = np.ones(n, bool); done = np.zeros(n, bool)
    order = np.argsort(-mag, kind="stable")
    for i in order:
        if done[i]: continue
        m = mag[i]; dkm = 10 ** (0.1238 * m + 0.983)
        dt = 10 ** (0.032 * m + 2.7389) if m >= 6.5 else 10 ** (0.5409 * m - 0.547)
        lo_i, hi_i = np.searchsorted(t_days, t_days[i] - dt), np.searchsorted(t_days, t_days[i] + dt, "right")
        idx = np.arange(lo_i, hi_i); idx = idx[(idx != i) & ~done[idx]]
        if len(idx):
            close = idx[haversine_km(lat[i], lon[i], lat[idx], lon[idx]) <= dkm]
            keep[close] = False; done[close] = True
        done[i] = True
    return keep

def rr_ci(a, ta, b, tb, conf=0.95):
    """Rate ratio (a/ta)/(b/tb) with exact conditional (Clopper–Pearson) CI and exact two-sided p."""
    n = a + b
    if n == 0 or ta == 0 or tb == 0: return None, None, None, None
    ci = stats.binomtest(int(a), int(n), ta / (ta + tb)).proportion_ci(conf, method="exact")
    f = lambda p: (p / (1 - p)) * (tb / ta) if p < 1 else float("inf")
    p0 = stats.binomtest(int(a), int(n), ta / (ta + tb)).pvalue
    return (a / ta) / (b / tb), f(ci.low), f(ci.high), p0

def mc_maxc(m):
    """Completeness magnitude: maximum curvature + 0.2 (Wiemer & Wyss 2000 correction)."""
    bins = np.round(m, 1); u, c = np.unique(bins, return_counts=True)
    return round(float(u[np.argmax(c)]) + 0.2, 1)

def bvalue(m, mc, dm=0.1):
    m = m[m >= mc - 1e-9]
    if len(m) < 30: return None, None, len(m)
    b = math.log10(math.e) / (m.mean() - (mc - dm / 2))
    return b, b / math.sqrt(len(m)), len(m)          # Aki (1965) MLE with Utsu binning correction; Aki SE

def holm(ps):
    idx = sorted(range(len(ps)), key=lambda i: ps[i]); out = [None] * len(ps); run = 0
    for r, i in enumerate(idx):
        run = max(run, min(1.0, ps[i] * (len(ps) - r))); out[i] = run
    return out

def bh(ps):
    n = len(ps); idx = sorted(range(n), key=lambda i: ps[i]); out = [None] * n; run = 1.0
    for r in range(n - 1, -1, -1):
        i = idx[r]; run = min(run, ps[i] * n / (r + 1)); out[i] = min(1.0, run)
    return out

def R(x, n=4):
    if x is None: return None
    if isinstance(x, (float, np.floating)):
        if not np.isfinite(x): return None
        return float(round(float(x), n))
    return x

# ------------------------------------------------------------------ main
def main():
    now = datetime.now(timezone.utc)
    if "--fetch" in sys.argv: fetch(now)
    rng = np.random.default_rng(SEED)
    kp_t, kp, kp_def = load_kp(datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1))
    # analysis end = last complete Kp 3-h interval (no NaN tail)
    good = np.where(np.isfinite(kp))[0]; nb = int(good[-1]) + 1
    END = kp_t[nb - 1] + timedelta(hours=3)
    kp, kp_def, kp_t = kp[:nb], kp_def[:nb], kp_t[:nb]
    kp = np.where(np.isfinite(kp), kp, 0.0)
    flares = load_flares(END)
    Q = load_quakes(END)
    qt = np.array([hrs(q[0]) for q in Q]); qm = np.array([q[1] for q in Q]); qla = np.array([q[2] for q in Q]); qlo = np.array([q[3] for q in Q])
    mc = mc_maxc(qm)
    print(f"Kp bins {nb} ({kp_t[0]}..{END}); flares {len(flares)}; quakes M4.5+ {len(Q)}; Mc(maxc+0.2)={mc}", file=sys.stderr)

    # completeness: analysis set M >= max(mc, 5.0) is the primary; declustered with Gardner–Knopoff on the full M4.5+ catalog
    MMIN = max(mc, 5.0)
    keep_gk = gardner_knopoff(qt / 24.0, qm, qla, qlo)
    sets = {"raw": qm >= MMIN - 1e-9, "declustered": (qm >= MMIN - 1e-9) & keep_gk}
    print({k: int(v.sum()) for k, v in sets.items()}, file=sys.stderr)

    qbin = np.floor(qt / 3).astype(int)
    counts = {k: np.bincount(qbin[v], minlength=nb)[:nb].astype(float) for k, v in sets.items()}

    # ---- storm masks / onsets
    g1 = kp >= G1 - 1e-6; g3 = kp >= G3 - 1e-6
    def onsets(mask):
        out = []; last = -10**9
        for i in np.where(mask)[0]:
            if i - last > QUIET_H // 3 and not mask[max(0, i - QUIET_H // 3):i].any(): out.append(i)
            last = i
        return np.array(out, int)
    on1, on3 = onsets(g1), onsets(g3)
    fl_h = np.array([hrs(f[0]) for f in flares]); fl_c = np.array([f[1] for f in flares])
    xbins = np.unique(np.floor(fl_h[fl_c == "X"] / 3).astype(int))
    def win_mask(starts, nbins=WIN_H // 3):
        m = np.zeros(nb, bool)
        for s in starts: m[s:s + nbins] = True
        return m
    masks = {"g1_bins": g1, "g3_bins": g3, "g1_onset72": win_mask(on1), "g3_onset72": win_mask(on3), "x_flare72": win_mask(xbins)}
    labels = {"g1_bins": "3-hour intervals with Kp ≥ 5− (G1+ storm in progress)",
              "g3_bins": "3-hour intervals with Kp ≥ 7− (G3+ strong storm in progress)",
              "g1_onset72": "0–72 h after each G1+ storm onset (impact window)",
              "g3_onset72": "0–72 h after each G3+ storm onset (impact window)",
              "x_flare72": "0–72 h after each X-class flare peak"}

    # circular shifts shared by every test (≥ 60 days away from zero shift so windows never overlap themselves)
    shifts = rng.integers(60 * 8, nb - 60 * 8, NPERM)
    tests = []
    rate = {}
    for key, M in masks.items():
        rate[key] = {}
        for sk, C in counts.items():
            a, ta = C[M].sum(), M.sum() * 3 / 24; b, tb = C[~M].sum(), (~M).sum() * 3 / 24
            rr, lo, hi, pp = rr_ci(a, ta, b, tb)
            tot = C.sum(); obs = a / ta / ((tot - a) / tb)
            null = np.empty(NPERM)
            for j, s in enumerate(shifts):
                Ms = np.roll(M, s); aa = C[Ms].sum(); null[j] = (aa / ta) / ((tot - aa) / tb)
            p_perm = (1 + np.sum(np.abs(np.log(null)) >= abs(math.log(obs)) - 1e-12)) / (NPERM + 1)
            rate[key][sk] = {"quakes_in": int(a), "days_in": R(ta, 2), "quakes_out": int(b), "days_out": R(tb, 2),
                             "rate_in_per_day": R(a / ta, 3), "rate_out_per_day": R(b / tb, 3), "rr": R(rr), "ci_low": R(lo), "ci_high": R(hi),
                             "p_poisson": R(pp, 6), "p_perm": R(p_perm, 5), "null_rr_2_5": R(np.percentile(null, 2.5)), "null_rr_97_5": R(np.percentile(null, 97.5)),
                             "pct_change": R((rr - 1) * 100, 2)}
            tests.append({"id": f"rate:{key}:{sk}", "family": "rate", "set": sk, "label": labels[key], "p": p_perm, "p_analytic": R(pp, 6)})

    # ---- daily series + lag cross-correlation (solar leads quakes by 0..10 days)
    nd = nb // 8
    kpd = kp[:nd * 8].reshape(nd, 8).max(1)
    fd = {L: np.bincount(np.floor(fl_h[fl_c == L] / 24).astype(int), minlength=nd)[:nd] for L in "CMX"}
    qd = {k: C[:nd * 8].reshape(nd, 8).sum(1) for k, C in counts.items()}
    mom = np.zeros(nd); qday = np.floor(qt / 24).astype(int); sel = sets["raw"] & (qday < nd)
    np.add.at(mom, qday[sel], 10 ** (1.5 * qm[sel] + 9.1))
    def anom(x, w=81):
        k = np.ones(w) / w; p = np.pad(x.astype(float), (w // 2, w // 2), mode="edge"); return x - np.convolve(p, k, "valid")
    LAGS = list(range(0, 11))
    def xcorr(a, b):
        a, b = anom(a), anom(b); out = []
        for L in LAGS:
            x, y = a[:nd - L], b[L:]; out.append(float(np.corrcoef(x, y)[0, 1]))
        return np.array(out)
    lagres = {}
    dshift = rng.integers(365, nd - 365, 1000)
    for sk in counts:
        for nm, sol in (("kp_max", kpd), ("flares_mx", fd["M"] + fd["X"])):
            r = xcorr(sol, qd[sk]); mx = np.max(np.abs(r))
            null = np.array([np.max(np.abs(xcorr(np.roll(sol, s), qd[sk]))) for s in dshift])
            p = (1 + np.sum(null >= mx - 1e-12)) / (len(dshift) + 1)
            n_eff = nd
            lagres[f"{nm}:{sk}"] = {"lags": LAGS, "r": [R(v) for v in r], "max_abs_r": R(mx), "best_lag": int(LAGS[int(np.argmax(np.abs(r)))]),
                                   "null95_max_abs_r": R(np.percentile(null, 95)), "p_family": R(p, 4), "n_days": int(n_eff)}
            tests.append({"id": f"lag:{nm}:{sk}", "family": "lag", "set": sk, "label": f"Lag correlation 0–10 d, {'daily max Kp' if nm=='kp_max' else 'daily M+X flare count'} vs daily quake count", "p": p})

    # ---- superposed epoch around G1+ and G3+ onsets (daily counts, −10..+10 d)
    def sea(on_bins, C):
        offs = range(-10, 11); res = []
        for o in offs:
            v = [C[s + o * 8: s + o * 8 + 8].sum() for s in on_bins if 0 <= s + o * 8 and s + o * 8 + 8 <= nb]
            res.append(np.mean(v) if v else np.nan)
        return np.array(res)
    seares = {}
    for nm, on in (("g1", on1), ("g3", on3)):
        for sk, C in counts.items():
            obs = sea(on, C)
            nulls = np.array([sea((on + s) % (nb - 8), C) for s in shifts[:500]])
            seares[f"{nm}:{sk}"] = {"days": list(range(-10, 11)), "mean": [R(v, 3) for v in obs], "null_lo": [R(v, 3) for v in np.percentile(nulls, 2.5, 0)],
                                    "null_hi": [R(v, 3) for v in np.percentile(nulls, 97.5, 0)], "null_mean": [R(v, 3) for v in nulls.mean(0)],
                                    "baseline_per_day": R(C.sum() / (nb / 8), 3), "n_events": int(len(on))}

    # ---- geometry: day/night + latitude bands for quakes inside G1+ onset windows
    geo = {}
    on_dt = [START + timedelta(hours=3 * int(s)) for s in on1]
    ss_lat_on, ss_lon_on = subsolar(on_dt)
    qdt = [q[0] for q in Q]
    sq_lat, sq_lon = subsolar(qdt)
    day_own = cos_zenith(qla, qlo, sq_lat, sq_lon) > 0           # sunlit at the quake's own time
    mlat = mag_lat(qla, qlo)
    GB = [0, 15, 30, 45, 60, 90]; gbl = ["0–15°", "15–30°", "30–45°", "45–60°", "60–90°"]
    def band(x): return np.clip(np.digitize(np.abs(x), GB[1:-1]), 0, 4)
    gband, mband = band(qla), band(mlat)
    on_h = on1 * 3.0
    def window_assign(onh):
        """index of the most recent onset (within 72 h) for every quake, −1 if none."""
        k = np.searchsorted(onh, qt, "right") - 1
        ok = (k >= 0) & (qt - onh[np.maximum(k, 0)] < WIN_H)
        return np.where(ok, k, -1)
    for sk, S in sets.items():
        w = window_assign(on_h); inw = (w >= 0) & S; out = (w < 0) & S
        # (a) day/night at the quake's own time vs the out-of-window baseline
        n_in, d_in = int(inw.sum()), int(day_own[inw].sum()); p_base = day_own[out].mean()
        bt = stats.binomtest(d_in, n_in, p_base)
        # (b) side facing the Sun AT IMPACT TIME (subsolar point of the onset), permutation null by shifting onsets
        def impact_day_frac(onh, ssla, sslo):
            ww = window_assign(onh); ii = (ww >= 0) & S
            return cos_zenith(qla[ii], qlo[ii], ssla[ww[ii]], sslo[ww[ii]]) > 0, ii
        dd, _ = impact_day_frac(on_h, ss_lat_on, ss_lon_on); obs_f = dd.mean()
        null = []
        for s in shifts[:600]:
            oh = np.sort((on_h + s * 3.0) % (nb * 3.0 - WIN_H))
            sla, slo = subsolar([START + timedelta(hours=float(h)) for h in oh])
            f, _ = impact_day_frac(oh, sla, slo); null.append(f.mean())
        null = np.array(null); p_imp = (1 + np.sum(np.abs(null - null.mean()) >= abs(obs_f - null.mean()) - 1e-12)) / (len(null) + 1)
        # (c) latitude bands vs baseline proportions (chi-square goodness of fit)
        def chi(bands):
            oi = np.bincount(bands[inw], minlength=5).astype(float); ob = np.bincount(bands[out], minlength=5).astype(float)
            exp = ob / ob.sum() * oi.sum(); ch = stats.chisquare(oi, exp)
            return {"bands": gbl, "observed": [int(x) for x in oi], "expected": [R(x, 1) for x in exp],
                    "obs_pct": [R(x / oi.sum() * 100, 1) for x in oi], "base_pct": [R(x / ob.sum() * 100, 1) for x in ob], "chi2": R(ch.statistic, 3), "p": R(ch.pvalue, 5), "df": 4}
        cg, cm = chi(gband), chi(mband)
        # (d) magnitude distribution shift
        ks = stats.ks_2samp(qm[inw], qm[out])
        b_in, se_in, n_bi = bvalue(qm[inw], MMIN); b_out, se_out, n_bo = bvalue(qm[out], MMIN)
        z = (b_in - b_out) / math.sqrt(se_in ** 2 + se_out ** 2); p_b = 2 * stats.norm.sf(abs(z))
        # permutation p-values for every geometry/magnitude statistic (aftershocks make the analytic tests anti-conservative)
        def stat_vec(ww):
            ii = (ww >= 0) & S; oo = (ww < 0) & S
            dfr = day_own[ii].mean() - day_own[oo].mean()
            def c2(bands):
                oi = np.bincount(bands[ii], minlength=5).astype(float); ob = np.bincount(bands[oo], minlength=5).astype(float)
                ex = ob / ob.sum() * oi.sum(); return float(((oi - ex) ** 2 / ex).sum())
            bi, si, _ = bvalue(qm[ii], MMIN); bo, so, _ = bvalue(qm[oo], MMIN)
            return np.array([abs(dfr), c2(gband), c2(mband), stats.ks_2samp(qm[ii], qm[oo]).statistic, abs((bi - bo) / math.sqrt(si ** 2 + so ** 2))])
        obs_v = stat_vec(w)
        nv = np.array([stat_vec(window_assign(np.sort((on_h + s * 3.0) % (nb * 3.0 - WIN_H)))) for s in shifts[:600]])
        pv = (1 + (nv >= obs_v - 1e-12).sum(0)) / (len(nv) + 1)
        perm = {"day_own": pv[0], "geo_lat": pv[1], "mag_lat": pv[2], "ks": pv[3], "bval": pv[4]}
        cg["p_perm"] = R(pv[1], 4); cm["p_perm"] = R(pv[2], 4)
        geo[sk] = {"n_in": n_in, "n_out": int(out.sum()),
                   "day_own": {"in_day": d_in, "in_pct": R(d_in / n_in * 100, 2), "base_pct": R(p_base * 100, 2), "p_binom": R(bt.pvalue, 5), "p_perm": R(perm["day_own"], 4),
                               "ci_low_pct": R(bt.proportion_ci(0.95).low * 100, 2), "ci_high_pct": R(bt.proportion_ci(0.95).high * 100, 2)},
                   "day_impact": {"in_pct": R(obs_f * 100, 2), "null_mean_pct": R(null.mean() * 100, 2), "null_lo_pct": R(np.percentile(null, 2.5) * 100, 2),
                                  "null_hi_pct": R(np.percentile(null, 97.5) * 100, 2), "p_perm": R(p_imp, 4), "n": int(len(dd))},
                   "geo_lat": cg, "mag_lat": cm,
                   "mag": {"ks_D": R(ks.statistic), "ks_p": R(ks.pvalue, 5), "mean_in": R(qm[inw].mean(), 3), "mean_out": R(qm[out].mean(), 3),
                           "b_in": R(b_in, 3), "b_in_se": R(se_in, 3), "b_out": R(b_out, 3), "b_out_se": R(se_out, 3), "b_z": R(z, 3), "b_p": R(p_b, 5), "ks_p_perm": R(perm["ks"], 4), "b_p_perm": R(perm["bval"], 4)}}
        tests += [{"id": f"daynight_own:{sk}", "family": "geometry", "set": sk, "label": "Day vs night (sunlit at the quake's own time) in G1+ impact windows", "p": perm["day_own"], "p_analytic": R(bt.pvalue, 6)},
                  {"id": f"daynight_impact:{sk}", "family": "geometry", "set": sk, "label": "Side facing the Sun at the impact time (G1+ onsets)", "p": p_imp},
                  {"id": f"geolat:{sk}", "family": "geometry", "set": sk, "label": "Geographic latitude bands, impact windows vs baseline", "p": perm["geo_lat"], "p_analytic": cg["p"]},
                  {"id": f"maglat:{sk}", "family": "geometry", "set": sk, "label": "Geomagnetic (dipole) latitude bands, impact windows vs baseline", "p": perm["mag_lat"], "p_analytic": cm["p"]},
                  {"id": f"ks:{sk}", "family": "magnitude", "set": sk, "label": "Magnitude distribution (KS test), impact windows vs baseline", "p": perm["ks"], "p_analytic": R(ks.pvalue, 6)},
                  {"id": f"bval:{sk}", "family": "magnitude", "set": sk, "label": "Gutenberg–Richter b-value, impact windows vs baseline", "p": perm["bval"], "p_analytic": R(p_b, 6)}]

    # ---- multiple comparisons
    ps = [float(t["p"]) for t in tests]; ho, bq = holm(ps), bh(ps)
    for t, h, q in zip(tests, ho, bq): t["p"] = R(t["p"], 6); t["p_holm"] = R(h, 6); t["q_bh"] = R(q, 6); t["sig_raw"] = t["p"] < 0.05; t["sig_holm"] = h < 0.05

    # ---- weekly series for the overlay chart
    nw = nd // 7
    def wk(x, f=np.sum): return [f(x[i * 7:(i + 1) * 7]) for i in range(nw)]
    series = {"week_start": [(START + timedelta(days=7 * i)).strftime("%Y-%m-%d") for i in range(nw)],
              "kp_max": [R(v, 2) for v in wk(kpd, np.max)], "g1_days": [int(v) for v in wk((kpd >= G1 - 1e-6).astype(int))],
              "flares_c": [int(v) for v in wk(fd["C"])], "flares_m": [int(v) for v in wk(fd["M"])], "flares_x": [int(v) for v in wk(fd["X"])],
              "quakes_raw": [int(v) for v in wk(qd["raw"])], "quakes_decl": [int(v) for v in wk(qd["declustered"])],
              "moment_log10": [R(math.log10(v), 3) if v > 0 else None for v in wk(mom)]}

    # ---- events (G1+ onsets) for the map selector
    ev = []
    for k, s in enumerate(on1):
        seg = kp[s:s + WIN_H // 3]
        ev.append({"i": k, "t": (START + timedelta(hours=3 * int(s))).strftime("%Y-%m-%dT%H:%MZ"), "kp_peak": R(float(seg.max()), 2),
                   "g3": bool(seg.max() >= G3 - 1e-6), "ss_lat": R(ss_lat_on[k], 2), "ss_lon": R(ss_lon_on[k], 2)})
    wq = window_assign(on_h)
    pts_in = [[R(qla[i], 2), R(qlo[i], 2), R(qm[i], 1), int(wq[i]), int(bool(keep_gk[i])), Q[i][0].strftime("%Y-%m-%dT%H:%MZ")]
              for i in np.where((wq >= 0) & sets["raw"])[0]]
    pts_out = [[R(qla[i], 2), R(qlo[i], 2), R(qm[i], 1), -1, int(bool(keep_gk[i])), Q[i][0].strftime("%Y-%m-%dT%H:%MZ")]
               for i in np.where((wq < 0) & (qm >= 6.0 - 1e-9))[0]]

    fcount = {L: int((fl_c == L).sum()) for L in "ABCMX"}
    srcs = {}
    for f in flares: srcs.setdefault(f[3], [f[0], f[0]]); srcs[f[3]][1] = f[0]
    flare_src = [{"source": k, "first": v[0].strftime("%Y-%m-%d"), "last": v[1].strftime("%Y-%m-%d")} for k, v in srcs.items()]
    n_sig_raw = sum(t["sig_raw"] for t in tests); n_sig_holm = sum(t["sig_holm"] for t in tests)
    out = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "generated_et": et(now),
        "label": "Exploratory analysis, not established science",
        "span": {"start": START.strftime("%Y-%m-%d"), "end_utc": END.strftime("%Y-%m-%dT%H:%MZ"), "end_et": et(END), "days": R(nb / 8, 1)},
        "params": {"mc_maxc": mc, "m_min": MMIN, "win_h": WIN_H, "quiet_h": QUIET_H, "g1_kp": "5− (≥4.67)", "g3_kp": "7− (≥6.67)", "nperm": NPERM,
                   "lag_surrogates": int(len(dshift)), "seed": SEED, "dipole_pole": DIPOLE, "decluster": "Gardner & Knopoff (1974) windows, full M4.5+ catalog"},
        "counts": {"kp_bins": int(nb), "kp_first": kp_t[0].strftime("%Y-%m-%d"), "kp_definitive_through": (kp_t[int(np.where(kp_def == 2)[0][-1])]).strftime("%Y-%m-%d") if (kp_def == 2).any() else None,
                   "g1_bins": int(g1.sum()), "g3_bins": int(g3.sum()), "g1_onsets": int(len(on1)), "g3_onsets": int(len(on3)), "x_flare_bins": int(len(xbins)),
                   "flares": fcount, "flares_first": flares[0][0].strftime("%Y-%m-%d"), "flares_last": flares[-1][0].strftime("%Y-%m-%d"), "flare_sources": flare_src,
                   "quakes_m45": int(len(Q)), "quakes_first": Q[0][0].strftime("%Y-%m-%d"), "quakes_last": Q[-1][0].strftime("%Y-%m-%dT%H:%MZ"),
                   "quakes_raw": int(sets["raw"].sum()), "quakes_decl": int(sets["declustered"].sum()), "aftershock_share_pct": R((1 - sets["declustered"].sum() / sets["raw"].sum()) * 100, 1)},
        "rate": rate, "lag": lagres, "sea": seares, "geo": geo, "tests": tests,
        "summary": {"n_tests": len(tests), "n_sig_raw": int(n_sig_raw), "n_sig_holm": int(n_sig_holm)},
        "series": series, "events": ev,
        "sources": [{"name": "GFZ Potsdam — Kp index (Matzka et al. 2021), definitive + nowcast", "url": URLS["kp"]},
                    {"name": "NOAA NCEI — GOES XRS flare event reports (2010–2017)", "url": URLS["goes_legacy"]},
                    {"name": "NOAA NCEI — GOES-16 XRS flare summary (GOES-R)", "url": URLS["goes16"]},
                    {"name": "NOAA NCEI — GOES-19 XRS flare summary (GOES-R)", "url": URLS["goes19"]},
                    {"name": "NOAA SWPC — GOES X-ray flares, last 7 days", "url": URLS["swpc7"]},
                    {"name": "USGS ComCat — FDSN event web service, M4.5+ worldwide", "url": URLS["usgs"]}],
    }
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "solar_quake.json"), "w"), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    json.dump({"generated_utc": out["generated_utc"], "fields": ["lat", "lon", "mag", "event", "mainshock", "t"], "impact": pts_in, "other_m6": pts_out,
               "events": ev}, open(os.path.join(OUT, "solar_quake_map.json"), "w"), separators=(",", ":"), allow_nan=False)
    print(json.dumps({"counts": out["counts"], "summary": out["summary"]}, indent=1, default=str), file=sys.stderr)

if __name__ == "__main__":
    main()
