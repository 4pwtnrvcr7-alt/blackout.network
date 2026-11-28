#!/usr/bin/env python3
"""Wire archive builder, phase 3 (Nov 27 2026).

Adds shards app/archive_wire_data/p3_<source>.ndjson.gz.b64 (same row layout as phases 1-2):
  p3_storm   NOAA NCEI Storm Events, significant only (5+ deaths, 50+ injuries, $250M+ damage, or F4/F5/EF4/EF5).
             Link is the live per-event page https://www.ncei.noaa.gov/access/storm-events-database/event-details/{EVENT_ID}
             (the modernized SPA). A row is shipped only after the event-details API confirms that event_id is on the page.
             No yearly CSV links.
  p3_nvd     NVD records published 2000-01-01 .. 2020-12-31 with CVSS base score 9.0+ (v2, v3.0 or v3.1). Link: NVD detail page.
  p3_wiki    Wikipedia Current events daily archive pages, 2002-01-01 .. 2024-10-28 (the portal has no daily pages before 2002).
             One row per day whose page exists and is not an empty stub, linking to Portal:Current events/YYYY Month D.
  p3_who     WHO Disease Outbreak News gap fill: leftover items dated from the URL, from PublicationDateAndTime when it agrees
             with the URL year (and is not a known site-migration batch), or from the date printed on the item page.
  p3_gvp     Smithsonian GVP eruptions, VEI 2+ (only written if a sample of volcano.si.edu pages returns 200 and shows the volcano).

Every row has ONE direct source link that shows the record, and no write-up. Ranks come from the scanner's own scoring (read-only).
Usage: python3 tools/build_wire_archive_p3.py [--raw2 ...] [--raw3 ...] [--only storm,nvd,wiki,who,gvp]
"""
import os, sys, re, json, glob, gzip, base64, io, argparse, collections, urllib.request
from datetime import datetime, timezone, date, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_wire_archive as B
from build_wire_archive import S, tag, smart, log, keep_t, Scorer, STATES, APP, UA

UTC = timezone.utc
def dt_iso(t): return datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)

# ------------------------------------------------------------------ Storm Events
def money(n):
    if n >= 1e9: s=f"${n/1e9:.1f} billion".replace(".0 billion"," billion")
    elif n >= 1e6: s=f"${n/1e6:.0f} million" if n>=10e6 else f"${n/1e6:.1f} million"
    elif n >= 1e3: s=f"${n/1e3:.0f},000".replace(",000,000"," million") if False else f"${int(n):,}"
    else: s=f"${int(n)}"
    return s

def dmg(s):
    s=(s or "").strip()
    if not s: return 0
    m=re.match(r"^([\d.]+)([KMB]?)$",s)
    if not m: return 0
    return float(m.group(1))*{"":1,"K":1e3,"M":1e6,"B":1e9}[m.group(2)]

def storm(raw2, raw3):
    cand=json.load(open(os.path.join(raw3,"storm_cand.json")))
    links=json.load(open(os.path.join(raw3,"storm_links.json")))
    ok=links.get("ok") or {}
    out=[]; skipped=0
    for r in cand:
        eid=str(int(r["EVENT_ID"]))
        if ok.get(eid) is not True:
            skipped += 1; continue
        ym=r["BEGIN_YEARMONTH"]; day=int(r["BEGIN_DAY"] or 1); tm=int(r["BEGIN_TIME"] or 0)
        y,mo=int(ym[:4]),int(ym[4:6])
        t=datetime(y,mo,day,(tm//100)%24,tm%100,tzinfo=UTC)
        iso=t.strftime("%Y-%m-%dT%H:%M:%SZ")
        if not keep_t(iso): continue
        typ=(r["EVENT_TYPE"] or "Severe weather").strip()
        scale=(r.get("TOR_F_SCALE") or "").strip()
        st=(r.get("STATE") or "").title()
        cz=smart((r.get("CZ_NAME") or "").replace(" CO.", "").replace(" PARISH", "").title())
        loc=", ".join(x for x in (cz, st) if x) or "United States"
        deaths=int(r["DEATHS_DIRECT"] or 0)+int(r["DEATHS_INDIRECT"] or 0)
        inj=int(r["INJURIES_DIRECT"] or 0)+int(r["INJURIES_INDIRECT"] or 0)
        pd=dmg(r["DAMAGE_PROPERTY"])+dmg(r["DAMAGE_CROPS"])
        if typ.lower()=="tornado" and scale: what=f"{scale} tornado"
        elif typ.lower()=="hurricane (typhoon)": what="Hurricane"
        else: what=typ
        head=f"{what[0].upper()+what[1:]} in {loc}"
        bits=[]
        if deaths: bits.append(f"{deaths} death{'s' if deaths!=1 else ''}")
        if inj>=50: bits.append(f"{inj} injuries")
        if pd>=1e6: bits.append(f"{money(pd)} in damage")
        if bits: head += ": " + ", ".join(bits)
        url=f"https://www.ncei.noaa.gov/access/storm-events-database/event-details/{eid}"
        base=28 + min(40, deaths*4) + (10 if scale in ("EF4","EF5","F4","F5") else 0) + (8 if pd>=1e9 else 0)
        it=S.item("NOAA Storm Events","NOAA",f"SE{eid}",head,"natural disaster",url,t, r.get("BEGIN_LAT") or None, r.get("BEGIN_LON") or None, loc, base,
                  extra={"event_id":eid,"type":typ,"deaths":deaths,"damage":pd})
        tags=["#StormEvents", tag(typ) or "#SevereWeather", tag(st) or "#USA"]
        out.append(dict(it=it,title=head,loc=loc,tags=tags,link=url,src="NOAA Storm Events",kind="stormevt",cat="natural disaster"))
    log("storm events",len(out),"skipped (unverified link)",skipped); return out

# ------------------------------------------------------------------ NVD
def nvd(raw3):
    out=[]
    for v in json.load(open(os.path.join(raw3,"nvd_critical.json"))):
        pub=v["published"]
        t=pub[:19]+"Z" if not pub.endswith("Z") else pub
        if not keep_t(t) or not (t[:10] <= "2020-12-31"): continue
        cve=v["cve"]; score=v["score"]
        desc=re.sub(r"\s+"," ",v.get("desc") or "").strip()
        desc=re.sub(r"\s*\([^)]*CVE[^)]*\)\s*$","",desc)
        short=desc.split(".")[0].strip()
        vend=(v.get("vendor") or "").replace("_"," ").strip()
        if vend.lower() in ("n/a","unknown",""): vend=""
        suffix=f" ({cve}, CVSS {score:g})"
        prefix="Critical NVD record: "
        room=240-len(prefix)-len(suffix)
        if not short: head=f"Critical NVD record: {cve}, CVSS {score:g}"
        else:
            if len(short)>room: short=short[:max(0,room-1)].rsplit(" ",1)[0]+"…"
            head=prefix+short+suffix
        url=f"https://nvd.nist.gov/vuln/detail/{cve}"
        base=36 + (8 if score>=9.8 else 0) + (8 if score>=10 else 0)
        it=S.item("NVD","NVD",cve,head,"cyber",url,dt_iso(t),None,None,"Global",base,extra={"cve":cve,"cvss":score,"metric":v.get("metric")})
        tags=["#NVD","#CVE", tag(vend) if vend and tag(vend) else "#Critical"]
        out.append(dict(it=it,title=head[:240],loc="Global",tags=tags,link=url,src="NVD",kind="nvd",cat="cyber"))
    log("nvd critical",len(out)); return out

# ------------------------------------------------------------------ Wikipedia current events
def wiki(raw3):
    pages=json.load(open(os.path.join(raw3,"wiki_days.json")))
    out=[]
    for title, meta in pages.items():
        if (meta.get("len") or 0) < 200: continue
        # "Portal:Current events/2002 January 1"
        m=re.match(r"^Portal:Current events/(\d{4}) ([A-Za-z]+) (\d{1,2})$", title)
        if not m: continue
        y, mon, d = int(m.group(1)), m.group(2), int(m.group(3))
        try: t=datetime.strptime(f"{y} {mon} {d}", "%Y %B %d").replace(tzinfo=UTC)
        except ValueError: continue
        iso=t.strftime("%Y-%m-%dT%H:%M:%SZ")
        if not keep_t(iso): continue
        head=f"Wikipedia current events for {mon} {d}, {y}"
        # article URL uses underscores
        url="https://en.wikipedia.org/wiki/"+title.replace(" ","_")
        it=S.item("Wikipedia Current Events","Wikipedia",f"WCE-{y:04d}{t.month:02d}{d:02d}",head,"other",url,t,None,None,"Worldwide",18,extra={"wiki":title})
        tags=["#Wikipedia","#CurrentEvents",f"#{y}"]
        out.append(dict(it=it,title=head,loc="Worldwide",tags=tags,link=url,src="Wikipedia Current Events",kind="wiki",cat="other"))
    log("wiki current events days",len(out)); return out

# ------------------------------------------------------------------ WHO gap fill
def who_gap(raw3):
    # reuse phase 1/2 who_items with a datefn that only returns dates for leftover, already-resolved items
    dated={v["UrlName"]: v["_t"] for v in json.load(open(os.path.join(raw3,"who_dated_full.json")))}
    have=set()
    for fn in glob.glob(os.path.join(APP,"archive_wire_data","*.ndjson.gz.b64")):
        if os.path.basename(fn).startswith("p3_"): continue
        for line in gzip.decompress(base64.b64decode(open(fn,"rb").read())).decode().splitlines():
            r=json.loads(line)
            if r[11]=="WHO Disease Outbreak News": have.add(r[0])
    def datefn(v, url_name):
        t=dated.get(url_name)
        return t if t and keep_t(t) else None
    items=B.who_items(os.path.join(raw3,"..","raw"), datefn=datefn)
    out=[]
    for x in items:
        if x["it"]["id"] in have: continue
        # tidy "Of The" in locations (same as phase 2)
        fixed=re.sub(r"\b(Of|The|And)\b", lambda m: m.group(1).lower(), x["loc"])
        x["loc"]=x["it"]["location"]=fixed
        x["tags"]=[t for t in x["tags"] if t] or ["#WHO","#Outbreak"]
        out.append(x)
    log("who gap fill",len(out)); return out

# ------------------------------------------------------------------ GVP (only if links work)
def gvp_ok(raw2, sample=6):
    """Return True only if volcano.si.edu serves real volcano pages, not the 403 maintenance screen."""
    import random
    feats=json.load(open(os.path.join(raw2,"gvp_e.json")))["features"]
    vns=sorted({f["properties"]["VolcanoNumber"] for f in feats if (f["properties"].get("ExplosivityIndexMax") or 0)>=2 and 2000<=(f["properties"].get("StartDateYear") or 0)<=2024})
    if not vns: return False
    random.seed(3); pick=random.sample(vns, min(sample,len(vns)))
    ok=0
    for vn in pick:
        url=f"https://volcano.si.edu/volcano.cfm?vn={vn}"
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                code=r.status; body=r.read(2000).decode("utf-8","ignore")
        except Exception as ex:
            log("gvp sample fail", vn, type(ex).__name__); return False
        if code!=200 or re.search(r"temporarily unavailable|TEMPORARY SERVICE", body, re.I):
            log("gvp sample not ready", vn, code); return False
        ok += 1
    log("gvp sample ok", ok); return ok==len(pick)

def gvp(raw2):
    # import the phase-2 builder's gvp when present; otherwise a local copy
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_wire_archive_p2 as P2
    return P2.gvp(raw2)

def write(out_dir, name, rows):
    for r in rows: r[10]=[t for t in r[10] if t]
    rows.sort(key=lambda r: (r[1], r[0]))
    blob="".join(json.dumps(r, ensure_ascii=False, separators=(",",":"))+"\n" for r in rows).encode("utf-8")
    buf=io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f: f.write(blob)
    open(os.path.join(out_dir, f"{name}.ndjson.gz.b64"),"w").write(base64.b64encode(buf.getvalue()).decode("ascii")+"\n")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw2", default="/workspace/archive2000/raw2")
    ap.add_argument("--raw3", default="/workspace/archive2000/raw3")
    ap.add_argument("--out", default=os.path.join(APP,"archive_wire_data"))
    ap.add_argument("--only", default="")
    a=ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    only=set(filter(None, a.only.split(",")))
    plan=[("storm","p3_storm", lambda: storm(a.raw2,a.raw3)),
          ("nvd","p3_nvd", lambda: nvd(a.raw3)),
          ("wiki","p3_wiki", lambda: wiki(a.raw3)),
          ("who","p3_who", lambda: who_gap(a.raw3))]
    if not only or "gvp" in only:
        if gvp_ok(a.raw2):
            plan.append(("gvp","p3_gvp", lambda: gvp(a.raw2)))
        else:
            log("gvp held back: volcano.si.edu not serving record pages")
    sc=Scorer(); summary={}
    for key,name,fn in plan:
        if only and key not in only: continue
        items=fn(); rows=[]; bad=0
        for i,x in enumerate(items):
            it=x["it"]
            if not re.match(r"^https?://", x["link"] or ""): bad+=1; continue
            score,rank,conf=sc.score(it)
            rows.append([it["id"], it["event_time"], x["title"][:240], x["cat"], x["loc"][:120], it["lat"], it["lon"], score, rank, conf, x["tags"], x["src"], x["link"], x["kind"]])
            if i and i%5000==0: log("scored",name,i)
        write(a.out,name,rows); summary[name]=(len(rows),bad)
        log(name,len(rows),"rows; dropped no link",bad)
    log("summary", json.dumps(summary))

if __name__=="__main__": main()
