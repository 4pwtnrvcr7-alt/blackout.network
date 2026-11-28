#!/usr/bin/env python3
"""Wire archive builder, phase 2 (Nov 27 2026, Matt: more sources for the 2000-01-01 .. 2024-10-28 archive).

Adds shards app/archive_wire_data/p2_<source>.ndjson.gz.b64 (same row layout as phase 1, same read-only SQLite, nothing else changes):
  p2_who_2018_2021  WHO Disease Outbreak News items that phase 1 had to drop because the site migration (2021) scrambled their API dates.
                    The date comes from the item's own URL (D-month-YYYY slug) or, for YYYY-DONnnn items, from the API publication
                    time only when it agrees with the DON number sequence (a neighbour check); anything else is still dropped.
  p2_gvp            Smithsonian Global Volcanism Program eruptions, VEI 2+ (GVP web services, VOTW eruptions + volcano list)
  p2_ntsb           NTSB major investigations (case numbers with an M-class code: MA, MR, MM, MH, MP, MZ) from the CAROL public API
  p2_kev            CISA Known Exploited Vulnerabilities catalog, by date added, linked to the NVD record
  p2_solar          NOAA SWPC X-class solar flares (edited event reports, archived at NGDC) and G4-G5 geomagnetic storms (GFZ Kp)
Every row has ONE direct source link (checked) and no write-up. Free templates only. Ranks come from the scanner's own scoring (read-only).
Usage: python3 tools/build_wire_archive_p2.py [--raw /workspace/archive2000/raw2] [--only who,gvp,ntsb,kev,solar]"""
import os, sys, re, json, gzip, base64, io, glob, argparse, collections
from datetime import datetime, timezone, timedelta, date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_wire_archive as B
from build_wire_archive import S, tag, smart, log, keep_t, Scorer, STATES, APP

UTC = timezone.utc
def dt(y, m, d, hh=0, mm=0): return datetime(y, m, d, hh, mm, tzinfo=UTC)
MONTHS = {n.lower(): i for i, n in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}

# ------------------------------------------------------------------ WHO 2018-2021
def p1_ids():
    ids = set()
    for fn in glob.glob(os.path.join(APP, "archive_wire_data", "[0-9]*.ndjson.gz.b64")):
        for line in gzip.decompress(base64.b64decode(open(fn, "rb").read())).decode().splitlines():
            r = json.loads(line)
            if r[11] == "WHO Disease Outbreak News": ids.add(r[0])
    return ids

def who_backfill(raw):
    vals = json.load(open(os.path.join(raw, "..", "raw", "who.json")))
    seq = collections.defaultdict(list)       # year -> [(don number, publication date)]
    for v in vals:
        m = re.match(r"^(\d{4})-DON(\d+)$", v.get("UrlName") or "")
        if m and (v.get("PublicationDateAndTime") or "")[:4] == m.group(1): seq[m.group(1)].append((int(m.group(2)), v["PublicationDateAndTime"][:10]))
    for y in seq: seq[y].sort()
    def nb_ok(y, n, d):
        near = sorted(seq[y], key=lambda x: abs(x[0] - n))[1:7]
        ds = sorted(x[1] for x in near)
        if len(ds) < 3: return False
        med = datetime.strptime(ds[len(ds) // 2], "%Y-%m-%d"); me = datetime.strptime(d, "%Y-%m-%d")
        return abs((me - med).days) <= 45
    def datefn(v, url_name):
        pdt = (v.get("PublicationDateAndTime") or "")[:10]
        m = re.match(r"^(\d{1,2})-([A-Za-z]+)-(\d{4})(?:-|$)", url_name)
        if m and m.group(2).lower() in MONTHS:
            try: return dt(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError: return None
        m = re.match(r"^(\d{4})-DON(\d+)$", url_name)
        if m and pdt[:4] == m.group(1) and nb_ok(m.group(1), int(m.group(2)), pdt): return pdt + "T00:00:00Z"
        return None
    have = p1_ids()
    items = B.who_items(os.path.join(raw, "..", "raw"), datefn=datefn)
    out = [x for x in items if "2018-01-01" <= x["it"]["event_time"][:10] <= "2021-12-31" and x["it"]["id"] not in have]
    for x in out:      # .title() leaves "Of The" in country names
        fixed = re.sub(r"\b(Of|The|And)\b", lambda m: m.group(1).lower(), x["loc"]); x["loc"] = x["it"]["location"] = fixed
        x["tags"] = [t for t in x["tags"] if t] or ["#WHO", "#Outbreak"]
    log("who backfill rows", len(out), "(of", len(items), "dated by the new rule)")
    return out

# ------------------------------------------------------------------ Smithsonian GVP
def gvp(raw):
    vol = {f["properties"]["Volcano_Number"]: f["properties"] for f in json.load(open(os.path.join(raw, "gvp_v.json")))["features"]}
    out = []
    for f in json.load(open(os.path.join(raw, "gvp_e.json")))["features"]:
        p = f["properties"]; vei = p.get("ExplosivityIndexMax")
        y, mo, d = p.get("StartDateYear"), p.get("StartDateMonth"), p.get("StartDateDay")
        if vei is None or vei < 2 or not y or not (2000 <= y <= 2024) or not mo: continue
        day_known = bool(d)
        t = dt(y, mo, d or 1)
        if not keep_t(t.strftime("%Y-%m-%dT%H:%M:%SZ")): continue
        v = vol.get(p["VolcanoNumber"], {}); name = (p.get("VolcanoName") or v.get("Volcano_Name") or "").strip(); country = (v.get("Country") or "").strip()
        if not name: continue
        loc = f"{name}, {country}" if country else name
        when = "" if day_known else f" (began {t.strftime('%B %Y')})"
        size = {2: "explosive", 3: "large explosive", 4: "very large explosive", 5: "cataclysmic"}.get(vei, "large")
        head = f"Volcanic eruption at {name}, {country}: VEI {vei}{when}" if country else f"Volcanic eruption at {name}: VEI {vei}{when}"
        url = f"https://volcano.si.edu/volcano.cfm?vn={p['VolcanoNumber']}"
        base = 28 + vei * 11
        lat, lon = p.get("LatitudeDecimal"), p.get("LongitudeDecimal")
        it = S.item("GVP", "GVP", f"E{p['Activity_ID']}", head, "natural disaster", url, t, lat, lon, loc, base, extra={"vei": vei, "volcano": p["VolcanoNumber"], "day_known": day_known})
        tags = ["#Volcano", tag(name) or "#Eruption", tag(country) or "#GVP"]
        out.append(dict(it=it, title=head, loc=loc, tags=tags, link=url, src="Smithsonian GVP", kind="volcano", cat="natural disaster"))
    log("gvp eruptions VEI2+", len(out)); return out

# ------------------------------------------------------------------ NTSB major investigations
def ntsb(raw):
    rows = json.load(open(os.path.join(raw, "ntsb_major.json")))
    l1 = json.load(open(os.path.join(raw, "ntsb_links.json"))); l2 = json.load(open(os.path.join(raw, "ntsb_links2.json")))
    out = []
    for x in rows:
        n = x["NtsbNo"]; mode = x.get("Mode") or ""
        if l1.get(n, ["", False])[0] == "200" and l1[n][1]: link = f"https://www.ntsb.gov/investigations/Pages/{n}.aspx"
        elif mode == "Aviation" and (l2.get(n) or {}).get("pdf", "").startswith("200 application/pdf"):
            link = f"https://data.ntsb.gov/carol-repgen/api/Aviation/ReportMain/GenerateNewestReport/{x['Mkey']}/pdf"
        else: link = ""
        if not link: B.DROPPED["ntsb_nolink"] += 1; continue
        ed = x["EventDate"]; t = datetime.strptime(ed, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if not keep_t(t.strftime("%Y-%m-%dT%H:%M:%SZ")): continue
        city, st, ctry = (x.get("City") or "").strip(), (x.get("State") or "").strip(), (x.get("Country") or "").strip()
        loc = ", ".join(z for z in (city, st if ctry in ("United States", "") else ctry) if z) or ctry or "United States"
        veh = " ".join(z for z in ((x.get("VehicleMake") or "").title() if (x.get("VehicleMake") or "").isupper() else (x.get("VehicleMake") or ""), x.get("VehicleModel") or "") if z).strip()
        what = {"Aviation": "aircraft accident", "Railroad": "rail accident", "Highway": "highway accident", "Marine": "marine accident", "Pipeline": "pipeline accident", "Hazmat": "hazardous materials accident"}.get(mode, "transportation accident")
        fatal = x.get("HighestInjuryLevel") == "Fatal"
        head = f"{'Fatal ' if fatal else ''}{veh + ' ' if mode == 'Aviation' and veh else ''}{what if not (mode == 'Aviation' and veh) else 'accident'} in {loc}: NTSB major investigation"
        head = head[0].upper() + head[1:]
        base = 38 + (22 if fatal else 0) + (8 if int(str(x.get("InjuryOnboardCount") or "0") if str(x.get("InjuryOnboardCount") or "0").isdigit() else 0) >= 10 else 0)
        it = S.item("NTSB", "NTSB", n, head, "accident", link, t, None, None, loc, base, extra={"ntsb_no": n, "mode": mode})
        tags = ["#NTSB", {"Aviation": "#Aviation", "Railroad": "#Rail", "Highway": "#Highway", "Marine": "#Marine", "Pipeline": "#Pipeline", "Hazmat": "#Hazmat"}.get(mode, "#Transport"), tag(st or ctry) or "#Accident"]
        out.append(dict(it=it, title=head, loc=loc, tags=tags, link=link, src="NTSB", kind="ntsb", cat="accident"))
    log("ntsb major", len(out), "dropped no link", B.DROPPED["ntsb_nolink"]); return out

# ------------------------------------------------------------------ CISA KEV
def kev(raw):
    out = []
    for v in json.load(open(os.path.join(raw, "kev.json")))["vulnerabilities"]:
        cve = v["cveID"]; da = v["dateAdded"]
        t = datetime.strptime(da, "%Y-%m-%d").replace(tzinfo=UTC)
        if not keep_t(t.strftime("%Y-%m-%dT%H:%M:%SZ")) or not re.match(r"^CVE-\d{4}-\d{4,}$", cve): continue
        vend = (v.get("vendorProject") or "").strip(); prod = (v.get("product") or "").strip()
        name = re.sub(r"\s+", " ", v.get("vulnerabilityName") or f"{vend} {prod} vulnerability").strip()
        ransom = v.get("knownRansomwareCampaignUse") == "Known"
        head = f"CISA adds {name} ({cve}) to its exploited-vulnerabilities catalog" + (", used in ransomware campaigns" if ransom else "")
        url = f"https://nvd.nist.gov/vuln/detail/{cve}"
        base = 36 + (14 if ransom else 0) + (6 if re.search(r"remote code|execution|authentication bypass", v.get("shortDescription") or "", re.I) else 0)
        it = S.item("CISA KEV", "CISA", cve, head, "cyber", url, t, None, None, "Global", base, extra={"cve": cve, "vendor": vend, "product": prod, "ransomware": ransom})
        tags = ["#CISA", "#KEV", tag(vend) or "#CVE"]
        out.append(dict(it=it, title=head[:240], loc="Global", tags=tags, link=url, src="CISA KEV", kind="kev", cat="cyber"))
    log("kev", len(out)); return out

# ------------------------------------------------------------------ SWPC solar flares and GFZ geomagnetic storms
def solar(raw):
    out = []; seen = set()
    sw = os.path.join(raw, "swpc")
    for fn in sorted(glob.glob(os.path.join(sw, "*.txt"))):
        day = os.path.basename(fn)[:8]
        for line in open(fn, errors="ignore"):
            if " XRA " not in line: continue
            p = line.split()
            try:
                i = p.index("XRA"); cls = p[i + 2]
            except (ValueError, IndexError): continue
            if not re.match(r"^X\d+(\.\d)?$", cls): continue
            tm = [z for z in p[:i] if re.match(r"^(\d{4}|////)$", z)]
            mx = tm[1] if len(tm) > 1 and tm[1] != "////" else (tm[0] if tm else "0000")
            if not re.match(r"^\d{4}$", mx): mx = "0000"
            t = dt(int(day[:4]), int(day[4:6]), int(day[6:8]), int(mx[:2]) % 24, int(mx[2:]) % 60)
            key = (day, mx, cls)
            if key in seen or not keep_t(t.strftime("%Y-%m-%dT%H:%M:%SZ")): continue
            seen.add(key)
            val = float(cls[1:])
            band = "Extreme" if val >= 10 else "Major"
            head = f"{cls} solar flare peaks at {mx[:2]}:{mx[2:]} UTC" + (f", an extreme X-class event" if val >= 10 else "")
            url = f"https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_event_reports/{day[:4]}/{day[4:6]}/{day}events.txt"
            it = S.item("NOAA SWPC", "SWPC", f"flare-{day}-{mx}-{cls}", head, "space weather", url, t, None, None, "Sun (Earth-facing impacts)", 40 + min(40, val * 5), extra={"class": cls})
            out.append(dict(it=it, title=head, loc="Sun", tags=["#SolarFlare", "#SpaceWeather", "#NOAA"], link=url, src="NOAA SWPC", kind="solar", cat="space weather"))
    nfl = len(out)
    kp = json.load(open(os.path.join(raw, "kp.json")))
    days = collections.OrderedDict()
    for t_, k in zip(kp["datetime"], kp["Kp"]):
        if k >= 7.66: days.setdefault(t_[:10], []).append((k, t_))
    # one row per storm: consecutive days merge, dated at the 3-hour interval with the highest Kp
    groups = []; prev = None
    for d_ in days:
        dd = datetime.strptime(d_, "%Y-%m-%d").date()
        if prev and (dd - prev).days <= 1: groups[-1].append(d_)
        else: groups.append([d_])
        prev = dd
    for g in groups:
        best = max((x for d_ in g for x in days[d_]), key=lambda x: (x[0], -ord(x[1][1])))
        k, t_ = best
        t = datetime.strptime(t_[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
        if not keep_t(t.strftime("%Y-%m-%dT%H:%M:%SZ")): continue
        g5 = k >= 8.99
        lab = {9.0: "9", 8.667: "9-", 8.333: "8+", 8.0: "8", 7.667: "8-"}.get(round(k, 3), f"{k:.1f}")
        head = f"{'Extreme (G5)' if g5 else 'Severe (G4)'} geomagnetic storm: Kp reaches {lab}"
        d0 = t.strftime("%Y-%m-%d")
        url = f"https://kp.gfz.de/app/json/?start={d0}T00:00:00Z&end={d0}T23:59:59Z&index=Kp"
        it = S.item("GFZ Kp", "GFZ", f"kp-{d0}", head, "space weather", url, t, None, None, "Earth (global)", 58 if g5 else 48, extra={"kp": k})
        out.append(dict(it=it, title=head, loc="Earth (global)", tags=["#GeomagneticStorm", "#SpaceWeather", "#Aurora"], link=url, src="GFZ Kp index", kind="solar", cat="space weather"))
    log("solar: X flares", nfl, "G4/G5 storms", len(out) - nfl); return out

def write(out_dir, name, rows):
    for r in rows: r[10] = [t for t in r[10] if t]      # a tag longer than 26 characters comes back empty from tag(): never store it
    rows.sort(key=lambda r: (r[1], r[0]))
    blob = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f: f.write(blob)
    open(os.path.join(out_dir, f"{name}.ndjson.gz.b64"), "w").write(base64.b64encode(buf.getvalue()).decode("ascii") + "\n")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", default="/workspace/archive2000/raw2"); ap.add_argument("--out", default=os.path.join(APP, "archive_wire_data"))
    ap.add_argument("--only", default="")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    plan = [("who", "p2_who_2018_2021", who_backfill), ("gvp", "p2_gvp", gvp), ("ntsb", "p2_ntsb", ntsb), ("kev", "p2_kev", kev), ("solar", "p2_solar", solar)]
    sc = Scorer(); summary = {}
    for key, name, fn in plan:
        if only and key not in only: continue
        items = fn(a.raw); rows = []; bad = 0
        for x in items:
            it = x["it"]
            if not re.match(r"^https?://", x["link"] or ""): bad += 1; continue
            score, rank, conf = sc.score(it)
            rows.append([it["id"], it["event_time"], x["title"][:240], x["cat"], x["loc"][:120], it["lat"], it["lon"], score, rank, conf, x["tags"], x["src"], x["link"], x["kind"]])
        write(a.out, name, rows); summary[name] = (len(rows), bad)
        log(name, len(rows), "rows; dropped no link", bad)
    log("summary", json.dumps(summary))

if __name__ == "__main__": main()
