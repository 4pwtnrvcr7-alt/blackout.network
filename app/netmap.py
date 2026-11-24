"""/grid: The Grid (was "Network Status"), full-screen outage map (Matt pt1755u, Nov 23 2026).
Nov 24 2026 (Matt pt1795u): the old /grid page is merged in (grid operator layer, "More about the grid" sheet, its loader); /grid 302s here.
Read-only and keyless. Everything is fetched on this node from free public feeds, cached in memory (stale-while-revalidate,
one refresh at a time, never per request) and re-served as one compact JSON:
  IODA (Georgia Tech) country / region / network (ASN) outage signals · official provider status APIs (Atlassian Statuspage JSON,
  Stripe, and the cloud feeds netpages.py already reads) · PeeringDB facilities (data centers, refreshed daily, cached on disk) ·
  DOE/ORNL ODIN power outages via gridpage.py (gridstatus.db).
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json, the newsletter or the QA gate.
Routes: /grid (page, via netpages.py), /api/netmap/data, /api/netmap/dc, /api/netmap/<static file>."""
import os, re, json, time, math, threading, urllib.request, html as _html
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "netmap_static")
FILES = {"gridlayer.js": "application/javascript", "gridlayer.css": "text/css", "net.js": "application/javascript", "net.css": "text/css", "boot.js": "application/javascript", "board.js": "application/javascript", "board.css": "text/css", "cables.json": "application/json", "towers.json": "application/json", "grid.json": "application/json", "gridops.json": "application/json", "logos.svg": "image/svg+xml", "inet.json": "application/json", "hydro.json": "application/json", "inet_ents.json": "application/json"}
E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)
UA = "BlackoutNetwork-status/2.0 (+https://blackout.network/grid; cached, polite)"
IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"; IODA_UI = "https://ioda.inetintel.cc.gatech.edu"
DAYS = 30
SATJS = ("https://cdn.jsdelivr.net/npm/satellite.js@6.0.1/dist/satellite.min.js", "sha384-ks/q8WwP74/nmNCaw/3Kj9Iv2xK5DsfHUJx18wEND2nHyRN7wjPfXjJF1Ejyj1lH")   # same pinned build as /grid/starlink
STRONG = {"bgp", "ping-slash24"}
MAX_EVENT_S = 72 * 3600    # IODA events longer than 3 days are baseline shifts, not outages

def _v(name):
    try: return str(int(os.path.getmtime(os.path.join(STATIC, name))))
    except OSError: return "0"
def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
# IODA back-off (Nov 24 2026): after a failed IODA call, every IODA call in this process fails fast for 1, 2, 4 ... 30 min,
# so the server stops hammering IODA while it is not answering us. One success resets it.
_IB = {"until": 0.0, "n": 0, "err": None}
def ioda_state(): return {"backoff_s": max(0, round(_IB["until"] - time.time())), "fails": _IB["n"], "last_error": _IB["err"]}
def http(url, timeout=12, cap=6_000_000):
    if not url.startswith(IODA): return _http(url, timeout, cap)
    if time.time() < _IB["until"]: raise OSError("IODA back-off")
    try:
        b = _http(url, timeout, cap)
    except Exception as e:
        _IB["n"] += 1; _IB["until"] = time.time() + min(1800, 60 * 2 ** (_IB["n"] - 1)); _IB["err"] = (type(e).__name__ + " " + str(getattr(e, "code", "") or ""))[:60]
        raise
    _IB.update(n=0, until=0.0); return b
def _http(url, timeout=12, cap=6_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"}), timeout=timeout) as r:
        return r.read(cap)
def jget(url, **k): return json.loads(http(url, **k).decode("utf-8", "replace"))
def pts(s):
    if not s: return None
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

# ---------------------------------------------------------------- tiny SWR cache
_C = {}; _BUSY = set(); _L = threading.Lock()
def swr(key, ttl, fn, wait=True):
    hit = _C.get(key)
    if hit and time.time() - hit[0] < ttl: return hit[1]
    def job():
        try: _C[key] = (time.time(), fn())
        except Exception:
            if key in _C: _C[key] = (time.time() - ttl + 120, _C[key][1])   # retry in 2 min, keep the last good copy
        finally:
            with _L: _BUSY.discard(key)
    with _L:
        run = key not in _BUSY
        if run: _BUSY.add(key)
    if hit:
        if run: threading.Thread(target=job, daemon=True, name="nm-" + key).start()
        return hit[1]
    if run: job()
    elif wait:
        for _ in range(450):   # up to 45 s for the very first build after a deploy
            if key in _C: break
            time.sleep(0.1)
    h = _C.get(key); return h[1] if h else None

# ---------------------------------------------------------------- the networks
# id, name, group, kind, feed, official status page, support / contact page
#   kind "sp" = Atlassian Statuspage (feed = base URL) · "np" = netpages.py provider slug · "stripe" · "asn" = IODA (feed = [ASNs])
NETS = [
 # internet service providers (U.S.) and backbone
 ("spectrum", "Spectrum", "isp", "asn", [20115, 33363, 11427, 20001, 10796, 12271, 11351], "https://www.spectrum.net/support/internet/spectrum-outage", "https://www.spectrum.net/contact-us"),
 ("xfinity", "Xfinity (Comcast)", "isp", "asn", [7922, 7015, 21508, 33651], "https://www.xfinity.com/support/status", "https://www.xfinity.com/support/contact-us"),
 ("att", "AT&T Internet", "isp", "asn", [7018], "https://www.att.com/outages/", "https://www.att.com/support/contact-us/"),
 ("verizonfios", "Verizon Fios", "isp", "asn", [701], "https://www.verizon.com/support/residential/service-outage", "https://www.verizon.com/support/contact-us/"),
 ("cox", "Cox", "isp", "asn", [22773], "https://www.cox.com/residential/support/outage-center.html", "https://www.cox.com/residential/contactus.html"),
 ("optimum", "Optimum (Altice)", "isp", "asn", [6128], "https://www.optimum.net/support/outage/", "https://www.optimum.net/contact-us/"),
 ("frontier", "Frontier", "isp", "asn", [5650], "https://frontier.com/helpcenter/categories/internet/troubleshooting/check-for-outages", "https://frontier.com/contactus/contact-us"),
 ("lumen", "Lumen / CenturyLink", "isp", "asn", [209, 3356], "https://www.centurylink.com/home/help/repair/report-a-problem.html", "https://www.lumen.com/en-us/contact-us.html"),
 ("googlefiber", "Google Fiber", "isp", "asn", [16591], "https://fiber.google.com/outages/", "https://support.google.com/fiber/"),
 ("cogent", "Cogent (backbone)", "isp", "asn", [174], "https://www.cogentco.com/en/network/network-status", "https://www.cogentco.com/en/about-cogent/contact-us"),
 ("he", "Hurricane Electric (backbone)", "isp", "asn", [6939], "https://bgp.he.net/AS6939", "https://he.net/contact.html"),
 # mobile carriers
 ("attmobile", "AT&T Wireless", "mobile", "asn", [20057], "https://www.att.com/outages/", "https://www.att.com/support/contact-us/"),
 ("verizonwireless", "Verizon Wireless", "mobile", "asn", [22394, 6167], "https://www.verizon.com/support/check-network-status/", "https://www.verizon.com/support/contact-us/"),
 ("tmobile", "T-Mobile", "mobile", "asn", [21928], "https://www.t-mobile.com/support/coverage/network-status", "https://www.t-mobile.com/contact-us"),
 ("uscellular", "UScellular", "mobile", "asn", [6430], "https://www.uscellular.com/support/network-status", "https://www.uscellular.com/contact-us"),
 # satellite internet
 ("starlink", "Starlink", "sat", "asn", [14593], "https://www.starlink.com/map", "https://www.starlink.com/support"),
 ("viasat", "Viasat", "sat", "asn", [7155], "https://www.viasat.com/support/", "https://www.viasat.com/contact/"),
 ("hughesnet", "HughesNet", "sat", "asn", [6621], "https://www.hughesnet.com/support", "https://www.hughesnet.com/contact-us"),
 # cloud and internet infrastructure
 ("aws", "AWS", "cloud", "np", "aws", "https://health.aws.amazon.com/health/status", "https://aws.amazon.com/contact-us/"),
 ("azure", "Microsoft Azure", "cloud", "np", "azure", "https://azure.status.microsoft/en-us/status", "https://azure.microsoft.com/en-us/support/"),
 ("gcp", "Google Cloud", "cloud", "np", "gcp", "https://status.cloud.google.com/", "https://cloud.google.com/support"),
 ("cloudflare", "Cloudflare", "cloud", "np", "cloudflare", "https://www.cloudflarestatus.com", "https://www.cloudflare.com/support/"),
 ("akamai", "Akamai", "cloud", "np", "akamai", "https://www.akamaistatus.com", "https://www.akamai.com/company/contact"),
 ("digitalocean", "DigitalOcean", "cloud", "sp", "https://status.digitalocean.com", "https://status.digitalocean.com", "https://www.digitalocean.com/support"),
 ("linode", "Akamai Cloud (Linode)", "cloud", "sp", "https://status.linode.com", "https://status.linode.com", "https://www.linode.com/support/"),
 ("github", "GitHub", "cloud", "sp", "https://www.githubstatus.com", "https://www.githubstatus.com", "https://support.github.com/"),
 ("vercel", "Vercel", "cloud", "sp", "https://www.vercel-status.com", "https://www.vercel-status.com", "https://vercel.com/help"),
 ("netlify", "Netlify", "cloud", "sp", "https://www.netlifystatus.com", "https://www.netlifystatus.com", "https://www.netlify.com/support/"),
 ("godaddy", "GoDaddy (domains, DNS)", "cloud", "sp", "https://status.godaddy.com", "https://status.godaddy.com", "https://www.godaddy.com/help"),
 # payments and money
 ("stripe", "Stripe", "pay", "stripe", "https://status.stripe.com/current", "https://status.stripe.com", "https://support.stripe.com/"),
 ("square", "Square", "pay", "sp", "https://www.issquareup.com", "https://www.issquareup.com", "https://squareup.com/help/us/en"),
 ("cashapp", "Cash App", "pay", "sp", "https://status.cash.app", "https://status.cash.app", "https://cash.app/help"),
 ("shopify", "Shopify", "pay", "sp", "https://www.shopifystatus.com", "https://www.shopifystatus.com", "https://help.shopify.com/"),
 ("authorizenet", "Authorize.net", "pay", "sp", "https://status.authorize.net", "https://status.authorize.net", "https://support.authorize.net/"),
 # banking rails and public services (stage 2 piece 3; free public status feeds only)
 ("fedres", "Federal Reserve (FedNow, Fedwire, FedACH)", "rails", "link", "Official status is published on the Federal Reserve page, which does not allow automated reads. Open it to check",
  "https://www.frbservices.org/service-status/", "https://www.frbservices.org/contact-us/"),
 ("column", "Fedwire and FedACH via Column Bank", "rails", "spc", ("https://status.column.com", r"^(FedWire|FedACH)$"), "https://status.column.com", "https://column.com/contact"),
 ("increase", "ACH, wires and RTP via Increase", "rails", "sp", "https://status.increase.com", "https://status.increase.com", "https://increase.com/contact"),
 ("mx", "MX (bank account connections)", "rails", "sp", "https://status.mx.com", "https://status.mx.com", "https://www.mx.com/contact/"),
 ("clover", "Clover (card terminals)", "rails", "sp", "https://status.clover.com", "https://status.clover.com", "https://www.clover.com/help"),
 ("toast", "Toast (restaurant payments)", "rails", "sp", "https://status.toasttab.com", "https://status.toasttab.com", "https://central.toasttab.com/s/support"),
 ("gusto", "Gusto (payroll)", "rails", "sp", "https://status.gusto.com", "https://status.gusto.com", "https://support.gusto.com/"),
 ("logingov", "Login.gov (federal sign-in: SSA, IRS and more)", "gov", "sp", "https://status.login.gov", "https://status.login.gov", "https://login.gov/help/"),
 ("bandwidth", "Bandwidth US voice (carrier behind many calling apps)", "apps", "spc", ("https://status.bandwidth.com", r"United States"), "https://status.bandwidth.com", "https://support.bandwidth.com/"),
 # government and public services (pt1758u board): free public Statuspage feeds only
 ("ssa", "Social Security (SSA.gov, my Social Security)", "gov", "sp", "https://status.ssa.gov", "https://status.ssa.gov", "https://www.ssa.gov/agency/contact/"),
 ("cloudgov", "cloud.gov (hosting for many federal sites)", "gov", "sp", "https://cloudgov.statuspage.io", "https://cloudgov.statuspage.io", "https://cloud.gov/docs/help/"),
 ("plaid", "Plaid (bank links)", "pay", "sp", "https://status.plaid.com", "https://status.plaid.com", "https://support.plaid.com/"),
 ("chime", "Chime", "pay", "sp", "https://status.chime.com", "https://status.chime.com", "https://help.chime.com/"),
 ("affirm", "Affirm", "pay", "sp", "https://status.affirm.com", "https://status.affirm.com", "https://helpcenter.affirm.com/"),
 ("klarna", "Klarna", "pay", "sp", "https://status.klarna.com", "https://status.klarna.com", "https://www.klarna.com/us/customer-service/"),
 ("wise", "Wise", "pay", "sp", "https://status.wise.com", "https://status.wise.com", "https://wise.com/help/"),
 ("coinbase", "Coinbase", "pay", "sp", "https://status.coinbase.com", "https://status.coinbase.com", "https://help.coinbase.com/"),
 ("kraken", "Kraken", "pay", "sp", "https://status.kraken.com", "https://status.kraken.com", "https://support.kraken.com/"),
 ("gemini", "Gemini", "pay", "sp", "https://status.gemini.com", "https://status.gemini.com", "https://support.gemini.com/"),
 # banks, card networks, brokerages and payment apps (pt1785u): most publish no status feed, so these use netwatch.py signals
 ("wellsfargo", "Wells Fargo", "bank", "watch", "wellsfargo", None, "https://www.wellsfargo.com/help/"),
 ("chase", "Chase (JPMorgan Chase)", "bank", "watch", "chase", None, "https://www.chase.com/digital/customer-service"),
 ("bofa", "Bank of America", "bank", "watch", "bofa", None, "https://www.bankofamerica.com/customer-service/contact-us/"),
 ("citi", "Citi", "bank", "watch", "citi", None, "https://online.citi.com/US/ag/contactus"),
 ("capitalone", "Capital One", "bank", "watch", "capitalone", None, "https://www.capitalone.com/contact/"),
 ("usbank", "U.S. Bank", "bank", "watch", "usbank", None, "https://www.usbank.com/customer-service.html"),
 ("pnc", "PNC", "bank", "watch", "pnc", None, "https://www.pnc.com/en/customer-service.html"),
 ("truist", "Truist", "bank", "watch", "truist", None, "https://www.truist.com/contact-us"),
 ("td", "TD Bank", "bank", "watch", "td", None, "https://www.td.com/us/en/personal-banking/contact-us"),
 ("navyfederal", "Navy Federal Credit Union", "bank", "watch", "navyfederal", None, "https://www.navyfederal.org/contact-us.html"),
 ("usaa", "USAA", "bank", "watch", "usaa", None, "https://www.usaa.com/support/contact/"),
 ("ally", "Ally Bank", "bank", "watch", "ally", None, "https://www.ally.com/help/"),
 ("regions", "Regions Bank", "bank", "watch", "regions", None, "https://www.regions.com/help/contact-us"),
 ("citizens", "Citizens Bank", "bank", "watch", "citizens", None, "https://www.citizensbank.com/customer-service/contact-us.aspx"),
 ("fifththird", "Fifth Third Bank", "bank", "watch", "fifththird", None, "https://www.53.com/content/fifth-third/en/customer-service.html"),
 ("schwab", "Charles Schwab", "bank", "watch", "schwab", None, "https://www.schwab.com/contact-us"),
 ("fidelity", "Fidelity", "bank", "watch", "fidelity", None, "https://www.fidelity.com/customer-service/overview"),
 ("vanguard", "Vanguard", "bank", "watch", "vanguard", None, "https://investor.vanguard.com/contact-us"),
 ("robinhood", "Robinhood", "bank", "sp", "https://status.robinhood.com", "https://status.robinhood.com", "https://robinhood.com/us/en/support/"),
 ("visa", "Visa (card network)", "cards", "watch", "visa", None, "https://usa.visa.com/support.html"),
 ("mastercard", "Mastercard (card network)", "cards", "watch", "mastercard", None, "https://www.mastercard.us/en-us/personal/get-support.html"),
 ("amex", "American Express", "cards", "watch", "amex", None, "https://www.americanexpress.com/en-us/customer-service/"),
 ("discover", "Discover", "cards", "watch", "discover", None, "https://www.discover.com/contact-us/"),
 ("marqeta", "Marqeta (card issuing behind many fintech cards)", "cards", "sp", "https://status.marqeta.com", "https://status.marqeta.com", "https://www.marqeta.com/contact"),
 ("paypal", "PayPal (and Braintree)", "pay", "paypal", None, "https://www.paypal-status.com", "https://www.paypal.com/us/cshelp/personal"),
 ("venmo", "Venmo", "pay", "watch", "venmo", None, "https://help.venmo.com/"),
 ("zelle", "Zelle", "pay", "watch", "zelle", None, "https://www.zellepay.com/support"),
 ("applepay", "Apple Pay and Wallet", "pay", "apple", "Apple Pay", "https://www.apple.com/support/systemstatus/", "https://support.apple.com/apple-pay"),
 ("googlepay", "Google Pay and Wallet", "pay", "watch", "googlepay", None, "https://support.google.com/wallet/"),
 ("mercury", "Mercury (business banking)", "pay", "sp", "https://status.mercury.com", "https://status.mercury.com", "https://mercury.com/contact"),
 ("brex", "Brex (business cards)", "pay", "sp", "https://status.brex.com", "https://status.brex.com", "https://www.brex.com/support"),
 # apps, messaging and work
 ("m365", "Microsoft 365 / Outlook / Teams", "apps", "np", "m365", "https://status.cloud.microsoft", "https://support.microsoft.com/contactus"),
 ("workspace", "Google Workspace (Gmail, Meet)", "apps", "np", "workspace", "https://www.google.com/appsstatus/dashboard/", "https://support.google.com/"),
 ("discord", "Discord", "apps", "sp", "https://discordstatus.com", "https://discordstatus.com", "https://support.discord.com/"),
 ("zoom", "Zoom", "apps", "sp", "https://www.zoomstatus.com", "https://www.zoomstatus.com", "https://support.zoom.com/"),
 ("reddit", "Reddit", "apps", "sp", "https://www.redditstatus.com", "https://www.redditstatus.com", "https://support.reddithelp.com/"),
 ("twilio", "Twilio (texts, calls)", "apps", "sp", "https://status.twilio.com", "https://status.twilio.com", "https://help.twilio.com/"),
 ("proton", "Proton (Mail, VPN)", "apps", "sp", "https://status.proton.me", "https://status.proton.me", "https://proton.me/support"),
 ("ring", "Ring", "apps", "sp", "https://status.ring.com", "https://status.ring.com", "https://ring.com/support"),
 ("openai", "OpenAI (ChatGPT)", "apps", "sp", "https://status.openai.com", "https://status.openai.com", "https://help.openai.com/"),
 ("tailscale", "Tailscale (VPN)", "apps", "sp", "https://status.tailscale.com", "https://status.tailscale.com", "https://tailscale.com/contact/support"),
 ("1password", "1Password", "apps", "sp", "https://status.1password.com", "https://status.1password.com", "https://support.1password.com/"),
]
GROUPS = [("bank", "Banks and brokerages"), ("cards", "Card networks"), ("isp", "Internet providers"), ("mobile", "Mobile carriers"), ("sat", "Satellite internet"), ("cloud", "Cloud and web"),
          ("pay", "Payments and money"), ("rails", "Banking rails"), ("apps", "Apps and messaging"), ("gov", "Government and public")]
NP_PAGES = {"aws", "azure", "m365", "gcp", "workspace", "cloudflare", "akamai", "starlink"}
def _page_off(path):   # Nov 24 2026 (Matt): deactivated pages (deactivated.py, e.g. /grid/starlink) get no "full page" link on the cards
    try:
        import deactivated
        return deactivated.is_off(path)
    except Exception:
        return False

def _day_index(t, n0):
    return (n0 - t.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)).days

def _bars(spans, n0=None):
    """spans: [(start, end_or_None, level)] -> DAYS day levels (oldest first) + uptime % (minutes at level>=2)."""
    n = now(); n0 = n0 or n.replace(hour=0, minute=0, second=0, microsecond=0)
    days = [0] * DAYS; badiv = []; win0 = n0 - timedelta(days=DAYS - 1)
    for s, e, lv in spans:
        if not s: continue
        e = e or n
        if e < win0 or e < s: continue
        s2 = max(s, win0)
        if lv >= 2: badiv.append((s2, min(e, n)))
        d = s2
        while d <= e and d <= n:
            k = _day_index(d, n0)
            if 0 <= k < DAYS: days[DAYS - 1 - k] = max(days[DAYS - 1 - k], lv)
            d = (d + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    bad = 0.0; ce = None
    for a, b in sorted(badiv):   # union, so overlapping incidents are not counted twice
        if ce is None or a > ce: bad += (b - a).total_seconds(); ce = b
        elif b > ce: bad += (b - ce).total_seconds(); ce = b
    tot = (n - win0).total_seconds()
    return days, round(100 - 100 * bad / tot, 2) if tot > 0 else None

def _hrs(spans):
    """spans -> 24 hourly worst levels for the last 24 h, oldest first (the tile sparkline)."""
    n = now(); h0 = n.replace(minute=0, second=0, microsecond=0); out = [0] * 24
    for s, e, lv in spans:
        if not s: continue
        e = e or n
        for k in range(24):
            a = h0 - timedelta(hours=23 - k); b = a + timedelta(hours=1)
            if s < b and e >= a: out[k] = max(out[k], lv)
    return out

class _RL(list):
    full = None   # pt1785u: the provider's whole published list (90 days), kept off the payload for the detail pages
def _recent(items, days=7):
    """[(title, start, end, level)] -> newest-first incident list for the last `days` days (the timeline and the verdict)."""
    lim = now() - timedelta(days=days); lim90 = now() - timedelta(days=90); out = []; full = []
    for t, s, e, lv in items:
        if not s or (e or now()) < lim90: continue
        x = dict(t=(t or "")[:160], s=iso(s), e=iso(e) if e else None, lv=lv); full.append(x)
        if (e or now()) >= lim: out.append(x)
    out.sort(key=lambda x: x["s"], reverse=True); full.sort(key=lambda x: x["s"], reverse=True)
    r = _RL(out[:8]); r.full = full[:120]; return r
HIST = {}

IMP = {"none": 1, "minor": 1, "maintenance": 0, "major": 2, "critical": 3}
def sp_one(base):
    s = jget(base + "/api/v2/summary.json", timeout=9)
    ind = (s.get("status") or {}).get("indicator", "none"); desc = (s.get("status") or {}).get("description") or ""
    act = [i for i in s.get("incidents") or [] if i.get("status") not in ("resolved", "postmortem")]
    lvl = {"none": 0, "minor": 1, "major": 2, "critical": 3, "maintenance": 0}.get(ind, 1)
    if act and lvl == 0: lvl = 1
    inc = swr("spi:" + base, 3600, lambda: jget(base + "/api/v2/incidents.json", timeout=9).get("incidents") or [], wait=True) or []
    spans = [(pts(i.get("started_at") or i.get("created_at")), pts(i.get("resolved_at")), IMP.get(i.get("impact") or "minor", 1)) for i in inc]
    days, up = _bars([x for x in spans if x[2] > 0])
    rec = _recent([(i.get("name"), pts(i.get("started_at") or i.get("created_at")), pts(i.get("resolved_at")), IMP.get(i.get("impact") or "minor", 1)) for i in inc if IMP.get(i.get("impact") or "minor", 1) > 0])
    return dict(level=lvl, status=desc or "Status published", incidents=[dict(t=i.get("name", "")[:160], since=i.get("started_at") or i.get("created_at"),
                impact=i.get("impact")) for i in act[:4]], days=days, uptime=up, basis="provider incident reports", h24=_hrs([x for x in spans if x[2] > 0]), recent=rec, recent_ok=True)

def spc_one(feed):
    """Statuspage, only the components that matter here (feed = (base, regex on component names))."""
    base, rx = feed; rx = re.compile(rx)
    s = jget(base + "/api/v2/summary.json", timeout=9)
    comps = [c for c in s.get("components") or [] if rx.search(c.get("name") or "")]
    worst = max([CST.get(c.get("status"), 0) for c in comps] or [0])
    hit = lambda i: any(rx.search(c.get("name") or "") for c in i.get("components") or [])
    act = [i for i in s.get("incidents") or [] if i.get("status") not in ("resolved", "postmortem") and hit(i)]
    lvl = max(worst, 1 if act else 0)
    inc = swr("spi:" + base, 3600, lambda: jget(base + "/api/v2/incidents.json", timeout=9).get("incidents") or [], wait=True) or []
    spans = [(pts(i.get("started_at") or i.get("created_at")), pts(i.get("resolved_at")), IMP.get(i.get("impact") or "minor", 1)) for i in inc if hit(i)]
    days, up = _bars([x for x in spans if x[2] > 0])
    rec = _recent([(i.get("name"), pts(i.get("started_at") or i.get("created_at")), pts(i.get("resolved_at")), IMP.get(i.get("impact") or "minor", 1)) for i in inc if hit(i) and IMP.get(i.get("impact") or "minor", 1) > 0])
    st = {0: "All tracked services operational", 1: "Minor issues reported", 2: "Partial outage reported", 3: "Major outage reported"}[lvl]
    return dict(level=lvl, status=st, incidents=[dict(t=i.get("name", "")[:160], since=i.get("started_at") or i.get("created_at"), impact=i.get("impact")) for i in act[:4]],
                days=days, uptime=up, basis="provider incident reports for the tracked services", h24=_hrs([x for x in spans if x[2] > 0]), recent=rec, recent_ok=True)
CST = {"operational": 0, "under_maintenance": 0, "degraded_performance": 1, "partial_outage": 2, "major_outage": 3}

def link_one(note):
    return dict(level=-1, status=note, incidents=[], days=None, uptime=None, basis="", link_only=True)

def stripe_one(url):
    d = jget(url, timeout=9); big = d.get("largestatus", "up")
    lvl = {"up": 0, "degraded": 2, "down": 3}.get(big, 1)
    bad = [k for k, v in (d.get("statuses") or {}).items() if v != "up"]
    return dict(level=lvl, status=d.get("message") or ("All services are online" if not lvl else "Issues reported"),
                incidents=[dict(t=f"{k}: {(d.get('statuses') or {}).get(k)}") for k in bad[:4]], days=None, uptime=None, basis="")

def np_one(slug):
    import netpages as NPM
    b = NPM.brief(slug); d = NPM.data(slug)
    spans = [(i.get("start"), i.get("end"), 1 if i.get("longrun") else min(3, int(i.get("sev") or 1))) for i in d.get("active") or []]
    spans += [(i.get("start"), i.get("end") or (i["start"] + timedelta(hours=1) if i.get("start") else None), min(3, int(i.get("sev") or 1))) for i in d.get("history") or []]
    days, up = _bars(spans)
    act = d.get("active") or []
    rec = _recent([(i.get("title"), i.get("start"), i.get("end"), 1 if i.get("longrun") else min(3, int(i.get("sev") or 1))) for i in act if not i.get("longrun")] +
                  [(i.get("title"), i.get("start"), i.get("end") or (i["start"] + timedelta(hours=1) if i.get("start") else None), min(3, int(i.get("sev") or 1))) for i in d.get("history") or []])
    return dict(level=b.get("level", -1), status=b.get("status") or "", incidents=[dict(t=(i.get("title") or "")[:160], since=iso(i.get("start"))) for i in act[:4]],
                days=days, uptime=up, basis="provider incident reports", h24=_hrs([x for x in spans if x[2] > 0]), recent=rec, recent_ok=True)

# ---------------------------------------------------------------- IODA
# Nov 24 2026: when Render gets 403 from IODA, use the box relay snapshot (app/data/ioda_relay_data.json, pushed by
# tools/ioda_relay every 10 min, max 2 h old). The ASN list is cut on the box to the ASNs in NETS.
RELAY_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ioda_relay_data.json")
def _relayed(key, fn):
    try: return fn()
    except Exception:
        try:
            with open(RELAY_DATA, encoding="utf-8") as fh: r = json.load(fh)
            if time.time() - (pts(r.get("generated")) or now()).timestamp() < 7200 and isinstance(r.get(key), list): return r[key]
        except Exception: pass
        raise
def ioda_asn_events():
    n = int(time.time()); return _relayed("asn", lambda: jget(f"{IODA}/outages/events?entityType=asn&from={n - DAYS * 86400}&until={n}&limit=30000", timeout=40, cap=20_000_000).get("data") or [])
def ioda_country_events():
    n = int(time.time()); return _relayed("cev", lambda: jget(f"{IODA}/outages/events?entityType=country&from={n - DAYS * 86400}&until={n}&limit=5000", timeout=30).get("data") or [])
def ioda_summary(et, hours=24):
    n = int(time.time()); f = lambda: jget(f"{IODA}/outages/summary?entityType={et}&from={n - hours * 3600}&until={n}&limit=3000", timeout=25).get("data") or []
    return _relayed("reg", f) if et == "region" and hours == 24 else f()

def _ev(e):
    s = datetime.fromtimestamp(int(e["start"]), timezone.utc); d = int(e.get("duration") or 0)
    return s, s + timedelta(seconds=d), d

def asn_one(asns, evs):
    want = {f"asn/{a}" for a in asns}; spans = []; cur = []; n = now()
    for e in evs:
        if e.get("location") not in want or e.get("datasource") not in STRONG: continue
        s, en, d = _ev(e)
        if d > MAX_EVENT_S: continue
        spans.append((s, en, 2))
        if en >= n - timedelta(minutes=75): cur.append(e)
    days, up = _bars(spans)
    if evs is None: return dict(level=-1, status="Measurements unavailable right now", days=None, uptime=None, incidents=[], basis="")
    grp = []   # IODA reports many short events: merge ones less than an hour apart into one timeline entry
    for e in sorted((e for e in evs if e.get("location") in want and e.get("datasource") in STRONG and int(e.get("duration") or 0) <= MAX_EVENT_S), key=lambda e: int(e["start"])):
        s, en, _ = _ev(e); nm = e.get("location_name") or e.get("location")
        if grp and s <= grp[-1][2] + timedelta(hours=1): grp[-1][2] = max(grp[-1][2], en); grp[-1][3].add(nm)
        else: grp.append([None, s, en, {nm}])
    rec = _recent([("Outage signal on " + ", ".join(sorted(g[3])[:2]) + (" (IODA routing and probing data)"), g[1], None if g[2] >= n - timedelta(minutes=75) else g[2], 2) for g in grp])
    lvl = 2 if cur else 0
    last = max((s for s, _, _ in spans), default=None)
    st = (f"Outage signal on {len({e['location'] for e in cur})} of {len(asns)} network{'s' if len(asns) > 1 else ''}" if cur else
          "No outage signal" + (f" · last one {last.strftime('%b %-d')}" if last else " in 30 days"))
    return dict(level=lvl, status=st, incidents=[dict(t=f"{e.get('location_name')}: {'routing (BGP)' if e['datasource'] == 'bgp' else 'active probing'} drop", since=iso(_ev(e)[0])) for e in cur[:3]],
                days=days, uptime=up, basis="IODA measurements", ioda=f"{IODA_UI}/asn/{asns[0]}", h24=_hrs(spans), recent=rec, recent_ok=True)

# ---------------------------------------------------------------- geography
_GEO = {"v": None}
def centroids():
    if _GEO["v"] is None:
        out = {}
        try:
            with open(os.path.join(BASE, "signal_map_static", "world.geojson"), encoding="utf-8") as fh: feats = json.load(fh)["features"]
            for f in feats:
                g = f.get("geometry") or {}; polys = g.get("coordinates") or []
                if g.get("type") == "Polygon": polys = [polys]
                best = max((p[0] for p in polys if p), key=len, default=None)
                if not best: continue
                out[f["properties"]["name"]] = (round(sum(p[0] for p in best) / len(best), 2), round(sum(p[1] for p in best) / len(best), 2))
        except Exception: pass
        _GEO["v"] = out
    return _GEO["v"]
ALIAS = {"United States": "United States of America", "Russian Federation": "Russia", "Iran, Islamic Republic of": "Iran", "Syrian Arab Republic": "Syria",
         "Venezuela, Bolivarian Republic of": "Venezuela", "Korea, Republic of": "South Korea", "Korea, Democratic People's Republic of": "North Korea",
         "Tanzania, United Republic of": "Tanzania", "Bolivia, Plurinational State of": "Bolivia", "Lao People's Democratic Republic": "Laos",
         "Viet Nam": "Vietnam", "Lao Peoples Democratic Republic": "Laos", "Moldova, Republic of": "Moldova", "Congo, The Democratic Republic of the": "Dem. Rep. Congo", "Democratic Republic of the Congo": "Dem. Rep. Congo",
         "Congo": "Congo", "Côte d'Ivoire": "Côte d'Ivoire", "Ivory Coast": "Côte d'Ivoire", "Cote D Ivoire": "Côte d'Ivoire", "Cote d'Ivoire": "Côte d'Ivoire", "Central African Republic": "Central African Rep.", "South Sudan": "S. Sudan",
         "Bosnia and Herzegovina": "Bosnia and Herz.", "Dominican Republic": "Dominican Rep.", "Czechia": "Czechia", "Czech Republic": "Czechia",
         "Equatorial Guinea": "Eq. Guinea", "Western Sahara": "W. Sahara", "Solomon Islands": "Solomon Is.", "Falkland Islands": "Falkland Is.", "Eswatini": "eSwatini",
         "Swaziland": "eSwatini", "North Macedonia": "Macedonia", "Palestine, State of": "Palestine", "Taiwan, Province of China": "Taiwan", "Brunei Darussalam": "Brunei",
         "Myanmar": "Myanmar", "Timor-Leste": "Timor-Leste", "United Kingdom": "United Kingdom", "Libyan Arab Jamahiriya": "Libya", "Libya": "Libya"}

SMALL = {"SG": (103.82, 1.35), "NF": (167.95, -29.03), "HK": (114.17, 22.32), "MO": (113.55, 22.2), "BH": (50.56, 26.07), "MT": (14.4, 35.9), "MU": (57.55, -20.25),
         "MV": (73.5, 4.2), "BB": (-59.55, 13.17), "AG": (-61.8, 17.07), "GU": (144.79, 13.44), "VI": (-64.9, 18.34), "AS": (-170.7, -14.3), "BM": (-64.75, 32.3),
         "KY": (-81.25, 19.31), "AW": (-69.97, 12.52), "CW": (-68.99, 12.17), "LC": (-60.98, 13.9), "GD": (-61.68, 12.12), "DM": (-61.36, 15.42), "KN": (-62.73, 17.3),
         "VC": (-61.2, 13.25), "TO": (-175.2, -21.18), "WS": (-172.1, -13.76), "SC": (55.45, -4.68), "KM": (43.33, -11.7), "ST": (6.6, 0.25), "CV": (-23.6, 15.1)}
def outages():
    """Countries and regions with an IODA outage signal: current (ended within 75 min or still open) or in the last 24 h."""
    n = now(); cen = centroids(); ce = swr("ioda:cev", 900, ioda_country_events) or []
    by = {}; daily = [0] * DAYS; n0 = n.replace(hour=0, minute=0, second=0, microsecond=0)
    for e in ce:
        if e.get("datasource") not in STRONG | {"merit-nt", "gtr", "gtr-norm"}: continue
        s, en, d = _ev(e)
        if d > MAX_EVENT_S: continue
        k = _day_index(s, n0)
        if 0 <= k < DAYS: daily[DAYS - 1 - k] += 1
        cc = (e.get("location") or "").split("/")[-1]; nm = e.get("location_name") or cc
        o = by.setdefault(cc, dict(cc=cc, name=nm, cur=False, h24=0, ds=set(), score=0, last=None))
        if en >= n - timedelta(hours=24):
            o["h24"] += 1; o["ds"].add(e["datasource"]); o["score"] = max(o["score"], float(e.get("score") or 0))
            if en >= n - timedelta(minutes=75) and e["datasource"] in STRONG: o["cur"] = True
            o["last"] = max(o["last"] or s, s)
    countries = []
    for o in by.values():
        if not o["h24"]: continue
        geo = ALIAS.get(o["name"], o["name"]); c = cen.get(geo) or SMALL.get(o["cc"])
        major = o["cur"] and len(o["ds"] & STRONG) >= 2
        countries.append(dict(cc=o["cc"], name=o["name"], geo=geo, lon=c[0] if c else None, lat=c[1] if c else None, cur=o["cur"], major=major,
                              signals=sorted(o["ds"]), last=iso(o["last"]), ioda=f"{IODA_UI}/country/{o['cc']}"))
    countries.sort(key=lambda x: (not x["major"], not x["cur"], x["name"]))
    regions = []
    try:
        import gridpage as GP
        stp = {}
        try:
            import netstarlink as SL; stp = {v: k for k, v in SL.US_STATES.items()}
        except Exception: pass
        for r in swr("ioda:reg", 900, lambda: ioda_summary("region")) or []:
            ent = r.get("entity") or {}; at = ent.get("attrs") or {}
            if at.get("country_code") != "US": continue
            st = stp.get(ent.get("name")); p = GP.ST_PT.get(st) if st else None
            if not p: continue
            regions.append(dict(name=ent.get("name"), st=st, lon=p[0], lat=p[1], events=r.get("event_cnt"), ioda=f"{IODA_UI}/region/{ent.get('code')}"))
    except Exception: pass
    return dict(countries=countries, us_regions=regions, daily=daily)

def power():
    try:
        import gridpage as GP
        d = GP.data()
        return dict(generated=d.get("generated"), states=[dict(st=s.get("st"), name=s.get("name"), outages=s.get("outages") or 0, lon=s.get("lon"), lat=s.get("lat"),
                    top=[dict(name=t.get("name"), outages=t.get("outages"), web=t.get("web")) for t in (s.get("top") or [])[:3]]) for s in d.get("states") or [] if s.get("lon") is not None])
    except Exception as ex:
        return dict(error=type(ex).__name__, states=[])

# Public cloud regions (provider-published region names and their metro areas)
CLOUD_PTS = [
 ("aws", "US East (N. Virginia)", -77.5, 39.0), ("aws", "US East (Ohio)", -82.9, 40.0), ("aws", "US West (Oregon)", -119.7, 45.6), ("aws", "US West (N. California)", -121.9, 37.4),
 ("aws", "Canada (Central)", -73.6, 45.5), ("aws", "South America (São Paulo)", -46.6, -23.5), ("aws", "Europe (Ireland)", -6.3, 53.3), ("aws", "Europe (Frankfurt)", 8.7, 50.1),
 ("aws", "Europe (London)", -0.1, 51.5), ("aws", "Europe (Stockholm)", 18.1, 59.3), ("aws", "Asia Pacific (Tokyo)", 139.7, 35.7), ("aws", "Asia Pacific (Singapore)", 103.8, 1.35),
 ("aws", "Asia Pacific (Sydney)", 151.2, -33.9), ("aws", "Asia Pacific (Mumbai)", 72.9, 19.1), ("aws", "Middle East (Bahrain)", 50.6, 26.1), ("aws", "Africa (Cape Town)", 18.4, -33.9),
 ("azure", "East US (Virginia)", -78.4, 37.4), ("azure", "Central US (Iowa)", -93.6, 41.6), ("azure", "South Central US (Texas)", -98.5, 29.4), ("azure", "West US 2 (Washington)", -119.9, 47.2),
 ("azure", "North Europe (Ireland)", -6.25, 53.35), ("azure", "West Europe (Netherlands)", 4.9, 52.4), ("azure", "UK South (London)", -0.12, 51.5), ("azure", "Southeast Asia (Singapore)", 103.85, 1.28),
 ("azure", "Japan East (Tokyo)", 139.77, 35.68), ("azure", "Australia East (NSW)", 151.2, -33.86), ("azure", "Brazil South (São Paulo)", -46.63, -23.55), ("azure", "Central India (Pune)", 73.9, 18.6),
 ("gcp", "us-east4 (N. Virginia)", -77.4, 39.1), ("gcp", "us-central1 (Iowa)", -95.9, 41.3), ("gcp", "us-west1 (Oregon)", -121.2, 45.6), ("gcp", "us-east1 (South Carolina)", -80.0, 33.2),
 ("gcp", "europe-west1 (Belgium)", 3.8, 50.5), ("gcp", "europe-west3 (Frankfurt)", 8.68, 50.11), ("gcp", "asia-northeast1 (Tokyo)", 139.69, 35.69), ("gcp", "asia-southeast1 (Singapore)", 103.7, 1.3),
 ("gcp", "australia-southeast1 (Sydney)", 151.21, -33.87), ("gcp", "southamerica-east1 (São Paulo)", -46.64, -23.55), ("gcp", "asia-south1 (Mumbai)", 72.88, 19.08),
]

def build():
    # pt1793 (5): the IODA download (~17 s), the outage summaries (~18 s) and the provider feeds (~14 s) run side by side, not one after another
    pre = ThreadPoolExecutor(3, thread_name_prefix="nm-pre")
    f_asn = pre.submit(swr, "ioda:asn", 1800, ioda_asn_events, True); f_out = pre.submit(outages); f_pw = pre.submit(power); pre.shutdown(wait=False)
    class _Lazy:
        v = None
        def get(self):
            if self.v is None:
                try: self.v = f_asn.result(timeout=60) or []
                except Exception: self.v = []
            return self.v
    asn = _Lazy()
    def one(n):
        nid, name, grp, kind, feed, page, support = n
        try:
            if kind == "sp": r = sp_one(feed)
            elif kind == "np": r = np_one(feed)
            elif kind == "stripe": r = stripe_one(feed)
            elif kind == "spc": r = spc_one(feed)
            elif kind == "link": r = link_one(feed)
            elif kind == "watch":
                import netwatch; r = netwatch.watch_one(feed, swr)
            elif kind == "paypal":
                import netwatch; r = swr("pp", 300, lambda: netwatch.paypal_one(feed, _bars, _hrs, _recent), wait=True)
                r = dict(r)
            elif kind == "apple":
                import netwatch; r = dict(swr("apple:" + feed, 300, lambda: netwatch.apple_one(feed, _bars, _hrs, _recent), wait=True))
            else: r = asn_one(feed, asn.get())
        except Exception:
            r = dict(level=-1, status="Status feed unreachable right now", incidents=[], days=None, uptime=None, basis="")
        r.update(id=nid, name=name, group=grp, kind=kind, status_url=page, support=support, page=f"/grid/{nid}" if nid in NP_PAGES and not _page_off(f"/grid/{nid}") else None,
                 detail=f"/grid/status/{nid}")
        return r
    with ThreadPoolExecutor(12) as ex:
        nets = list(ex.map(one, NETS))
    tl = []
    try:   # pt1758u board: hourly history, the incident timeline and "Down for me" reports live in netboard.py
        import netboard as NB
        rp = NB.reports()
        for n in nets:   # feedless services (banks, card networks): weigh our own Down for me reports in with the news and the sign-in check
            if not n.get("watch"): continue
            r = rp.get(n["id"]) or {}; h1 = int(r.get("h1") or 0); lv = n.get("level", -1)
            if r.get("surge"):
                n["level"] = 3 if lv >= 2 else 2
                n["status"] = f"{h1} people reported problems on this page in the last hour" + ("; " + n["status"][0].lower() + n["status"][1:] if lv >= 2 else "")
            elif h1 >= 2 and lv < 1:
                n["level"] = 1; n["status"] = f"{h1} people reported problems on this page in the last hour (below our spike threshold)"
        NB.record(nets); hist = NB.hours({n["id"] for n in nets})
        for n in nets:
            h = list(n.get("h24") or [-1] * 24); st = hist.get(n["id"])
            if st: h = [max(a, b) for a, b in zip(h, st)]
            if n["level"] >= 0: h[-1] = max(h[-1], n["level"])
            n["h24"] = h if n.get("level", -1) >= 0 or st else None
        NB.record_levels({"web:" + n["id"]: n["web_lv"] for n in nets if n.get("watch") and n.get("web_lv", -1) >= 0})   # sign-in check history, per hour
        wh = NB.hours({"web:" + n["id"] for n in nets if n.get("watch")})
        for n in nets:
            if n.get("watch"): n["web24"] = wh.get("web:" + n["id"]); n.pop("web_lv", None)
        tl = NB.timeline(72, 50)
    except Exception: pass
    for n in nets:
        full = getattr(n.get("recent"), "full", None)
        if full is not None: HIST[n["id"]] = full
        n["recent"] = list(n.get("recent") or [])[:3]; n.pop("recent_ok", None)
    lvl = {n["id"]: n["level"] for n in nets}
    out = f_out.result(); pw = f_pw.result()
    cloud = [dict(p=p, name=nm, lon=lo, lat=la, level=lvl.get(p, -1)) for p, nm, lo, la in CLOUD_PTS]
    issues = [n for n in nets if n["level"] >= 2]; tracked = [n for n in nets if not n.get("link_only")]
    return dict(generated=iso(now()), groups=[dict(id=g, name=t) for g, t in GROUPS], nets=nets, cloud=cloud, outages=out, power=pw, timeline=tl,
                summary=dict(networks=len(tracked), ok=sum(1 for n in tracked if n["level"] in (0, 1)), issues=len(issues), unknown=sum(1 for n in tracked if n["level"] < 0), no_signal=sum(1 for n in tracked if n.get("watch") and n["level"] < 0),
                             countries_now=sum(1 for c in out["countries"] if c["cur"]), countries_24h=len(out["countries"]),
                             power_customers=sum(s["outages"] for s in (pw.get("states") or []))),
                sources=SOURCES, ttl_s=300)

SOURCES = [
 dict(name="IODA, Georgia Tech Internet Intelligence Lab (country, region and network outage signals)", url="https://ioda.inetintel.cc.gatech.edu/"),
 dict(name="Official provider status pages (Atlassian Statuspage public JSON, Stripe status, AWS Health, Azure, Google Cloud, Microsoft 365)", url="https://www.atlassian.com/software/statuspage"),
 dict(name="PeeringDB facility records (data centers and colocation sites)", url="https://www.peeringdb.com/"),
 dict(name="DOE / ORNL ODIN utility outage reports (via The Grid page)", url="https://ornl.opendatasoft.com/explore/dataset/odin-real-time-outages-county/"),
 dict(name="Map tiles: OpenFreeMap, OpenMapTiles, OpenStreetMap contributors", url="https://openfreemap.org/"),
]

def _build_and_keep():
    d = build()
    try:   # pt1793 (5): keep the last good snapshot in votes.db, so a fresh deploy (votes.db is handed over) serves it at once while it rebuilds
        import netboard as NB; NB.save_snapshot("netmap:data", json.dumps(d, separators=(",", ":")))
    except Exception: pass
    return d
def data():
    if "data" not in _C:
        try:
            import netboard as NB; snap = NB.load_snapshot("netmap:data")
            if snap and "data" not in _C: _C["data"] = (0.0, json.loads(snap))   # stale on purpose: served now, rebuilt in the background (single flight)
        except Exception: pass
    return swr("data", 300, _build_and_keep)

# ---------------------------------------------------------------- data centers (PeeringDB, daily, disk cache)
def _dc_path():
    d = os.environ.get("BN_STATE_DIR") or "/tmp"; os.makedirs(d, exist_ok=True); return os.path.join(d, "bn_peeringdb_fac.json")
_DCB = {"until": 0.0}
def _dc_fallback(p):
    try:
        with open(p, "rb") as fh: return fh.read()
    except OSError:
        with open(os.path.join(STATIC, "peeringdb_fac.json"), "rb") as fh: return fh.read()   # bundled snapshot (PeeringDB, Nov 23 2026, 5,304 sites)
def _dc_build():
    p = _dc_path()
    try:
        if time.time() - os.path.getmtime(p) < 86400:
            with open(p, "rb") as fh: return fh.read()
    except OSError: pass
    if time.time() < _DCB["until"]: return _dc_fallback(p)
    try:
        d = jget("https://www.peeringdb.com/api/fac?fields=id,name,city,country,latitude,longitude,org_name,net_count,ix_count,website", timeout=60, cap=20_000_000)["data"]
        if len(d) < 1000: raise RuntimeError("short PeeringDB answer")
    except Exception:
        _DCB["until"] = time.time() + 3600   # PeeringDB throttles anonymous readers: back off an hour, serve the last copy or the bundled snapshot
        return _dc_fallback(p)
    rows = [[round(x["longitude"], 4), round(x["latitude"], 4), x.get("name") or "", x.get("city") or "", x.get("country") or "", x.get("org_name") or "",
             int(x.get("net_count") or 0), int(x.get("ix_count") or 0), x.get("id")] for x in d if x.get("latitude") is not None and x.get("longitude") is not None]
    b = json.dumps({"generated": iso(now()), "cols": ["lon", "lat", "name", "city", "cc", "org", "nets", "ixs", "id"], "rows": rows,
                    "source": "PeeringDB", "source_url": "https://www.peeringdb.com/"}, separators=(",", ":")).encode()
    tmp = p + ".tmp"
    with open(tmp, "wb") as fh: fh.write(b)
    os.replace(tmp, p); return b
def dc(): return swr("dc", 6 * 3600, _dc_build)

# ---------------------------------------------------------------- page
# Nov 24 2026 (Matt pt1795u): The Grid and Network Status merged into this page (now "The Grid"); its loader is the old /grid
# "Energizing the grid" animation (current running down three feeder lines into a 3x3 grid of nodes). Progress follows net.js prog().
LOADER = ('<div class="gx-ld" id="nx_ld" role="status" aria-label="Loading The Grid">'
  '<svg class="gx-ldsvg" viewBox="0 0 320 200" aria-hidden="true" focusable="false">'
  '<g class="gx-lines">'
  '<path d="M10 40 C 70 40, 90 70, 130 70 L 160 70"/><path d="M10 160 C 70 160, 90 130, 130 130 L 160 130"/>'
  '<path d="M10 100 L 160 100"/>'
  '<path d="M160 70 L 220 70 L 280 70 M160 100 L 220 100 L 280 100 M160 130 L 220 130 L 280 130 M160 70 L 160 130 M220 70 L 220 130 M280 70 L 280 130"/>'
  '</g>'
  '<g class="gx-flow"><path d="M10 40 C 70 40, 90 70, 130 70 L 160 70"/><path d="M10 160 C 70 160, 90 130, 130 130 L 160 130"/><path d="M10 100 L 160 100"/></g>'
  '<g class="gx-tow"><path d="M10 26 v28 M4 34 h12 M6 30 l4 -4 l4 4"/><path d="M10 86 v28 M4 94 h12 M6 90 l4 -4 l4 4"/><path d="M10 146 v28 M4 154 h12 M6 150 l4 -4 l4 4"/></g>'
  '<g class="gx-nodes">' + "".join(f'<circle cx="{x}" cy="{y}" r="5" style="--d:{i * 0.09:.2f}s"/>' for i, (x, y) in enumerate(
      [(160, 70), (160, 100), (160, 130), (220, 70), (220, 100), (220, 130), (280, 70), (280, 100), (280, 130)])) + '</g>'
  '</svg>'
  '<p class="gx-ldk"><span>Energizing the grid</span><b id="nx_ldn">00%</b></p>'
  '<ol class="gx-lds" aria-hidden="true"><li data-s="map">Map</li><li data-s="nets">Networks</li><li data-s="out">Outages</li><li data-s="rep">Reports</li></ol>'
  '<p class="gx-ldmsg" id="nx_ldmsg" hidden></p></div>')

# The old /grid page's "More about the grid" sheet (gridpage.py), merged in: same sections, filled by gridlayer.js from /api/gridpage/*.
def _gsec(sid, h, sub):
    return (f'<details class="gx-sec" id="{sid}"><summary><span><b>{E(h)}</b><small>{E(sub)}</small></span><i aria-hidden="true"></i></summary>'
            f'<div class="gx-body" data-sec="{sid}"><p class="gx-empty">Loading…</p></div></details>')
GRID_MORE = ('<section class="gx-more" id="gx_more" aria-label="More about the grid" hidden>'
  '<div class="gx-grab" aria-hidden="true"></div>'
  '<div class="gx-mh"><div><p class="gx-k">The Grid</p><h2>More about the grid</h2></div><button type="button" class="gx-x" id="gx_more_x" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>'
  '<div class="gx-scroll" id="gx_scroll">'
  '<div class="gx-reg" id="gx_reg" role="group" aria-label="Show a region on the map"><span>Show on map</span><button type="button" data-r="us">U.S.</button><button type="button" data-r="eu">Europe</button><button type="button" data-r="apac">Asia-Pacific</button><button type="button" data-r="world">World</button></div>'
  '<div class="gx-kpis" id="gx_kpis"></div>'
  + _gsec("gx-regions", "Grid operators", "Status, demand and the last 36 hours for each operator region")
  + _gsec("gx-world", "Worldwide", "Operators outside the U.S. and grid or blackout alerts on the Wire")
  + _gsec("gx-outages", "Outages by state", "Utility outage counts reported to DOE / ORNL ODIN")
  + _gsec("gx-weather", "Weather threats to power", "Ranked weather alerts with grid and infrastructure checks")
  + _gsec("gx-threats", "Grid threats", "Physical, cyber and reliability threats to U.S. power")
  + _gsec("gx-space", "Space weather", "NOAA geomagnetic storm scale and 3-day outlook")
  + _gsec("gx-local", "Your state", "Utilities, outage maps, alerts and open shelters")
  + _gsec("gx-sources", "Sources and data age", "Where every number on this page comes from")
  + '</div></section><aside class="gx-card" id="gx_card" hidden aria-live="polite"></aside>')

BOARD = ('<section class="nb" id="nb" aria-label="Network status board"><div class="nb-in">'
  '<header class="nb-hero"><p class="nb-k">Is it down?</p>'
  '<form class="nb-q" id="nb_qf" role="search" autocomplete="off"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>'
  '<input id="nb_q" type="search" enterkeyhint="search" placeholder="AWS, Verizon, Gmail, ChatGPT, Venmo" aria-label="Is it down? Type a service name" spellcheck="false">'
  '<button type="submit">Check</button></form><ul class="nb-sug" id="nb_sug" hidden></ul>'
  '<div class="nb-v" id="nb_v" aria-live="polite" hidden></div></header>'
  '<div class="nb-pulse" id="nb_pulse"><i></i><div><p class="nb-pt">Checking services</p><p class="nb-ps">Official status pages, IODA and reports</p></div></div>'
  '<section class="nb-now" id="nb_now" hidden aria-label="Problems now"></section>'
  '<div id="nb_groups"></div>'
  '<section class="nb-sec nb-grid" aria-label="The power grid"><div class="nb-gh"><h2>The power grid</h2><span>Operators, outages, weather</span></div>'
  '<p class="nb-note" id="nb_grid">Grid operators, outages by state, weather threats to power and space weather.</p>'
  '<button type="button" class="nb-gbtn" data-more="gx-regions">More about the grid</button></section>'
  '<section class="nb-sec" aria-label="Incident timeline"><div class="nb-gh"><h2>Incident timeline</h2><span>Last 3 days</span></div><div id="nb_tl"><p class="nb-empty">Loading</p></div></section>'
  '<section class="nb-sec" aria-label="Chain reactions"><div class="nb-gh"><h2>How outages spread</h2><span>Documented dependencies</span></div>'
  '<p class="nb-note">When one of these fails, the services under it usually fail too. Each link is from a past outage, and anything we infer is marked likely.</p><div class="nb-chg" id="nb_chains"></div></section>'
  '<footer class="nb-foot"><p>Verdicts combine official status pages, IODA internet measurements (Georgia Tech) and reports from people on this page. '
  '"Down for me" stores the service, the time and an optional ZIP, nothing else. Open <b>Map</b> for grid operators, data centers, power and internet outages, or <b>Sky</b> for satellites.</p>'
  '<p><a href="/grid/providers">Cloud provider pages</a> · <a href="https://ioda.inetintel.cc.gatech.edu/" target="_blank" rel="noopener">IODA</a> · <a href="https://www.peeringdb.com/" target="_blank" rel="noopener">PeeringDB</a></p></footer>'
  '</div></section>')

SKY_CHIPS = [("starlink", "Starlink", "#E8ECF5"), ("gps", "GPS", "#4FC3F7"), ("glonass", "GLONASS", "#B39DFF"), ("galileo", "Galileo", "#5CE1B6"),
             ("beidou", "BeiDou", "#FF8FB1"), ("iridium", "Iridium", "#9DB4FF"), ("oneweb", "OneWeb", "#FFA270"), ("goes", "GOES", "#FF7AE0")]
# Nov 24 2026 (Matt): one "Power grid" chip (outages + operators + 230 kV+ lines); chips with no map items (Mobile, Satellite, Payments, Apps) live on Status only
CHIPS = [("internet", "Internet"), ("grid", "Power grid"), ("hydro", "Hydro dams"), ("cloud", "Cloud"), ("sea", "Undersea cables"), ("towers", "Cell towers"), ("dc", "Data centers")]

def page(qs=None):
    try:
        import sitenav, sitenav_ui
        top = sitenav.header_html("net"); theme = sitenav_ui.THEME_SCRIPT
    except Exception:
        top = '<header class="bn-top"><div class="bn-tbar"><a class="bn-logo" href="/"><span class="bnt-wm">blackout.network</span></a></div></header>'; theme = ""
    try:
        import signal_map
        mlv = signal_map._v("maplibre-gl.js"); mlc = signal_map._v("maplibre-gl.css")
    except Exception:
        mlv = mlc = "0"
    title = "The Grid: live status of power, internet, mobile, cloud and apps | BLACKOUT.NETWORK"
    desc = ("The Grid: live status of the power grid and the networks that run on it. Grid operators colored by status, outages by state, weather threats, "
            "plus plain-English verdicts for internet providers, mobile carriers, AWS, Cloudflare, payments, apps and government services, an incident log and a satellite globe.")
    skychips = "".join(f'<button type="button" data-g="{g}" aria-pressed="true"><i style="background:{c};border-color:{c}"></i>{E(t)}</button>' for g, t, c in SKY_CHIPS)
    chips = "".join(f'<button type="button" data-k="{k}" aria-pressed="true"><i></i>{E(t)}</button>' for k, t in CHIPS)
    return f'''<!doctype html><html lang="en" class="nx-root"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{theme}
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="https://blackout.network/grid">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="https://blackout.network/grid"><meta property="og:type" content="website"><meta property="og:image" content="https://blackout.network/og/grid.png">
<meta name="theme-color" content="#05060a">
<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin>
<link rel="preload" href="/api/netmap/data" as="fetch" crossorigin>
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/maplibre-gl.css?v={mlc}"><link rel="stylesheet" href="/api/netmap/net.css?v={_v("net.css")}">
<script src="/sitenav.js" defer></script>
<link rel="stylesheet" href="/api/netmap/board.css?v={_v("board.css")}"><link rel="stylesheet" href="/api/netmap/gridlayer.css?v={_v("gridlayer.css")}">
</head><body class="nx">
<script>(function(){{if(location.hash==="#status"){{document.body.classList.add("nx-board");}}}})()</script>
<a class="skip" href="#nb_q">Skip to the outage search</a>
<div class="nx-head">{top}</div>
<script>(function(){{var m=document.getElementById("bn-menu");if(m&&m.parentNode!==document.body)document.body.appendChild(m)}})()</script>
<main id="nx_main" data-bnt-skip>
<h1 class="nx-vh">The Grid: live status of the power grid, internet, mobile, cloud, payments, apps and government services</h1>
<div id="nx_map" class="nx-map" role="region" aria-label="Map of the power grid and network outages. Drag to pan, pinch or scroll to zoom, tap a point for details."></div>
{LOADER}
{BOARD.replace('id="nb"', 'id="nb" data-logos="/api/netmap/logos.svg?v=' + _v("logos.svg") + '"', 1)}
<div class="nx-top"><div class="nx-mode" id="nx_mode" role="group" aria-label="View"><button type="button" data-m="status" aria-pressed="false">Status</button><button type="button" data-m="map" aria-pressed="true">Map</button><button type="button" data-m="sky" aria-pressed="false">Sky</button></div><div class="nx-chip" id="nx_chip"><i></i><span id="nx_sum" aria-live="polite">Checking networks…</span></div></div>
<div class="nx-f" id="nx_f" role="group" aria-label="Show networks">{chips}</div>
<div class="nx-f nx-sf" id="nx_sf" role="group" aria-label="Show constellations" hidden>{skychips}</div>
<aside class="nx-sw" id="nx_sw" hidden aria-live="polite"></aside>
<div class="nx-side"><aside class="nx-sea" id="nx_sea" hidden aria-label="Undersea cables"></aside></div>
<div class="nx-ctl"><button type="button" class="nx-b" id="nx_zin" aria-label="Zoom in"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6v12M6 12h12"/></svg></button>
<button type="button" class="nx-b" id="nx_zout" aria-label="Zoom out"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg></button>
<button type="button" class="nx-b" id="nx_world" aria-label="Show the world"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.8 5.2 3.8 8.5s-1.2 6.1-3.8 8.5c-2.6-2.4-3.8-5.2-3.8-8.5s1.2-6.1 3.8-8.5z"/></svg></button>
<button type="button" class="nx-b" id="nx_home" aria-label="Show the whole U.S."><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button></div>
<div class="nx-leg" id="nx_leg" aria-label="Legend"><ul>
<li><i class="s-ok"></i>Normal</li><li><i class="s-deg"></i>Disruption</li><li><i class="s-out"></i>Major</li><li style="display:none"><i class="s-na" style="background:#7C8190"></i>No data</li><li><i class="s-dc"></i>Data center</li></ul>
<ul class="nx-shapes" id="gx_leg"><li><i class="sh-ring"></i>Grid operator</li><li><i class="sh-dia"></i>Weather or grid alert</li></ul><ul class="nx-lnk" aria-label="Power lines, coloured by their grid operator&#39;s live status"><li><i class="ln" style="background:#2FD67B"></i>Lines normal</li><li><i class="ln" style="background:#F5D547"></i>Strained</li><li><i class="ln" style="background:#FF3B3B"></i>Outage</li><li><i class="ln" style="background:#7C8190"></i>No live feed</li></ul><p class="nx-live" id="gx_live">Live line status: U.S. grid operators</p><ul class="nx-lnk" aria-label="Hydro dams by reservoir level"><li><i style="width:8px;height:8px;border-radius:50%;background:#2FD67B"></i>Dam level OK</li><li><i style="width:8px;height:8px;border-radius:50%;background:#FF7A1A"></i>Low water</li><li><i style="width:8px;height:8px;border-radius:50%;background:#FF3B3B"></i>Near min. pool</li><li><i style="width:8px;height:8px;border-radius:50%;background:rgba(124,129,144,.6)"></i>No level data</li></ul></div>
<button type="button" class="nx-more-btn" id="nx_more_btn" aria-controls="nx_more" aria-expanded="false"><span id="nx_more_lbl">All networks</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 15l6-6 6 6"/></svg></button>
<button type="button" class="gx-more-btn" id="gx_more_btn" aria-controls="gx_more" aria-expanded="false"><span class="gx-ml">More about the grid</span><span class="gx-ms">Grid details</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 15l6-6 6 6"/></svg></button>
<aside class="nx-card" id="nx_card" hidden aria-live="polite"></aside>
{GRID_MORE}
<section class="nx-more" id="nx_more" aria-label="All networks" hidden>
<div class="nx-grab" aria-hidden="true"></div>
<div class="nx-mh"><div><p class="nx-k">The Grid</p><h2>All networks</h2></div><button type="button" class="nx-x" id="nx_more_x" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
<div class="nx-scroll" id="nx_scroll"><div id="nx_list"><p class="nx-empty">Loading…</p></div></div></section>
<noscript><p class="nx-nojs">The network map needs JavaScript. <a href="/grid/providers">Cloud provider pages</a></p></noscript>
</main>
<script src="/api/signal/maplibre-gl.js?v={mlv}" defer></script><script src="/api/netmap/net.js?v={_v("net.js")}" defer></script><script src="/api/netmap/board.js?v={_v("board.js")}" defer></script><script src="/api/netmap/gridlayer.js?v={_v("gridlayer.js")}" defer></script><script>window.BN_SATJS={json.dumps(list(SATJS))};</script>
</body></html>'''

def detail_page(sid):
    """pt1785u: the on-site detail page behind every tile's Expand control (opens at the top, like every site page)."""
    if sid not in {x[0] for x in NETS}: return 404, {"error": "not found"}
    import netboard as NB, netdetail as ND, site_page
    d = data() or {}; n = next((x for x in d.get("nets") or [] if x["id"] == sid), None)
    if n is None:
        x = next(x for x in NETS if x[0] == sid)
        n = dict(id=sid, name=x[1], group=x[2], kind=x[3], level=-1, status="Live status is loading. Try again in a minute.", status_url=x[5], support=x[6], watch=x[3] == "watch")
    body = ND.render(n, NB.service_history(sid, 90), (NB.reports() or {}).get(sid), d.get("generated"), HIST.get(sid) or [])
    nm = ND.short(n["name"])
    title = f"Is {nm} down? Live status, outage history and reports"
    desc = f"{nm} status now, 90-day uptime, incident history and Down for me reports, from " + (n.get("basis") or "official status feeds") + "."
    return 200, site_page.page(title, desc, body, f"/grid/status/{sid}", active="net", og_type="website"), "text/html"

def handle_get(path, qs=None, headers=None):
    p = path.rstrip("/") or "/"
    if p in ("/grid", "/network"): return 200, page(qs or {}), "text/html"
    m = re.fullmatch(r"/grid/status/([a-z0-9]+)", p)
    if m: return detail_page(m.group(1))
    if p == "/api/netmap/data":
        try:
            d = data()
            return (200, d) if d else (503, {"error": "network data is still loading"})
        except Exception as ex: return 503, {"error": "network data unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/dc":
        try:
            b = dc()
            return (200, b, "application/json") if b else (503, {"error": "data centers are still loading"})
        except Exception as ex: return 503, {"error": "data centers unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/sky":
        import netsky
        try:
            lite = str(((qs or {}).get("lite") or [""])[0] if isinstance((qs or {}).get("lite"), list) else (qs or {}).get("lite") or "") == "1"
            return 200, netsky.sky_cached(lite), "application/json"
        except Exception as ex: return 503, {"error": "orbital data unavailable right now", "detail": type(ex).__name__}
    if p == "/api/netmap/board":   # pt1758u: reports, timeline and chain reactions for the status board (light, 20 s cache)
        import netboard as NB
        try:
            try:
                import gridpage as GP; stp = {k: list(v) for k, v in GP.ST_PT.items()}
            except Exception: stp = {}
            return 200, dict(generated=iso(now()), reports=NB.reports(), timeline=NB.timeline(72, 50), deps=NB.DEPS, st_pt=stp)
        except Exception as ex: return 503, {"error": "board data unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/cables":   # pt1812u: per-cable status (green / yellow / red), 10 min cache
        import netcables
        try:
            r = swr("cables", 600, lambda: netcables.api(swr, lambda: ((_C.get("data") or (0, {}))[1] or {}).get("outages")), wait=True)
            if r and not r.get("news_ok") and "cables" in _C and time.time() - _C["cables"][0] > 120: _C["cables"] = (time.time() - 600, r)   # news failed: try again soon (served stale meanwhile)
            return (200, r) if r else (503, {"error": "cable data is still loading"})
        except Exception as ex: return 503, {"error": "cable data unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/inet":   # pt1810u: internet status per U.S. state, territory and country (IODA, 10 min cache)
        import netinet
        try:
            r = swr("inet", 600, lambda: netinet.build(jget), wait=True)
            if r and not all((r.get("feeds") or {}).values()) and "inet" in _C and time.time() - _C["inet"][0] > 120: _C["inet"] = (time.time() - 600, r)   # IODA did not answer: try again soon
            try:
                import netcables; nw = swr("inet:news", 1800, lambda: netinet.news(netcables._rss), wait=False)
            except Exception: nw = None
            r = netinet.serve(r, nw)
            r["ioda"] = ioda_state()
            return (200, r) if r.get("places") else (503, {"error": "internet status is still loading"})
        except Exception as ex: return 503, {"error": "internet status unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/gridfreq":   # pt1815u: live status outside the U.S. from keyless synchronous-area frequency feeds (5 min cache)
        import gridfreq
        try:
            r = swr("gridfreq", 300, lambda: gridfreq.build(jget, STATIC), wait=True)
            return (200, r) if r else (503, {"error": "grid frequency is still loading"})
        except Exception as ex: return 503, {"error": "grid frequency unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/reservoirs":   # pt1815u stage 2: reservoir level vs. minimum power pool (USBR, 30 min cache)
        import reservoirs
        try:
            r = swr("reservoirs", 1800, lambda: reservoirs.build(jget), wait=True)
            return (200, r) if r else (503, {"error": "reservoir levels are still loading"})
        except Exception as ex: return 503, {"error": "reservoir levels unavailable", "detail": type(ex).__name__}
    if p == "/api/netmap/space":
        import netsky
        return 200, netsky.space()
    mt = re.fullmatch(r"/api/netmap/gridtiles/(\d{1,2})/(\d{1,4})/(\d{1,4})\.pbf", p)
    if mt:
        import netinfra
        return netinfra.tile(STATIC, *map(int, mt.groups()))
    if p.startswith("/api/netmap/"):
        n = p[len("/api/netmap/"):]
        if n == "learn.json" or re.fullmatch(r"learn/[a-z0-9_-]+\.(jpg|jpeg|png|webp|txt)", n):
            path = os.path.join(STATIC, n)
            root = os.path.abspath(STATIC) + os.sep
            if not os.path.abspath(path).startswith(root):
                return 404, {"error": "not found"}
            body = None
            if os.path.isfile(path):
                with open(path, "rb") as fh: body = fh.read()
            elif os.path.isfile(path + ".b64"):
                import base64
                with open(path + ".b64", "rb") as fh: body = base64.b64decode(fh.read())
            if body is None:
                return 404, {"error": "not found"}
            ctype = "application/json" if n.endswith(".json") else "text/plain; charset=utf-8" if n.endswith(".txt") else "image/jpeg" if n.endswith((".jpg", ".jpeg")) else "image/png" if n.endswith(".png") else "image/webp"
            return 200, body, ctype
        if n not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    return 404, {"error": "not found"}

# warm both caches in the background when the module loads, so the first visitor after a deploy gets live data at once
def _warm():
    def inet():   # follow-up pt1810u: first visitor after a deploy gets the Internet layer at once (was ~18 s cold)
        import netinet; swr("inet", 600, lambda: netinet.build(jget), wait=True)
    for f in (data, dc):
        try: f()
        except Exception: pass
    time.sleep(90)   # stagger: the Internet layer's IODA calls do not overlap the 30-day ASN download and outage summaries
    try: inet()
    except Exception: pass
if os.environ.get("BN_NETMAP_WARM", "1") != "0":
    threading.Thread(target=_warm, daemon=True, name="nm-warm").start()
