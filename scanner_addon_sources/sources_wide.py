"""BLACKOUT.NETWORK wide-net sources (2026-11-18, pt1653u: "every little sensor, every little API that's free").

Many keyless public feeds, each registered as its own scanner source so source_health tracks it separately.
Safety rails (one bad feed can't crash the scan or flood the Wire):
  * all URLs are prefetched in parallel once per scan (20 s timeout each, no retry) -> the whole batch adds ~20-30 s, not minutes;
  * every adapter raises on failure (scanner.scan() catches it per source and logs it in source_health);
  * per-source item cap (CAP, default 12) + max age; cross-source duplicate titles dropped within a scan;
  * kill switches: env BN_SOURCES_WIDE=0 or a file `sources_wide_off` next to this module turns the whole set off;
    `sources_wide_disabled.json` (list of keys) turns single feeds off (they report ok with 0 items + note "disabled").
  * low base scores (news 6-10, official 8-20): a lone item never reaches push rank; it only adds corroboration.
No keys, no logins, no scraping behind bot checks. Public RSS/Atom/JSON only.
"""
import re, json, os, time, hashlib, csv, io
import xml.etree.ElementTree as ET
from datetime import timedelta, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import scanner as S

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (BlackoutNetwork early-warning research monitor; +https://blackout.network)"}
TIMEOUT = 20
CAP = 12
_CACHE = {"t": 0, "data": {}}
_SEEN = {"t": 0, "titles": set()}

def enabled():
    return os.environ.get("BN_SOURCES_WIDE", "1") != "0" and not os.path.exists(os.path.join(HERE, "sources_wide_off"))
def disabled_keys():
    try: return set(json.load(open(os.path.join(HERE, "sources_wide_disabled.json"))))
    except Exception: return set()

THREAT = (r"\b(killed|dead|deaths?|casualt|injur|wounded|evacuat|missile|airstrike|strikes?|attack|shelling|drone|troops|invasion|war\b|"
          r"explosion|blast|outbreak|epidemic|virus|infect|riot|clashes|unrest|curfew|sanction|emergency|martial law|coup|"
          r"default|collapse|crash|quake|earthquake|tsunami|flood|cyclone|hurricane|typhoon|wildfire|eruption|volcan|tornado|"
          r"ransomware|hack|breach|outage|blackout|cyber|terror|hostage|shooting|gunman|nuclear|radiation|chemical|spill|derail|"
          r"ebola|marburg|h5n1|bird flu|cholera|mpox|measles|plague|hijack|shot down|warship|navy|nato|ceasefire|mobiliz)")
NOISE = r"\b(podcast|quiz|recipe|review|opinion|horoscope|crossword|in pictures|watch:|live blog|sport|football|soccer|cricket|nba|nfl|oscar|celebrity)\b"

def _norm(t): return re.sub(r"[^a-z0-9 ]", "", (t or "").lower())[:90]

# ---------------------------------------------------------------- fetch layer
def _fetch_one(url):
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        return ("ok", r.content)
    except Exception as ex:
        return ("err", f"{type(ex).__name__}: {str(ex)[:200]}")

def _prefetch():
    if time.time() - _CACHE["t"] < 240: return
    off = disabled_keys()
    for sp in SPECS:
        if sp.get("tmpl"): sp["urls"] = [_nvd_url(sp["tmpl"])]
    urls = sorted({u for sp in SPECS if sp["key"] not in off for u in sp["urls"]})
    with ThreadPoolExecutor(max_workers=16) as ex:
        res = dict(zip(urls, ex.map(_fetch_one, urls)))
    _CACHE.update(t=time.time(), data=res)
    _SEEN.update(t=time.time(), titles=set())

def fetch(url):
    _prefetch()
    st, v = _CACHE["data"].get(url) or _fetch_one(url)
    if st != "ok": raise RuntimeError(v)
    return v

# ---------------------------------------------------------------- generic parsers
def p_rss(sp):
    """Generic RSS/Atom. Options: cat (forced) or classify; inc/exc regex; news tier; region."""
    out = []
    maxage = sp.get("maxage", 3)
    for url in sp["urls"]:
        for e in S.rss_items(fetch(url)):
            t = S.parse_t(e.get("pubDate") or e.get("updated") or e.get("published") or e.get("date") or e.get("sent"))
            if t and t < S.now() - timedelta(days=maxage): continue
            if not t and sp.get("need_time", True): continue
            title = S.strip(e.get("title")); desc = S.strip(e.get("description") or e.get("summary") or e.get("content"))[:600]
            text = title + " " + desc
            if not title: continue
            if sp.get("inc") and not re.search(sp["inc"], text, re.I): continue
            if sp.get("exc") and re.search(sp["exc"], text, re.I): continue
            if sp.get("news") and (not re.search(THREAT, title, re.I) or re.search(NOISE, title, re.I)): continue
            cat = sp.get("cat") or S.classify(text, sp.get("default", "other"))
            if sp.get("news") and cat == "other": continue
            b = sp.get("base", 8) + (15 if sp.get("boost") and re.search(sp["boost"], text, re.I) else 0)
            link = e.get("link") or sp["home"]
            out.append(S.item(sp["name"], sp.get("family", sp["key"]), e.get("guid") or e.get("id") or link or title, title, cat, link, t,
                              location=sp.get("region"), base=b, official=sp.get("official", not sp.get("news")),
                              extra={"desc": desc[:300], "tier": "news" if sp.get("news") else "official", "wide": sp["key"]}))
    return out

def p_statuspage(sp):
    j = json.loads(fetch(sp["urls"][0]))
    out = []
    for inc in j.get("incidents", []):
        imp = inc.get("impact") or "none"
        if imp in ("none", "minor") and not sp.get("all"): continue
        t = S.parse_t(inc.get("started_at") or inc.get("created_at"))
        title = f"{sp['label']} outage: {inc.get('name')} ({imp} impact, {inc.get('status')})"
        out.append(S.item(sp["name"], sp["key"], inc["id"], title, "cyber", inc.get("shortlink") or sp["home"], t, location="Global (internet)",
                          base={"critical": 25, "major": 15}.get(imp, 6), official=True, extra={"impact": imp, "wide": sp["key"], "kind": "service outage"}))
    return out

# ---------------------------------------------------------------- custom adapters
def p_donki(sp):
    out = []
    for n in json.loads(fetch(sp["urls"][0])):
        t = S.parse_t(n.get("messageIssueTime"))
        if not t or t < S.now() - timedelta(days=3): continue
        body = n.get("messageBody") or ""
        m = re.search(r"## Summary:\s*(.+?)(\n\s*\n|##)", body, re.S)
        summ = S.strip(m.group(1) if m else body)[:280]
        typ = n.get("messageType")
        if typ in ("Report", "RBE"): continue
        b = 8 + (20 if re.search(r"X\d|X-class|G[345]|Kp ?[789]|severe|S[2-5]\b", summ) else 0)
        out.append(S.item(sp["name"], "NASA", n.get("messageID"), f"NASA DONKI {typ}: {summ[:200]}", "space weather", n.get("messageURL") or sp["home"],
                          t, location="Global (Earth)", base=b, extra={"type": typ, "wide": sp["key"]}))
    return out

def p_swpc_scales(sp):
    j = json.loads(fetch(sp["urls"][0])); out = []
    cur = j.get("0") or {}
    for k, name in (("R", "radio blackout"), ("S", "solar radiation storm"), ("G", "geomagnetic storm")):
        lv = int((cur.get(k) or {}).get("Scale") or 0)
        if lv >= 2:
            t = S.parse_t(f"{cur.get('DateStamp')}T{cur.get('TimeStamp')}Z")
            out.append(S.item(sp["name"], "NOAA", f"{k}{lv}|{cur.get('DateStamp')}", f"NOAA space weather scale now {k}{lv} ({name})", "space weather",
                              sp["home"], t, location="Global (Earth)", base=10 + lv * 12, extra={"scale": f"{k}{lv}", "wide": sp["key"]}))
    for d in ("1", "2", "3"):
        g = int(((j.get(d) or {}).get("G") or {}).get("Scale") or 0)
        if g >= 3:
            out.append(S.item(sp["name"], "NOAA", f"Gfc{g}|{j[d].get('DateStamp')}", f"NOAA forecasts G{g} geomagnetic storm for {j[d].get('DateStamp')}",
                              "space weather", sp["home"], S.now(), location="Global (Earth)", base=10 + g * 8, extra={"wide": sp["key"]}))
    return out

def p_swpc_flare(sp):
    out = []
    for f in json.loads(fetch(sp["urls"][0])):
        c = f.get("max_class") or ""
        if not re.match(r"^(X|M[5-9])", c): continue
        out.append(S.item(sp["name"], "NOAA", f.get("begin_time"), f"Solar flare {c} (GOES X-ray), peak {f.get('max_time')}", "space weather",
                          sp["home"], S.parse_t(f.get("max_time")), location="Global (Earth)", base=25 if c.startswith("X") else 12, extra={"wide": sp["key"]}))
    return out

def p_usgs_vhp(sp):
    out = []
    for v in json.loads(fetch(sp["urls"][0])):
        if (v.get("colorCode") or "").upper() not in ("ORANGE", "RED") and (v.get("alertLevel") or "").upper() not in ("WATCH", "WARNING"): continue
        t = S.parse_t((v.get("sentUtc") or "").replace(" ", "T") + "Z")
        out.append(S.item(sp["name"], "USGS", v.get("noticeId"), f"{v.get('vName')} volcano {v.get('colorCode')}/{v.get('alertLevel')}", "natural disaster",
                          v.get("noticeUrl") or sp["home"], t, v.get("lat"), v.get("long"), "United States", 25 if v.get("colorCode") == "RED" else 15,
                          extra={"desc": (v.get("noticeSynopsis") or "")[:300], "wide": sp["key"]}))
    return out

def p_faa_nas(sp):
    root = ET.fromstring(fetch(sp["urls"][0])); out = []
    upd = S.now()
    for dt in root.iter("Delay_type"):
        kind = (dt.findtext("Name") or "")
        for g in list(dt.iter("Ground_Stop")) + list(dt.iter("Airport")) + list(dt.iter("Program")):
            arpt = g.findtext("ARPT") or g.findtext("ARPT_NAME") or "?"
            reason = g.findtext("Reason") or g.findtext("Reason") or ""
            if "Closure" in kind and not re.search(r"emergency|security|accident|disabled|fire|weather|evacuat|unsafe|wx", reason + (g.findtext("Text") or ""), re.I): continue
            label = "Ground stop" if "Ground Stop" in kind else ("Ground delay" if "Ground Delay" in kind else ("Airport closure" if "Closure" in kind else None))
            if not label: continue
            title = f"FAA {label}: {arpt} ({reason[:80]})"
            out.append(S.item(sp["name"], "FAA", f"{label}|{arpt}|{reason}|{upd:%Y%m%d}", title, "other", sp["home"], upd, location=f"{arpt}, US",
                              base=10 if label == "Ground stop" else 5, extra={"wide": sp["key"], "kind": "aviation"}))
    return out

def p_fema(sp):
    j = json.loads(fetch(sp["urls"][0])); out = []; seen = set()
    for d in j.get("DisasterDeclarationsSummaries", []):
        n = d.get("disasterNumber")
        if n in seen: continue
        seen.add(n)
        t = S.parse_t(d.get("declarationDate"))
        if not t or t < S.now() - timedelta(days=10): continue
        typ = {"DR": "Major disaster", "EM": "Emergency", "FM": "Fire management"}.get(d.get("declarationType"), d.get("declarationType"))
        out.append(S.item(sp["name"], "FEMA", n, f"FEMA {typ} declaration: {d.get('declarationTitle')} ({d.get('state')})", "natural disaster",
                          f"https://www.fema.gov/disaster/{n}", t, location=f"{d.get('state')}, US", base=18 if d.get("declarationType") == "DR" else 12,
                          extra={"incident": d.get("incidentType"), "wide": sp["key"]}))
    return out

def p_ukflood(sp):
    out = []
    for f in json.loads(fetch(sp["urls"][0])).get("items", []):
        sev = f.get("severityLevel")
        out.append(S.item(sp["name"], "UK-EA", f.get("floodAreaID", "") + "|" + (f.get("timeRaised") or ""), f"UK {f.get('severity')}: {f.get('description')}",
                          "natural disaster", "https://check-for-flooding.service.gov.uk/", S.parse_t(f.get("timeRaised")), location=f"{f.get('eaAreaName')}, UK",
                          base=30 if sev == 1 else 10, extra={"wide": sp["key"]}))
    return out

def p_bmkg(sp):
    out = []
    for url in sp["urls"]:
        for g in (json.loads(fetch(url)).get("Infogempa") or {}).get("gempa", []):
            try: m = float(g.get("Magnitude") or 0)
            except ValueError: m = 0
            if m < 5: continue
            t = S.parse_t(g.get("DateTime"))
            if t and t < S.now() - timedelta(days=3): continue
            try: lat, lon = [float(x) for x in (g.get("Coordinates") or ",").split(",")]
            except Exception: lat = lon = None
            out.append(S.item(sp["name"], "BMKG", g.get("DateTime"), f"M{m} earthquake, {g.get('Wilayah')} (BMKG)", "natural disaster", sp["home"], t, lat, lon,
                              "Indonesia", 20 + max(0, m - 4.5) * 18, extra={"potensi": g.get("Potensi"), "wide": sp["key"]}))
    return out

def p_fireball(sp):
    j = json.loads(fetch(sp["urls"][0])); out = []
    for r in j.get("data", []):
        d = dict(zip(j["fields"], r)); t = S.parse_t(d["date"].replace(" ", "T") + "Z")
        if not t or t < S.now() - timedelta(days=10): continue
        lat = float(d["lat"]) * (-1 if d.get("lat-dir") == "S" else 1) if d.get("lat") else None
        lon = float(d["lon"]) * (-1 if d.get("lon-dir") == "W" else 1) if d.get("lon") else None
        kt = float(d.get("impact-e") or 0)
        out.append(S.item(sp["name"], "NASA-JPL", d["date"], f"Bolide (fireball) airburst detected, ~{kt} kt impact energy", "other", sp["home"], t, lat, lon,
                          None, 8 + min(30, kt * 5), extra={"wide": sp["key"]}))
    return out

def p_cad(sp):
    j = json.loads(fetch(sp["urls"][0])); out = []
    for r in j.get("data", []) or []:
        d = dict(zip(j["fields"], r))
        out.append(S.item(sp["name"], "NASA-JPL", f"{d['des']}|{d['cd']}", f"Asteroid {d['des']} passes within {float(d['dist'])*389.2:.2f} lunar distances on {d['cd']} UTC",
                          "other", sp["home"], S.now(), None, None, "Near-Earth space", 8, extra={"h": d.get("h"), "wide": sp["key"]}))
    return out

def p_nvd(sp):
    j = json.loads(fetch(sp["urls"][0])); out = []
    for v in j.get("vulnerabilities", []):
        c = v["cve"]; t = S.parse_t(c.get("published"))
        if not t or t < S.now() - timedelta(days=3): continue
        desc = next((d["value"] for d in c.get("descriptions", []) if d.get("lang") == "en"), "")
        out.append(S.item(sp["name"], "NVD", c["id"], f"{c['id']} (CVSS critical): {desc[:200]}", "cyber", f"https://nvd.nist.gov/vuln/detail/{c['id']}", t,
                          location="Global", base=6, extra={"wide": sp["key"]}))
    return out

def p_gcp(sp):
    out = []
    for inc in json.loads(fetch(sp["urls"][0]))[:30]:
        t = S.parse_t(inc.get("begin"))
        if inc.get("end") and (S.parse_t(inc["end"]) or S.now()) < S.now() - timedelta(hours=12): continue
        if not t or t < S.now() - timedelta(days=3): continue
        sev = inc.get("severity")
        out.append(S.item(sp["name"], "Google", inc["id"], f"Google Cloud incident ({sev}): {(inc.get('external_desc') or '')[:200]}", "cyber",
                          "https://status.cloud.google.com/", t, location="Global (internet)", base=20 if sev == "high" else 6, extra={"wide": sp["key"], "kind": "service outage"}))
    return out

def p_ercot(sp):
    j = json.loads(fetch(sp["urls"][0])); c = j.get("current_condition") or {}
    if c.get("state") == "normal" and str(c.get("eea_level", "0")) == "0": return []
    t = S.now()
    return [S.item(sp["name"], "ERCOT", f"{c.get('state')}|{c.get('eea_level')}|{t:%Y%m%d%H}", f"Texas grid (ERCOT): {c.get('title')} - {c.get('condition_note')}",
                   "other", "https://www.ercot.com/gridmktinfo/dashboards", t, location="Texas, US", base=15 + 10 * int(c.get("eea_level") or 0),
                   extra={"prc_mw": c.get("prc_value"), "wide": sp["key"], "kind": "power grid"})]

def p_wfigs(sp):
    j = json.loads(fetch(sp["urls"][0])); out = []
    for f in j.get("features", []):
        a = f.get("attributes", {}); g = f.get("geometry") or {}
        mt = a.get("ModifiedOnDateTime_dt"); t = datetime.fromtimestamp(mt / 1000, timezone.utc) if mt else None
        if not t or t < S.now() - timedelta(days=3): continue
        pc = a.get("PercentContained"); size = a.get("IncidentSize") or 0
        if pc is not None and pc >= 90: continue
        st = (a.get("POOState") or "").replace("US-", "")
        out.append(S.item(sp["name"], "NIFC", f"{a.get('IncidentName')}|{st}", f"Wildfire: {a.get('IncidentName')} ({st}), {int(size):,} acres, {pc if pc is not None else '?'}% contained",
                          "natural disaster", "https://www.nifc.gov/fire-information", t, g.get("y"), g.get("x"), f"{st}, US", 10 + min(25, size / 10000),
                          extra={"acres": size, "wide": sp["key"]}))
    return out

def p_spc_torn(sp):
    out = []; day = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = list(csv.DictReader(io.StringIO(fetch(sp["urls"][0]).decode("utf-8", "replace"))))
    for r in rows:
        try: lat, lon = float(r.get("Lat")), float(r.get("Lon"))
        except Exception: lat = lon = None
        out.append(S.item(sp["name"], "NOAA-SPC", f"{day}|{r.get('Time')}|{r.get('Location')}", f"Tornado report: {r.get('Location')}, {r.get('County')} Co., {r.get('State')}",
                          "natural disaster", "https://www.spc.noaa.gov/climo/reports/today.html", S.now(), lat, lon, f"{r.get('State')}, US", 12,
                          extra={"comments": (r.get("Comments") or "")[:300], "wide": sp["key"]}))
    return out

def p_usgs_us(sp):
    out = []
    for f in json.loads(fetch(sp["urls"][0])).get("features", []):
        p = f["properties"]; m = p.get("mag") or 0
        if m >= 4.5: continue   # M4.5+ already comes from scanner.f_usgs
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append(S.item(sp["name"], "USGS", f["id"], f"M{m} earthquake - {p.get('place')}", "natural disaster", p.get("url"),
                          datetime.fromtimestamp(p["time"] / 1000, timezone.utc), lat, lon, p.get("place"), max(4, int(20 + (m - 4.5) * 10)),
                          extra={"felt": p.get("felt"), "wide": sp["key"]}))
    return out

def p_ransom(sp):
    out = []
    for r in json.loads(fetch(sp["urls"][0]))[:40]:
        t = S.parse_t((r.get("discovered") or "")[:19].replace(" ", "T") + "Z")
        if not t or t < S.now() - timedelta(days=2): continue
        out.append(S.item(sp["name"], "ransomlook", f"{r.get('group_name')}|{r.get('post_title')}", f"Ransomware claim: {r.get('group_name')} lists {r.get('post_title')}",
                          "cyber", "https://www.ransomlook.io/recent", t, location=None, base=4, official=False,
                          extra={"desc": (r.get("description") or "")[:200], "wide": sp["key"], "tier": "claims"}))
    return out

def p_infocon(sp):
    s = json.loads(fetch(sp["urls"][0])).get("status", "green")
    if s == "green": return []
    return [S.item(sp["name"], "SANS", f"infocon|{s}|{S.now():%Y%m%d}", f"SANS Internet Storm Center INFOCON raised to {s.upper()}", "cyber",
                   "https://isc.sans.edu/infocon.html", S.now(), location="Global (internet)", base={"yellow": 15, "orange": 30, "red": 45}.get(s, 10), extra={"wide": sp["key"]})]

def p_firms(sp):
    """NASA FIRMS VIIRS 24h (US): grid detections into 0.5 deg cells; report cells with >=40 detections or summed FRP >= 2000 MW."""
    cells = {}
    for r in csv.DictReader(io.StringIO(fetch(sp["urls"][0]).decode("utf-8", "replace"))):
        try: lat, lon, frp = float(r["latitude"]), float(r["longitude"]), float(r.get("frp") or 0)
        except Exception: continue
        if r.get("confidence") == "l": continue
        k = (round(lat * 2) / 2, round(lon * 2) / 2)
        c = cells.setdefault(k, [0, 0.0, None]); c[0] += 1; c[1] += frp; c[2] = max(c[2] or "", r.get("acq_date", "") + r.get("acq_time", ""))
    out = []; day = datetime.now(timezone.utc).strftime("%Y%m%d")
    for (lat, lon), (n, frp, _) in sorted(cells.items(), key=lambda kv: -kv[1][1]):
        if n < 40 and frp < 2000: continue
        out.append(S.item(sp["name"], "NASA-FIRMS", f"{day}|{lat}|{lon}", f"Satellite fire hotspots: {n} detections ({frp:,.0f} MW) near {lat:.1f}, {lon:.1f}",
                          "natural disaster", "https://firms.modaps.eosdis.nasa.gov/usfs/map/", S.now(), lat, lon, "United States", 10 + min(20, frp / 1000),
                          extra={"detections": n, "frp_mw": round(frp), "wide": sp["key"]}))
    return out

# ---------------------------------------------------------------- registry
def R(key, name, url, home=None, **kw): return dict(key=key, name=name, urls=url if isinstance(url, list) else [url], home=home or (url[0] if isinstance(url, list) else url), parse=kw.pop("parse", p_rss), **kw)
ND, DI, CY, SW, WC = "natural disaster", "disease", "cyber", "space weather", "war/conflict"
OUTB = r"outbreak|cases|ebola|marburg|cholera|mpox|measles|h5n1|avian|influenza|plague|dengue|polio|anthrax|nipah|emergenc|epidemic|alert"
SPECS = [
    # --- hazards / weather / geophysics
    R("nhc_at", "NOAA NHC Atlantic", "https://www.nhc.noaa.gov/index-at.xml", cat=ND, base=12, exc=r"no tropical cyclones|Tropical Weather Outlook", boost=r"hurricane warning|major hurricane|category [345]", region="Atlantic basin", maxage=2),
    R("nhc_ep", "NOAA NHC East Pacific", "https://www.nhc.noaa.gov/index-ep.xml", cat=ND, base=10, exc=r"no tropical cyclones|Tropical Weather Outlook", boost=r"hurricane warning|major hurricane", region="Eastern Pacific", maxage=2),
    R("nhc_cp", "NOAA CPHC Central Pacific", "https://www.nhc.noaa.gov/index-cp.xml", cat=ND, base=10, exc=r"no tropical cyclones|Tropical Weather Outlook", boost=r"hurricane warning", region="Central Pacific", maxage=2),
    R("ptwc_pheb", "PTWC Pacific tsunami messages (PHEB)", "https://www.tsunami.gov/events/xml/PHEBAtom.xml", cat=ND, base=12, boost=r"warning|threat", region="Pacific", maxage=3),
    R("usgs_us_m35", "USGS US quakes M3.5-4.4 (24h)", "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=3.5&starttime=-1day&eventtype=earthquake&maxlatitude=50&minlatitude=24&maxlongitude=-66&minlongitude=-125", home="https://earthquake.usgs.gov/", parse=p_usgs_us),
    R("bmkg", "BMKG Indonesia quakes (M5+)", ["https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json", "https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json"], home="https://www.bmkg.go.id/", parse=p_bmkg),
    R("usgs_vhp", "USGS volcano notices (ORANGE/RED, WATCH/WARNING)", "https://volcanoes.usgs.gov/vsc/api/volcanoApi/elevated", home="https://volcanoes.usgs.gov/", parse=p_usgs_vhp),
    R("nifc_wfigs", "NIFC WFIGS large wildfires (>5,000 acres)", "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations_Current/FeatureServer/0/query?where=IncidentSize%3E5000&outFields=IncidentName,IncidentSize,PercentContained,POOState,ModifiedOnDateTime_dt&f=json", parse=p_wfigs),
    R("firms_us", "NASA FIRMS VIIRS fire hotspots (US 24h, clustered)", "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv", parse=p_firms),
    R("spc_torn", "NOAA SPC tornado reports (today)", "https://www.spc.noaa.gov/climo/reports/today_torn.csv", parse=p_spc_torn),
    R("fema_decl", "FEMA disaster declarations", "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$orderby=declarationDate%20desc&$top=60", home="https://www.fema.gov/disaster/declarations", parse=p_fema),
    R("uk_flood", "UK Environment Agency flood warnings (severe + warning)", "https://environment.data.gov.uk/flood-monitoring/id/floods?min-severity=2", parse=p_ukflood),
    R("hko_warn", "Hong Kong Observatory warnings", "https://rss.weather.gov.hk/rss/WeatherWarningSummaryv2.xml", cat=ND, base=8, region="Hong Kong", exc=r"no warning|There is no", boost=r"signal (no\. )?(8|9|10)|black rainstorm", need_time=False),
    R("nz_metservice", "MetService NZ CAP (orange/red)", "https://alerts.metservice.com/cap/rss", cat=ND, base=8, region="New Zealand", inc=r"warning", boost=r"red warning"),
    # --- space
    R("donki", "NASA DONKI space weather notifications", "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/notifications?type=all", home="https://kauai.ccmc.gsfc.nasa.gov/DONKI/", parse=p_donki),
    R("swpc_scales", "NOAA SWPC scales (R/S/G now + 3-day G forecast)", "https://services.swpc.noaa.gov/products/noaa-scales.json", home="https://www.swpc.noaa.gov/noaa-scales-explanation", parse=p_swpc_scales),
    R("swpc_flares", "NOAA GOES X-ray flares (M5+)", "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json", home="https://www.swpc.noaa.gov/products/goes-x-ray-flux", parse=p_swpc_flare),
    R("jpl_fireball", "NASA JPL CNEOS fireballs", "https://ssd-api.jpl.nasa.gov/fireball.api?limit=20", home="https://cneos.jpl.nasa.gov/fireballs/", parse=p_fireball),
    R("jpl_cad", "NASA JPL close approaches (<1 lunar distance, 30 d)", "https://ssd-api.jpl.nasa.gov/cad.api?dist-max=1LD&date-min=now&date-max=%2B30", home="https://cneos.jpl.nasa.gov/ca/", parse=p_cad),
    # --- health
    R("cdc_han", "CDC Health Alert Network", "https://tools.cdc.gov/api/v2/resources/media/413690.rss", cat=DI, base=20, maxage=14, region="United States"),
    R("ecdc_news", "ECDC news", "https://www.ecdc.europa.eu/en/taxonomy/term/1244/feed", cat=DI, base=8, maxage=7, region="Europe", inc=OUTB),
    R("ecdc_threats", "ECDC communicable disease threats", "https://www.ecdc.europa.eu/en/taxonomy/term/1307/feed", cat=DI, base=10, maxage=8, region="Europe"),
    R("who_news", "WHO news (outbreak/emergency items)", "https://www.who.int/rss-feeds/news-english.xml", cat=DI, base=8, maxage=5, inc=OUTB),
    R("who_afro", "WHO Africa featured news", "https://www.afro.who.int/rss/featured-news.xml", cat=DI, base=8, maxage=7, inc=OUTB, region="Africa"),
    R("paho", "PAHO news", "https://www.paho.org/en/rss.xml", cat=DI, base=8, maxage=7, inc=OUTB, region="Americas"),
    R("fda_recalls", "FDA recalls (pathogen/toxin)", "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml", cat=DI, base=5, maxage=5, inc=r"listeria|salmonella|e\. coli|botulism|hepatitis|outbreak|toxin", region="United States"),
    R("outbreaknewstoday", "Outbreak News Today", "https://outbreaknewstoday.com/feed/", cat=DI, base=6, maxage=3, news=True),
    R("statnews", "STAT News", "https://www.statnews.com/feed/", base=5, maxage=2, news=True, inc=OUTB),
    R("avianflu_diary", "Avian Flu Diary", "https://afludiary.blogspot.com/feeds/posts/default", cat=DI, base=5, maxage=3, news=True),
    # --- nuclear / energy / infrastructure
    R("nrc_news", "US NRC press releases", "https://www.nrc.gov/public-involve/rss?feed=news", base=6, maxage=7, region="United States", inc=r"event|emergency|shutdown|alert|security|violation|unusual|scram|leak|radiation"),
    R("iaea_news", "IAEA top news", "https://www.iaea.org/feeds/topnews", base=8, maxage=7, inc=r"zaporizhzhia|chernobyl|kursk|nuclear safety|radiation|incident|attack|drone|power plant|emergency"),
    R("wnn", "World Nuclear News", "https://www.world-nuclear-news.org/rss", base=5, maxage=3, inc=r"shutdown|incident|attack|drone|emergency|leak|safety|zaporizhzhia|kursk"),
    R("ercot", "ERCOT Texas grid conditions (non-normal only)", "https://www.ercot.com/api/1/services/read/dashboards/daily-prc.json", home="https://www.ercot.com/gridmktinfo/dashboards", parse=p_ercot),
    R("utility_dive", "Utility Dive", "https://www.utilitydive.com/feeds/news/", base=5, maxage=3, news=True),
    R("power_mag", "POWER magazine", "https://www.powermag.com/feed/", base=5, maxage=3, news=True),
    R("bsee", "BSEE offshore safety", "https://www.bsee.gov/rss.xml", base=6, maxage=7, inc=r"spill|incident|explosion|fire|hurricane|evacuat|leak", region="Gulf of America"),
    R("faa_nas", "FAA NAS airport status (ground stops/delays/closures)", "https://nasstatus.faa.gov/api/airport-status-information", home="https://nasstatus.faa.gov/", parse=p_faa_nas),
    # --- internet / cloud status (only major/critical incidents)
    R("aws_status", "AWS service health RSS", "https://status.aws.amazon.com/rss/all.rss", cat=CY, base=8, maxage=1, exc=r"\[RESOLVED\]|operating normally", region="Global (internet)"),
    R("azure_status", "Azure status RSS", "https://azurestatuscdn.azureedge.net/en-us/status/feed/", cat=CY, base=10, maxage=1, region="Global (internet)", need_time=False),
    R("gcp_status", "Google Cloud incidents", "https://status.cloud.google.com/incidents.json", home="https://status.cloud.google.com/", parse=p_gcp),
    R("sans_infocon", "SANS ISC INFOCON", "https://isc.sans.edu/api/infocon?json", home="https://isc.sans.edu/", parse=p_infocon),
] + [R(f"sp_{k}", f"{lab} status (major/critical incidents)", f"https://{h}/api/v2/incidents/unresolved.json", home=f"https://{h}/", parse=p_statuspage, label=lab)
     for k, lab, h in [("cloudflare", "Cloudflare", "www.cloudflarestatus.com"), ("github", "GitHub", "www.githubstatus.com"), ("akamai", "Akamai", "www.akamaistatus.com"),
                       ("discord", "Discord", "discordstatus.com"), ("zoom", "Zoom", "status.zoom.us"), ("atlassian", "Atlassian", "status.atlassian.com"),
                       ("digitalocean", "DigitalOcean", "status.digitalocean.com"), ("reddit", "Reddit", "www.redditstatus.com"), ("dropbox", "Dropbox", "status.dropbox.com"),
                       ("twilio", "Twilio", "status.twilio.com"), ("vercel", "Vercel", "www.vercel-status.com"), ("shopify", "Shopify", "www.shopifystatus.com"),
                       ("linode", "Akamai Linode", "status.linode.com"), ("netlify", "Netlify", "www.netlifystatus.com"), ("anthropic", "Anthropic", "status.anthropic.com")]
] + [
    # --- cyber
    R("nvd_critical", "NIST NVD critical CVEs (new)", "https://services.nvd.nist.gov/rest/json/cves/2.0?cvssV3Severity=CRITICAL&resultsPerPage=50&pubStartDate={start}&pubEndDate={end}", home="https://nvd.nist.gov/", parse=p_nvd),
    R("ransomlook", "RansomLook recent ransomware claims", "https://www.ransomlook.io/api/recent", home="https://www.ransomlook.io/", parse=p_ransom, cap=10),
    R("cisa_news", "CISA news", "https://www.cisa.gov/news.xml", cat=CY, base=6, maxage=5, region="United States"),
    R("cert_at", "CERT.at warnings", "https://cert.at/cert-at.de.warnings.rss_2.0.xml", cat=CY, base=6, maxage=7, region="Austria"),
    R("sans_isc", "SANS Internet Storm Center diaries", "https://isc.sans.edu/rssfeed.xml", cat=CY, base=4, maxage=2, exc=r"stormcast"),
    R("bleeping", "BleepingComputer", "https://www.bleepingcomputer.com/feed/", base=6, maxage=2, news=True),
    R("krebs", "Krebs on Security", "https://krebsonsecurity.com/feed/", base=6, maxage=4, news=True),
    R("thehackernews", "The Hacker News", "https://feeds.feedburner.com/TheHackersNews", base=5, maxage=2, news=True),
    R("therecord", "The Record (Recorded Future News)", "https://therecord.media/feed", base=6, maxage=2, news=True),
    R("securityweek", "SecurityWeek", "https://www.securityweek.com/feed/", base=5, maxage=2, news=True),
    R("darkreading", "Dark Reading", "https://www.darkreading.com/rss.xml", base=5, maxage=2, news=True),
    # --- government / security / defense
    R("dod_news", "US DoD news", "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945&max=10", base=6, maxage=3, region="United States", news=True, official=True),
    R("dod_releases", "US DoD releases", "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=9&Site=945&max=10", base=6, maxage=3, region="United States", news=True, official=True),
    R("state_press", "US State Dept press releases", "https://www.state.gov/rss-feed/press-releases/feed/", base=6, maxage=3, inc=r"attack|terror|sanction|evacuat|ordered departure|hostage|missile|nuclear|ceasefire|emergency"),
    R("fbi_news", "FBI national press releases", "https://www.fbi.gov/feeds/national-press-releases/rss.xml", base=5, maxage=3, region="United States", inc=r"terror|attack|threat|cyber|ransomware|explosive|bomb|espionage|shooting"),
    R("doj", "DOJ press releases", "https://www.justice.gov/news/rss?type=press_release", base=4, maxage=2, region="United States", inc=r"terror|espionage|sanction|cyber|ransomware|hack|nuclear|export control|china|iran|russia|north korea"),
    R("eu_council", "Council of the EU press", "https://www.consilium.europa.eu/en/rss/pressreleases.ashx", base=5, maxage=3, region="Europe", inc=r"sanction|restrictive measures|attack|terror|emergency|hybrid|cyber"),
    R("uk_fcdo", "UK FCDO news", "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=foreign-commonwealth-development-office", base=5, maxage=3, inc=THREAT),
    R("un_news", "UN News (all)", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", base=6, maxage=2, news=True),
    R("un_peace", "UN News peace & security", "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml", base=6, maxage=3, news=True),
    R("un_ocha", "UN OCHA", "https://www.unocha.org/rss.xml", base=6, maxage=5, news=True),
    R("icrc", "ICRC news", "https://www.icrc.org/en/rss/news", base=6, maxage=5, news=True),
    R("crisisgroup", "International Crisis Group", "https://www.crisisgroup.org/rss.xml", base=6, maxage=5, news=True),
    R("bellingcat", "Bellingcat", "https://www.bellingcat.com/feed/", base=5, maxage=5, news=True),
    R("warontherocks", "War on the Rocks", "https://warontherocks.com/feed/", base=4, maxage=3, news=True),
    R("twz", "The War Zone", "https://www.twz.com/feed", base=6, maxage=2, news=True),
    R("defensenews", "Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", base=5, maxage=2, news=True),
    R("breakingdefense", "Breaking Defense", "https://breakingdefense.com/feed/", base=5, maxage=2, news=True),
    R("usni", "USNI News", "https://news.usni.org/feed", base=6, maxage=2, news=True),
    # --- maritime / aviation / space industry
    R("gcaptain", "gCaptain (maritime)", "https://gcaptain.com/feed/", base=6, maxage=2, news=True),
    R("maritime_exec", "The Maritime Executive", "https://maritime-executive.com/articles.rss", base=6, maxage=2, news=True),
    R("splash247", "Splash247 (shipping)", "https://splash247.com/feed/", base=5, maxage=2, news=True),
    R("simpleflying", "Simple Flying (aviation incidents)", "https://simpleflying.com/feed/", base=4, maxage=2, news=True, inc=r"crash|emergency|incident|evacuat|diverted|grounded|shot down|hijack"),
    R("spacenews", "SpaceNews", "https://spacenews.com/feed/", base=4, maxage=2, news=True),
    R("noaa_news", "NOAA news", "https://www.noaa.gov/rss.xml", base=5, maxage=5, inc=THREAT),
    # --- world news wires (threat headlines only, capped)
] + [R(k, n, u, base=7, maxage=1, news=True, cap=8) for k, n, u in [
    ("bbc_world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("aljazeera", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("dw", "DW", "https://rss.dw.com/rdf/rss-en-all"),
    ("france24", "France 24", "https://www.france24.com/en/rss"),
    ("npr_world", "NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("guardian_world", "The Guardian World", "https://www.theguardian.com/world/rss"),
    ("kyiv_ind", "Kyiv Independent", "https://kyivindependent.com/news-archive/rss/"),
    ("toi", "Times of Israel", "https://www.timesofisrael.com/feed/"),
    ("scmp", "South China Morning Post", "https://www.scmp.com/rss/91/feed"),
    ("abc_au", "ABC Australia", "https://www.abc.net.au/news/feed/2942460/rss.xml"),
    ("nbc", "NBC News", "https://feeds.nbcnews.com/nbcnews/public/news"),
    ("abcnews", "ABC News (US) international", "https://abcnews.go.com/abcnews/internationalheadlines"),
    ("cbs_world", "CBS News world", "https://www.cbsnews.com/latest/rss/world"),
    ("nyt_world", "New York Times world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("wapo_world", "Washington Post world", "https://feeds.washingtonpost.com/rss/world"),
    ("latimes", "LA Times world & nation", "https://www.latimes.com/world-nation/rss2.0.xml"),
    ("euronews", "Euronews", "https://www.euronews.com/rss?level=theme&name=news"),
    ("hindu", "The Hindu international", "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("japantimes", "Japan Times", "https://www.japantimes.co.jp/feed/"),
    ("straits", "Straits Times world", "https://www.straitstimes.com/news/world/rss.xml"),
    ("africanews", "Africanews", "https://www.africanews.com/feed/rss"),
    ("allafrica", "AllAfrica headlines", "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf"),
    ("mercopress", "MercoPress (South Atlantic/LatAm)", "https://en.mercopress.com/rss/"),
    ("rfi", "RFI English", "https://www.rfi.fr/en/rss"),
    ("independent", "The Independent world", "https://www.independent.co.uk/news/world/rss"),
    ("rnz", "RNZ world", "https://www.rnz.co.nz/rss/world.xml"),
    ("globalnews", "Global News (Canada) world", "https://globalnews.ca/world/feed/"),
    ("aa", "Anadolu Agency", "https://www.aa.com.tr/en/rss/default?cat=guncel"),
    ("ukrinform", "Ukrinform", "https://www.ukrinform.net/rss/block-lastnews"),
    ("pravda_ua", "Ukrainska Pravda", "https://www.pravda.com.ua/eng/rss/"),
    ("mee", "Middle East Eye", "https://www.middleeasteye.net/rss"),
    ("fox_world", "Fox News world", "https://moxie.foxnews.com/google-publisher/world.xml"),
    ("fox_us", "Fox News US", "https://moxie.foxnews.com/google-publisher/us.xml"),
    ("skynews", "Sky News world", "https://feeds.skynews.com/feeds/rss/world.xml"),
    ("clickorlando", "News 6 ClickOrlando (Central FL)", "https://www.clickorlando.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("wesh", "WESH 2 (Central FL)", "https://www.wesh.com/topstories-rss"),
]]

def _nvd_url(u):
    end = S.now(); start = end - timedelta(days=2)
    f = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000")
    return u.format(start=f(start), end=f(end))

def make(sp):
    def fn():
        if sp["key"] in disabled_keys(): return [], {"disabled": True}
        items = sp["parse"](sp)
        seen_ids, out = set(), []
        items.sort(key=lambda x: x.get("event_time") or "", reverse=True)
        for it in items:
            if it["id"] in seen_ids: continue
            nt = _norm(it["title"])
            if sp.get("news") and nt in _SEEN["titles"]: continue   # same headline already taken from another wire this scan
            seen_ids.add(it["id"]); _SEEN["titles"].add(nt); out.append(it)
            if len(out) >= sp.get("cap", CAP): break
        return out, ({"fetched": len(items), "kept": len(out)} if len(items) != len(out) else {})
    return fn

for _sp in SPECS:
    if "{start}" in _sp["urls"][0]: _sp["tmpl"] = _sp["urls"][0]; _sp["urls"] = [_nvd_url(_sp["tmpl"])]

def sources():
    if not enabled(): return []
    return [(f"[wide] {sp['name']}", sp["home"], make(sp)) for sp in SPECS]

WIDE_SOURCES = sources()
