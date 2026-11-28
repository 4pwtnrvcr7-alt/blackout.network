"""Live status per cloud region and per CDN edge city for the /grid map (Nov 28 2026, Matt pt2098u).
Read-only and keyless. Every source is a provider's own public status feed; none is scraped past a bot check:
  AWS Health  https://health.aws.amazon.com/public/currentevents      (open events, each tagged with its region)
  Azure       https://azure.status.microsoft/en-us/status/feed/       (active incidents; the region is read from the title)
  Google      https://status.cloud.google.com/incidents.json          (incidents with no end time; region read from the text)
  Oracle OCI  https://ocistatus.oraclecloud.com/api/v2/components.json (per-region, per-service health reports)
  Cloudflare  https://www.cloudflarestatus.com/api/v2/components.json (one component per edge city, named "City, Country - (IATA)")
Level scale (same as the other Grid layers): 0 operational, 1 degraded (orange), 2 outage (red), 3 major outage (red), -1 unknown (grey).
A feed that cannot be read gives -1 for its regions. A region is green only when its provider's feed was read and lists nothing for it.
No feed gives per-site status for third-party colocation data centers or for cell towers: those stay grey (see NOTES)."""
import csv, json, os, re, time
from datetime import datetime, timezone
BASE = os.path.dirname(os.path.abspath(__file__))

# (provider, key, display name, lon, lat). key = the provider's own region id.
AWS_REGIONS = [
 ("us-east-1", "US East (N. Virginia)", -77.5, 39.0), ("us-east-2", "US East (Ohio)", -82.9, 40.0), ("us-west-2", "US West (Oregon)", -119.7, 45.6), ("us-west-1", "US West (N. California)", -121.9, 37.4),
 ("ca-central-1", "Canada (Central)", -73.6, 45.5), ("ca-west-1", "Canada West (Calgary)", -114.1, 51.05), ("sa-east-1", "South America (São Paulo)", -46.6, -23.5), ("mx-central-1", "Mexico (Central)", -100.4, 20.6),
 ("eu-west-1", "Europe (Ireland)", -6.3, 53.3), ("eu-central-1", "Europe (Frankfurt)", 8.7, 50.1), ("eu-west-2", "Europe (London)", -0.1, 51.5), ("eu-west-3", "Europe (Paris)", 2.35, 48.85),
 ("eu-north-1", "Europe (Stockholm)", 18.1, 59.3), ("eu-south-1", "Europe (Milan)", 9.19, 45.46), ("ap-northeast-1", "Asia Pacific (Tokyo)", 139.7, 35.7), ("ap-northeast-2", "Asia Pacific (Seoul)", 126.98, 37.57),
 ("ap-northeast-3", "Asia Pacific (Osaka)", 135.5, 34.69), ("ap-southeast-1", "Asia Pacific (Singapore)", 103.8, 1.35), ("ap-southeast-2", "Asia Pacific (Sydney)", 151.2, -33.9), ("ap-southeast-3", "Asia Pacific (Jakarta)", 106.85, -6.2),
 ("ap-south-1", "Asia Pacific (Mumbai)", 72.9, 19.1), ("ap-east-1", "Asia Pacific (Hong Kong)", 114.17, 22.32), ("il-central-1", "Israel (Tel Aviv)", 34.78, 32.08), ("me-south-1", "Middle East (Bahrain)", 50.6, 26.1),
 ("me-central-1", "Middle East (UAE)", 55.3, 25.2), ("af-south-1", "Africa (Cape Town)", 18.4, -33.9),
]
AZURE_REGIONS = [   # the match text must be the name Azure writes in its status feed
 ("East US", "East US (Virginia)", -78.4, 37.4), ("Central US", "Central US (Iowa)", -93.6, 41.6), ("South Central US", "South Central US (Texas)", -98.5, 29.4), ("West US 2", "West US 2 (Washington)", -119.9, 47.2),
 ("North Europe", "North Europe (Ireland)", -6.25, 53.35), ("West Europe", "West Europe (Netherlands)", 4.9, 52.4), ("UK South", "UK South (London)", -0.12, 51.5), ("Southeast Asia", "Southeast Asia (Singapore)", 103.85, 1.28),
 ("Japan East", "Japan East (Tokyo)", 139.77, 35.68), ("Australia East", "Australia East (NSW)", 151.2, -33.86), ("Brazil South", "Brazil South (São Paulo)", -46.63, -23.55), ("Central India", "Central India (Pune)", 73.9, 18.6),
]
AZURE_OTHER = ["East US 2", "West US", "West US 3", "North Central US", "West Central US", "Canada Central", "Canada East", "UK West", "France Central", "Germany West Central", "Switzerland North", "Norway East", "Sweden Central",
               "East Asia", "Korea Central", "Japan West", "Australia Southeast", "Australia Central", "South India", "West India", "UAE North", "South Africa North", "Qatar Central", "Italy North", "Poland Central", "Spain Central", "Israel Central", "Mexico Central"]
GCP_REGIONS = [
 ("us-east4", "us-east4 (N. Virginia)", -77.4, 39.1), ("us-central1", "us-central1 (Iowa)", -95.9, 41.3), ("us-west1", "us-west1 (Oregon)", -121.2, 45.6), ("us-east1", "us-east1 (South Carolina)", -80.0, 33.2),
 ("europe-west1", "europe-west1 (Belgium)", 3.8, 50.5), ("europe-west3", "europe-west3 (Frankfurt)", 8.68, 50.11), ("asia-northeast1", "asia-northeast1 (Tokyo)", 139.69, 35.69), ("asia-southeast1", "asia-southeast1 (Singapore)", 103.7, 1.3),
 ("australia-southeast1", "australia-southeast1 (Sydney)", 151.21, -33.87), ("southamerica-east1", "southamerica-east1 (São Paulo)", -46.64, -23.55), ("asia-south1", "asia-south1 (Mumbai)", 72.88, 19.08),
]
OCI_REGIONS = [   # OCI canonical region id -> display name, lon, lat (commercial regions; the "mc-" multicloud copies are left out)
 ("us-ashburn-1", "US East (Ashburn)", -77.49, 39.04), ("us-phoenix-1", "US West (Phoenix)", -112.07, 33.45), ("us-sanjose-1", "US West (San Jose)", -121.89, 37.34), ("us-chicago-1", "US Midwest (Chicago)", -87.63, 41.88),
 ("us-columbus-1", "US Central (Columbus)", -83.0, 39.96), ("us-boardman-1", "US West (Boardman)", -119.7, 45.84), ("ca-toronto-1", "Canada Southeast (Toronto)", -79.38, 43.65), ("ca-montreal-1", "Canada Southeast (Montreal)", -73.57, 45.5),
 ("mx-queretaro-1", "Mexico Central (Querétaro)", -100.39, 20.59), ("mx-monterrey-1", "Mexico Northeast (Monterrey)", -100.32, 25.69), ("sa-saopaulo-1", "Brazil East (São Paulo)", -46.63, -23.55), ("sa-vinhedo-1", "Brazil Southeast (Vinhedo)", -46.98, -23.03),
 ("sa-santiago-1", "Chile Central (Santiago)", -70.65, -33.45), ("sa-bogota-1", "Colombia Central (Bogotá)", -74.07, 4.71), ("uk-london-1", "UK South (London)", -0.13, 51.51), ("uk-cardiff-1", "UK West (Newport)", -3.0, 51.59),
 ("eu-frankfurt-1", "Germany Central (Frankfurt)", 8.68, 50.11), ("eu-amsterdam-1", "Netherlands Northwest (Amsterdam)", 4.9, 52.37), ("eu-paris-1", "France Central (Paris)", 2.35, 48.85), ("eu-marseille-1", "France South (Marseille)", 5.37, 43.3),
 ("eu-milan-1", "Italy Northwest (Milan)", 9.19, 45.46), ("eu-madrid-1", "Spain Central (Madrid)", -3.7, 40.42), ("eu-stockholm-1", "Sweden Central (Stockholm)", 18.07, 59.33), ("eu-zurich-1", "Switzerland North (Zurich)", 8.54, 47.38),
 ("eu-jovanovac-1", "Serbia Central (Jovanovac)", 20.9, 44.1), ("il-jerusalem-1", "Israel Central (Jerusalem)", 35.22, 31.77), ("me-dubai-1", "UAE East (Dubai)", 55.3, 25.2), ("me-abudhabi-1", "UAE Central (Abu Dhabi)", 54.37, 24.45),
 ("me-jeddah-1", "Saudi Arabia West (Jeddah)", 39.17, 21.54), ("me-riyadh-1", "Saudi Arabia Central (Riyadh)", 46.68, 24.71), ("af-johannesburg-1", "South Africa Central (Johannesburg)", 28.05, -26.2), ("af-casablanca-1", "Morocco West (Casablanca)", -7.59, 33.57),
 ("ap-mumbai-1", "India West (Mumbai)", 72.88, 19.08), ("ap-hyderabad-1", "India South (Hyderabad)", 78.49, 17.39), ("ap-tokyo-1", "Japan East (Tokyo)", 139.69, 35.69), ("ap-osaka-1", "Japan Central (Osaka)", 135.5, 34.69),
 ("ap-seoul-1", "South Korea Central (Seoul)", 126.98, 37.57), ("ap-chuncheon-1", "South Korea North (Chuncheon)", 127.73, 37.88), ("ap-singapore-1", "Singapore (Singapore)", 103.82, 1.35), ("ap-sydney-1", "Australia East (Sydney)", 151.21, -33.87),
 ("ap-melbourne-1", "Australia Southeast (Melbourne)", 144.96, -37.81), ("ap-batam-1", "Indonesia North (Batam)", 104.03, 1.13),
]
NOTES = dict(
    dc="Grey: no free, machine-readable status feed exists for individual colocation data centers (PeeringDB lists the sites; Equinix and other operators publish no open per-site status, and Equinix's page blocks automated readers). Cloud regions and CDN edge cities have live status.",
    towers="Grey: the FCC publishes cell sites out of service by county only while it has activated its disaster reporting system (DIRS), and fcc.gov blocks automated readers, so there is no live feed to read. FCC registration data (ASR) says where a tower stands, not whether it is working.")

def decode(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"): return b.decode("utf-16", "replace")
    return b.decode("utf-8-sig", "replace")
def _day(ts):
    try: return time.strftime("%b %-d, %Y", time.gmtime(int(ts)))
    except Exception: return ""
def _cut(t, n):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    if len(t) <= n: return t
    return t[:n].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
def _rec(level, status, **k): return dict(level=level, status=_cut(status, 300), **k)

# ---------------------------------------------------------------- AWS
def aws_regions(text):
    """text = body of /public/currentevents. -> {region_id: {level,status,since}} for the regions in AWS_REGIONS."""
    ev = json.loads(text) if text.strip() else []
    out = {k: _rec(0, "No open AWS Health events for this region", src="AWS Health", url="https://health.aws.amazon.com/health/status") for k, *_ in AWS_REGIONS}
    glob = []
    for e in ev:
        try: reg = (e.get("arn") or "").split(":")[3]
        except Exception: reg = ""
        st = str(e.get("status") or "1"); lv = 3 if st == "3" else 1
        msg = f'{e.get("service_name") or "Service"}: {e.get("summary") or ""}'.strip(": ")
        since = int(e.get("date") or 0); old = since and time.time() - since > 72 * 3600
        log = e.get("event_log") or []
        if log and log[-1].get("message"): msg += ". " + _cut(log[-1]["message"], 200)
        if st != "3" and old: msg = "Long-running event since " + _day(since) + ". " + msg
        elif old: msg = "Open since " + _day(since) + ". " + msg
        if reg in out:
            if lv > out[reg]["level"] or out[reg]["level"] == 0: out[reg].update(level=lv, status=_cut(msg, 300), since=since)
        elif not reg: glob.append((lv, msg, since))
    for lv, msg, since in glob:   # an event with no region applies to every region
        for r in out.values():
            if r["level"] < 1: r.update(level=1, status="AWS lists an open event for all regions: " + msg[:300], since=since)
    return out

# ---------------------------------------------------------------- Azure
_AZ_NAMES = sorted([a[0] for a in AZURE_REGIONS] + AZURE_OTHER, key=len, reverse=True)
_AZ_RE = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in _AZ_NAMES) + r")(?![A-Za-z0-9])", re.I)
def azure_regions(xml_text):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    items = root.findall("./channel/item")
    out = {k: _rec(0, "Azure lists no active incidents", src="Azure status", url="https://azure.status.microsoft/en-us/status") for k, *_ in AZURE_REGIONS}
    for it in items:
        title = (it.findtext("title") or "").strip(); desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        hit = {m.group(1).lower() for m in _AZ_RE.finditer(title + " " + desc)}
        txt = ("Active Azure incident: " + title)[:300]
        if hit:
            for k, *_ in AZURE_REGIONS:
                if k.lower() in hit: out[k].update(level=max(out[k]["level"], 1), status=txt)
        else:   # an incident that names no region could touch any of them
            for r in out.values():
                if r["level"] < 1: r.update(level=1, status="Azure lists an active incident that names no region: " + title[:240])
    return out

# ---------------------------------------------------------------- Google Cloud
_GC_RE = re.compile(r"\b((?:us|europe|asia|australia|southamerica|northamerica|me|africa)-[a-z]+\d+)\b")
def gcp_regions(text):
    d = json.loads(text)
    out = {k: _rec(0, "Google lists no active incidents", src="Google Cloud status", url="https://status.cloud.google.com/") for k, *_ in GCP_REGIONS}
    for i in d:
        if i.get("end"): continue
        mr = i.get("most_recent_update") or {}
        imp = i.get("status_impact") or ""; lv = 3 if imp == "SERVICE_OUTAGE" else 1
        desc = (i.get("external_desc") or "").strip()
        locs = {(l.get("id") or "").lower() for l in (mr.get("affected_locations") or []) + (i.get("currently_affected_locations") or [])}
        locs |= set(_GC_RE.findall(desc + " " + (mr.get("text") or "")[:600]))
        locs = {l for l in locs if l}
        txt = ("Active Google Cloud incident: " + desc)[:300]
        if locs:
            for k, *_ in GCP_REGIONS:
                if k in locs: out[k].update(level=max(out[k]["level"], lv), status=txt)
        else:
            for r in out.values():
                if r["level"] < 1: r.update(level=1, status="Google lists an active incident that names no region: " + desc[:240])
    return out

# ---------------------------------------------------------------- Oracle OCI
def oci_regions(text):
    d = json.loads(text); rep = {r.get("regionCanonicalName"): r for r in d.get("regionHealthReports") or []}
    out = {}
    for k, *_ in OCI_REGIONS:
        r = rep.get(k)
        if not r: continue   # not in the feed: leave it off the map rather than guess
        bad = []
        for s in r.get("serviceHealthReports") or []:
            st = str(s.get("serviceStatus") or "")
            if st and st != "NormalPerformance" or s.get("incidents"): bad.append((s.get("serviceName") or "service", st or "incident"))
        if not bad: out[k] = _rec(0, f"All {len(r.get('serviceHealthReports') or [])} Oracle Cloud services report normal performance", src="Oracle Cloud status", url="https://ocistatus.oraclecloud.com/")
        else:
            worst = 3 if any(re.search(r"outage|unavail|down", s, re.I) for _, s in bad) else 1
            out[k] = _rec(worst, f"{len(bad)} Oracle Cloud service(s) not normal: " + ", ".join(f"{n} ({s})" for n, s in bad[:4]), src="Oracle Cloud status", url="https://ocistatus.oraclecloud.com/")
    return out

# ---------------------------------------------------------------- Cloudflare edge cities
_CF_NAME = re.compile(r"^(.*?)\s*-\s*\(([A-Z]{3})\)\s*$")
CFS = {"operational": (0, "Operational"), "under_maintenance": (0, "Under scheduled maintenance (traffic is re-routed)"), "degraded_performance": (1, "Degraded performance"),
       "partial_outage": (1, "Partial outage"), "major_outage": (3, "Major outage")}
_AP = {}
def _airports():
    if not _AP:
        with open(os.path.join(BASE, "jetdata", "airports.csv"), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                c = (r.get("iata_code") or "").strip()
                if c and r.get("latitude_deg") and (c not in _AP or r.get("type") in ("large_airport",) or (r.get("scheduled_service") == "yes" and _AP[c][2] != "large_airport")):
                    _AP[c] = (float(r["longitude_deg"]), float(r["latitude_deg"]), r.get("type") or "")
    return _AP
def cloudflare_pops(text):
    """-> list of dict(code, name, lon, lat, level, status) for every Cloudflare city component whose IATA code is a known airport."""
    ap = _airports(); out = []
    for c in json.loads(text).get("components") or []:
        m = _CF_NAME.match(c.get("name") or "")
        if not m or m.group(2) not in ap: continue
        lv, word = CFS.get(c.get("status"), (-1, "Status not reported"))
        lon, lat, _ = ap[m.group(2)]
        out.append(dict(code=m.group(2), name=m.group(1), lon=round(lon, 3), lat=round(lat, 3), level=lv, status=word, since=c.get("updated_at")))
    return out

# ---------------------------------------------------------------- everything
_LAST = {}; KEEP_S = 1800
def fetch(http, executor=None):
    """http(url) -> bytes. Returns (markers, sources). markers: list of dict(p, name, lon, lat, level, status, src, url[, edge, code]).
    A feed that fails gives level -1 and a plain 'status feed unreachable' line; nothing is guessed."""
    from concurrent.futures import ThreadPoolExecutor
    urls = dict(aws="https://health.aws.amazon.com/public/currentevents", azure="https://azure.status.microsoft/en-us/status/feed/", gcp="https://status.cloud.google.com/incidents.json",
                oci="https://ocistatus.oraclecloud.com/api/v2/components.json", cloudflare="https://www.cloudflarestatus.com/api/v2/components.json")
    def one(k):
        try: return k, decode(http(urls[k], timeout=28))   # AWS's currentevents answers in 1 to 6 s and sometimes slower
        except Exception as ex: return k, ex
    with ThreadPoolExecutor(5) as ex: raw = dict(ex.map(one, urls))
    markers = []; sources = []
    def table(k, regions, parse, p, label, page):
        t = raw[k]; res = None; err = None
        if isinstance(t, Exception): err = type(t).__name__
        else:
            try: res = parse(t)
            except Exception as e: err = type(e).__name__
        if res is not None: _LAST[k] = (time.time(), res)
        elif k in _LAST and time.time() - _LAST[k][0] < KEEP_S:   # a feed that blinks keeps its last good reading for 30 minutes instead of flipping every dot to grey
            res = _LAST[k][1]; err = None
        n = 0
        for key, nm, lon, lat in regions:
            r = res.get(key) if res is not None else _rec(-1, "Status feed unreachable right now", src=label, url=page)
            if r is None: continue
            markers.append(dict(p=p, name=nm, lon=lon, lat=lat, level=r["level"], status=_cut(r["status"], 300), src=r.get("src", label), url=r.get("url", page))); n += 1
        sources.append(dict(id=k, name=label, url=page, ok=err is None, regions=n, error=err))
    table("aws", AWS_REGIONS, aws_regions, "aws", "AWS Health", "https://health.aws.amazon.com/health/status")
    table("azure", [(a, b, c, d) for a, b, c, d in AZURE_REGIONS], azure_regions, "azure", "Azure status", "https://azure.status.microsoft/en-us/status")
    table("gcp", GCP_REGIONS, gcp_regions, "gcp", "Google Cloud status", "https://status.cloud.google.com/")
    table("oci", OCI_REGIONS, oci_regions, "oci", "Oracle Cloud status", "https://ocistatus.oraclecloud.com/")
    t = raw["cloudflare"]; err = None; pops = []
    if isinstance(t, Exception): err = type(t).__name__
    else:
        try: pops = cloudflare_pops(t)
        except Exception as e: err = type(e).__name__
    if pops: _LAST["cloudflare"] = (time.time(), pops)
    elif "cloudflare" in _LAST and time.time() - _LAST["cloudflare"][0] < KEEP_S: pops = _LAST["cloudflare"][1]; err = None
    for p in pops:
        markers.append(dict(p="cloudflare", edge=True, code=p["code"], name=p["name"], lon=p["lon"], lat=p["lat"], level=p["level"], status=p["status"], src="Cloudflare status", url="https://www.cloudflarestatus.com"))
    sources.append(dict(id="cloudflare", name="Cloudflare status", url="https://www.cloudflarestatus.com", ok=err is None, regions=len(pops), error=err))
    return markers, sources
