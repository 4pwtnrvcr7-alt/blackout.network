"""Supplemental world-news feeds for the homepage Civil unrest and UK and London widgets (site-side only).

The Wire (scanner) carries few protest/UK-security stories, so these two widgets also read keyless public feeds:
GDELT DOC 2.0 (artlist), Google News RSS search (outlet-attributed), and direct RSS from public broadcasters/major papers.
Everything is cached in memory + a JSON file and refreshed by one background thread about every 30 minutes; a request never
waits on the network, and a dead or rate-limited source is skipped (GDELT backs off for an hour on a 429).
Only allowlisted mainstream, wire and public-broadcaster domains count. Items are filtered (physical unrest / UK security),
headline-cleaned and grouped into events by title similarity; an event's outlet count is the number of distinct domains.
"""
import os, re, json, time, threading, html, urllib.request, urllib.parse
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
REFRESH = 30 * 60
UA = "Mozilla/5.0 (compatible; BlackoutNetwork/1.0; +https://blackout.network)"

# ------------------------------------------------------------------ reputable outlets (suffix match on the domain)
OUTLETS = {
    "apnews.com": "AP", "reuters.com": "Reuters", "afp.com": "AFP", "bbc.co.uk": "BBC", "bbc.com": "BBC", "theguardian.com": "The Guardian",
    "nytimes.com": "New York Times", "washingtonpost.com": "Washington Post", "wsj.com": "WSJ", "cnn.com": "CNN", "cbsnews.com": "CBS News",
    "nbcnews.com": "NBC News", "abcnews.go.com": "ABC News", "abcnews.com": "ABC News", "npr.org": "NPR", "pbs.org": "PBS", "usatoday.com": "USA Today",
    "latimes.com": "LA Times", "chicagotribune.com": "Chicago Tribune", "bostonglobe.com": "Boston Globe", "inquirer.com": "Philadelphia Inquirer",
    "sfchronicle.com": "SF Chronicle", "seattletimes.com": "Seattle Times", "startribune.com": "Star Tribune", "miamiherald.com": "Miami Herald",
    "politico.com": "Politico", "politico.eu": "Politico Europe", "axios.com": "Axios", "thehill.com": "The Hill", "bloomberg.com": "Bloomberg",
    "ft.com": "Financial Times", "economist.com": "The Economist", "cnbc.com": "CNBC", "foxnews.com": "Fox News", "newsweek.com": "Newsweek",
    "time.com": "TIME", "aljazeera.com": "Al Jazeera", "dw.com": "DW", "france24.com": "France 24", "euronews.com": "Euronews", "rfi.fr": "RFI",
    "lemonde.fr": "Le Monde", "news.sky.com": "Sky News", "skynews.com": "Sky News", "independent.co.uk": "The Independent",
    "telegraph.co.uk": "The Telegraph", "thetimes.co.uk": "The Times", "thetimes.com": "The Times", "standard.co.uk": "Evening Standard",
    "itv.com": "ITV News", "channel4.com": "Channel 4 News", "inews.co.uk": "i News", "scotsman.com": "The Scotsman", "heraldscotland.com": "The Herald",
    "irishtimes.com": "Irish Times", "rte.ie": "RTE", "cbc.ca": "CBC", "globalnews.ca": "Global News", "theglobeandmail.com": "Globe and Mail",
    "abc.net.au": "ABC Australia", "smh.com.au": "Sydney Morning Herald", "scmp.com": "South China Morning Post", "straitstimes.com": "Straits Times",
    "japantimes.co.jp": "Japan Times", "nhk.or.jp": "NHK", "kyodonews.net": "Kyodo", "thehindu.com": "The Hindu", "hindustantimes.com": "Hindustan Times",
    "indianexpress.com": "Indian Express", "ndtv.com": "NDTV", "timesofindia.indiatimes.com": "Times of India", "dawn.com": "Dawn",
    "voanews.com": "VOA", "rferl.org": "RFE/RL", "timesofisrael.com": "Times of Israel", "haaretz.com": "Haaretz", "kyivindependent.com": "Kyiv Independent",
    "lefigaro.fr": "Le Figaro", "spiegel.de": "Der Spiegel", "elpais.com": "El Pais", "batimes.com.ar": "Buenos Aires Times", "mercopress.com": "MercoPress",
    "africanews.com": "Africanews", "news24.com": "News24", "nation.africa": "Nation Africa", "premiumtimesng.com": "Premium Times",
    "thenationalnews.com": "The National", "arabnews.com": "Arab News", "yonhapnews.co.kr": "Yonhap", "koreaherald.com": "Korea Herald",
    "taipeitimes.com": "Taipei Times", "rappler.com": "Rappler", "bangkokpost.com": "Bangkok Post", "dailystar.net": "Daily Star",
}
def outlet(domain):
    d = (domain or "").lower().strip().lstrip(".")
    d = re.sub(r"^(www|m|amp|edition|uk|us|eu|news|feeds|rss)\.", "", d) if d.count(".") > 1 and not d.startswith("news.sky") else d
    for k, v in OUTLETS.items():
        if d == k or d.endswith("." + k): return k, v
    return None, None

# ------------------------------------------------------------------ headline clean-up
_SUFFIX = re.compile(r"\s+[-\u2013\u2014|]\s+(?P<o>[A-Z0-9][^-\u2013\u2014|]{1,40})$")
_TAILS = [r"\s*[:\-\u2013\u2014|]?\s*\d+\s+outlets?\s+compared\s*$", r"\s*\(?\b(video|photos?|watch|live updates?|live)\)?\s*$",
          r"\s+via\s+@\w+.*$", r"\s+https?://\S+.*$", r"\s+#\w+(\s+#\w+)*\s*$", r"\s*\|\s*[^|]{2,40}$"]
_SENT = re.compile(r"(?<=[a-z0-9\)\"'\u2019])[.!?]\s+(?=\S)")
def clean_headline(t, known_outlet=None):
    t = html.unescape(re.sub(r"<[^>]+>", "", t or ""))
    t = re.sub(r"\s+", " ", t).strip().strip('"').strip()
    for _ in range(2):
        m = _SUFFIX.search(t)
        if m and (known_outlet is None or len(m.group("o")) <= 40): t = t[:m.start()].rstrip()
        for p in _TAILS: t = re.sub(p, "", t, flags=re.I).strip()
    # social-media commentary glued on after a separator: "Headline - nice to see ...", "Headline. lol ..."
    t = re.sub(r"\s+[-\u2013\u2014:]\s+(?=[a-z])\S.*$", "", t).strip()
    t = re.sub(r"^[Ww]atch\s+(?=[A-Z])", "", t)
    t = re.sub(r"\s*[:\-\u2013\u2014]\s*(what (?:you need )?to know|live updates?|explained|in pictures|in photos)\s*$", "", t, flags=re.I)
    t = re.sub(r"^(video|watch|in pictures|in photos|live|breaking|update|exclusive)\s*[.:\-\u2013\u2014|]\s*", "", t, flags=re.I).strip()
    for m in _SENT.finditer(t):
        head, rest = t[:m.start()], t[m.end():]
        if re.search(r"\b(st|mr|mrs|ms|dr|gen|lt|sgt|gov|sen|rep|vs|ft|mt|no|jr|sr|col|capt|prof|inc|co|corp|ltd|approx|est|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)$", head, re.I): continue
        if len(head) >= 30 or rest[:1].islower(): t = head
        break
    t = t.rstrip(" .,;:-\u2013\u2014")
    if len(t) > 140:
        cut = t[:140]; t = cut[:cut.rfind(" ")].rstrip(" ,;:-") + "\u2026"
    return t

# ------------------------------------------------------------------ topic matching
_ST = r"(?:s|es|ers|ing|ed)?"
PHYS = re.compile(
    r"\b(riot" + _ST + r"|rioters?|looting|(?:shops?|stores?|businesses|homes) (?:were )?looted|tear[ -]?gas|water cannons?|rubber bullets|stun grenades|barricades?|unrest|civil disorder|"
    r"protesters|demonstrators|counter-?protest\w*|anti-government|uprisings?|insurrection|"
    r"martial law|general strike|national strike|nationwide strike|coup attempt|attempted coup|military coup|"
    r"stormed (?:the )?(?:parliament|capitol|congress|palace)|"
    r"national guard (?:troops|deploy\w*|activated|sent|arrive\w*)|deploy\w* (?:the )?national guard|troops (?:deployed|sent) to)\b", re.I)
PROTEST = re.compile(r"\b(protests?|demonstrations?|rall(?:y|ies)|marche[sd]?|sit-ins?|walkouts?|vigils?)\b", re.I)
PROTEST_CUE = re.compile(r"\b(thousands|hundreds|tens of thousands|crowds?|streets?|police|arrest\w*|clash\w*|erupt\w*|took to|gather\w*|outside|square|"
                         r"capital|block\w*|march\w*|mass|nationwide|across|cities|dozens of|violent|turn\w* violent|banned|draws?|drew|join\w*|"
                         r"against|demand\w*|deploy\w*|braces?|ahead of|human chain|encampment|occup\w*|enter\w*|storm\w*)\b", re.I)
CLASH = re.compile(r"\bclash(?:es|ed)?\b", re.I)
CLASH_CUE = re.compile(r"\b(police|protesters|demonstrators|security forces|troops|soldiers|army|riot|settlers|rioters|mobs?|gangs?|crowds?|erupt\w*|"
                       r"deadly|killed|dead|injured|wounded|arrests?|streets?|violent)\b", re.I)
CURFEW = re.compile(r"\bcurfews?\b", re.I)
CRACK = re.compile(r"\b(crackdowns?|state of (?:emergency|siege))\b", re.I)
CRACK_CUE = re.compile(r"\b(protest\w*|dissent|opposition|demonstrat\w*|unrest|arrest\w*|detain\w*|security forces|troops|army|military|gangs?|violence|curfew)\b", re.I)
COUP = re.compile(r"\bcoups?\b", re.I)
COUP_CUE = re.compile(r"\b(military|soldiers|troops|army|junta|seize\w*|ousted|overthrow\w*|attempt\w*|plot\w*|putsch|mutin\w*|gunfire|president(?:ial)? palace)\b", re.I)
METAPHOR = re.compile(r"\b(constitutional|judicial|legal|soft|silent|slow[- ]motion|boardroom|corporate|media|party|cabinet|whose|so-called|'?coup'?\?|"
                      r"coup or|restoration|tribunal|standoff|coup de gr\w+|coup for)\b.{0,25}|\bcourt (standoff|fight|battle|ruling)\b", re.I)
YOUTH = re.compile(r"\b(minors?|youth|teens?|teenagers?|juveniles?|under-1[0-9]s?|kids|children|students?)\b.{0,30}\bcurfews?\b|\bcurfews?\b.{0,30}\b(minors?|youth|teens?|teenagers?|juveniles?)\b", re.I)
ESCAL = re.compile(r"\b(clash\w*|arrest\w*|riot\w*|violence|violent|shot|shooting|killed|injur\w*|tear gas|looting|unrest)\b", re.I)
NOT_EVENT = re.compile(r"\b(opinion|op-ed|editorial|column|letters?|podcast|quiz|crossword|review:|book review|how the .{0,60} could|explainer|"
                       r"case dismissed|did not breach|calls to ban|suing|to sue|fans|banner|take back the night|sexual violence|watchdog finds|lawsuit|sues|sued|trial|sentenced|verdict|appeal court|athletics|football|soccer|basketball|baseball|rugby|cricket|"
                       r"tennis|boxing match|sailing|regatta|yacht|route du rhum|grand prix|nfl|nba|mlb|nhl|premier league|champions league|match|playoffs?|tournament|video game|movie|film|album|tv show|series finale)\b", re.I)
STRONG = re.compile(r"\b(thousands|tens of thousands|hundreds of thousands|hundreds|mass|nationwide|across (?:the )?(?:country|cities|france|europe)|"
                    r"storm\w*|block\w* (?:roads?|streets?|highways?)|clash\w*|tear gas|water cannons?|arrest\w*|detain\w*|killed|injur\w*|violent|violence|"
                    r"riot\w*|unrest|curfews?|crackdowns?|martial law|coup|general strike|national guard|troops|police (?:fire|fired|charge|charged|use|used|clear\w*|dismantle\w*|disperse\w*)|"
                    r"set fires?|fires|firecrackers|looting|barricades?|encampment|occup\w*|counter-?protest\w*|break into|broke into|"
                    r"anti-government|insurrection|uprising|state of emergency)\b", re.I)
US_PHYS = re.compile(r"\b(gather\w*|outside|human chain|march\w*|rall(?:y|ies)|block\w*|surround\w*|confront\w*|ICE|federal agents|immigration agents)\b")
def is_strong(t): return bool(STRONG.search(t or ""))
NOT_START = re.compile(r"^(how|why|who are|mapping|explainer|analysis|opinion|the view|inside|is|are|will|would|could|should|can|does|do|did)\b", re.I)
def is_unrest(t):
    if t and re.search(r"\b(to hold|to stage|set to|plans? to|will hold|will stage|planned)\s+(?:a\s+)?(?:protest|rally|march|demonstration)", t, re.I) and not is_strong(t): return False
    if not t or NOT_EVENT.search(t) or NOT_START.search(t) or t.rstrip().endswith("?"): return False
    m = METAPHOR.search(t)
    if m and COUP.search(m.group(0) + t[m.end():m.end() + 10]) or re.search(r"\b(constitutional|judicial|legal|soft|silent)\s+coup\b|\bcoup\?|\bcoup or\b", t, re.I):
        return False
    if CURFEW.search(t) and YOUTH.search(t) and not ESCAL.search(t): return False
    if re.search(r"\b(akin to|like|tantamount to|amounts? to|compared? to|order resembling)\s+(a\s+)?(martial law|coup|insurrection)", t, re.I): return False
    if PHYS.search(t): return True
    if CLASH.search(t) and CLASH_CUE.search(t): return True
    if PROTEST.search(t) and PROTEST_CUE.search(t) and not re.search(
            r"\bprotests? (?:the |a |new |against )?(?:bills?|plans?|rules?|decision|move|laws?|polic(?:y|ies)|bans?|cuts|proposals?|changes|curriculum)\b", t, re.I):
        return True
    if CURFEW.search(t) and not YOUTH.search(t): return True
    if CRACK.search(t) and CRACK_CUE.search(t): return True
    if COUP.search(t) and COUP_CUE.search(t): return True
    return False

US = re.compile(
    r"\b(u\.s\.a?\.?|united states|america|american|national guard|washington,? d\.?c\.?|new york|nyc|chicago|los angeles|l\.a\.|portland|minneapolis|"
    r"st\.? paul|seattle|denver|atlanta|detroit|boston|philadelphia|philly|dallas|houston|austin|phoenix|miami|charlotte|baltimore|san francisco|"
    r"oakland|san diego|new orleans|nashville|memphis|milwaukee|cleveland|columbus|cincinnati|pittsburgh|kansas city|st\.? louis|tucson|las vegas|"
    r"salt lake|sacramento|boyle heights|"
    r"alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|"
    r"louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|"
    r"north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|"
    r"west virginia|wisconsin|wyoming|trump|biden|fbi|dhs|ice agents?|ice officers?|ice raids?|ice facility|capitol|pentagon|white house|congress)\b", re.I)
US_FOREIGN = re.compile(r"\b(france|french|paris|poland|polish|ecuador|ghana|bangladesh|germany|german|frankfurt|berlin|italy|italian|rome|india|delhi|moldova|"
                        r"paraguay|britain|british|london|england|scotland|canada|mexico|brazil|nigeria|kenya|israel|israeli|gaza|west bank|iran|russia|ukraine|"
                        r"china|japan|korea|taiwan|spain|portugal|greece|turkey|pakistan|philippines|indonesia|thailand|australia|chile|argentina|colombia|"
                        r"peru|venezuela|haiti|cuba|egypt|sudan|ethiopia|lebanon|syria|iraq|yemen|saudi|uae|madagascar|kazakhstan|senegal|sahel|amsterdam|"
                        r"netherlands|dutch|belgium|serbia|georgia's|tbilisi|armenia|nepal|sri lanka|mali|niger|cameroon|togo|bolivia|peru)\b", re.I)
_ICE = re.compile(r"\bICE\b|\bEast Bay\b")
def is_us(t, loc=""):
    blob = f"{t} {loc or ''}"
    if not (US.search(blob) or _ICE.search(t or "")): return False
    if US_FOREIGN.search(blob) and not US.search(t): return False
    if US_FOREIGN.search(t) and len(US.findall(t)) <= 1 and re.search(r"\b(trump|america|american|u\.s\.|united states|congress|white house)\b", t, re.I):
        return False   # "Trump says ... France protests" is world news about another country
    return True

UK_GEO = re.compile(r"\b(uk|u\.k\.|united kingdom|britain|british|england|english|scotland|scottish|wales|welsh|northern ireland|london|londoners?|"
                    r"manchester|birmingham|liverpool|leeds|sheffield|bristol|glasgow|edinburgh|belfast|cardiff|newcastle|nottingham|leicester|"
                    r"met police|metropolitan police|scotland yard|mi5|mi6|gchq|downing street|westminster|whitehall|starmer|home office|home secretary)\b", re.I)
UK_SEC = re.compile(r"\b(terror\w*|counter-terror\w*|extremis\w*|far-right|jihadi\w*|bomb\w*|explosive|mass stabbing|stabbing spree|knife attack|machete attack|"
                    r"stabbing of (?:two|three|four|five|six|seven|several|\d+)|shooting|shot dead|gunman|"
                    r"cyber[- ]?attacks?|cyberattacks?|ransomware|hack(?:ed|ers?|ing)|data breach|riot\w*|disorder|unrest|protest\w*|demonstrat\w*|clash\w*|"
                    r"palestine action|spy|spies|espionage|sabotage|drones? (?:over|sighted|spotted)|russian (?:ship|submarine|spy|vessel|jets?|drones?)|"
                    r"national security|security services|threat level|armed police|counter-?terrorism|arson attack|attacks?|violence|violent|gunfire|firearms?|"
                    r"critical incident|evacuated after|bomb threat|threats? received|officers? (?:hurt|injured|attacked|stabbed)|state threats?)\b", re.I)
UK_NOT = re.compile(r"\b(spy(?:ing)? on|private investigators?|affair|terror tsar|terrorism watchdog|in terror|domestic violence|domestic abuse|football|premier league|cricket|rugby|tennis|f1|formula one|strictly|bake off|x factor|eurovision|recipe|travel|holiday|"
                    r"heart attack|panic attack|asthma attack|shark attack|dog attack|review|obituary|crossword|quiz|fashion|royal baby)\b", re.I)
UK_COURT = re.compile(r"\b(trial|court hears|told a court|court rules|jury|sentenced|jailed|inquest|appeal|tribunal|convicted|contempt)\b", re.I)
UK_DOMAINS = ("bbc.co.uk", "bbc.com", "theguardian.com", "news.sky.com", "skynews.com", "standard.co.uk", "independent.co.uk", "telegraph.co.uk",
              "thetimes.co.uk", "thetimes.com", "itv.com", "channel4.com", "inews.co.uk", "scotsman.com", "heraldscotland.com")
NOT_UK = re.compile(r"\b(ireland|irish|dublin|ont\.|ontario|canada|krak[o\u00f3]w|poland|france|paris|bondi|australia|new south wales|u\.s\.|america)\b", re.I)
UK_LOCAL = re.compile(r"\b(police|officers?|arrest\w*|critical incident|evacuated|disorder|riot\w*|terror\w*|stabbing|shooting|gunfire|bomb)\b", re.I)
PROTESTY = re.compile(r"\b(protest\w*|demonstrat\w*|clash\w*|march\w*)\b", re.I)
def is_uk(t, uk_feed=False):
    if not t or UK_NOT.search(t) or (NOT_EVENT.search(t) or NOT_START.search(t)) and not re.search(r"terror", t, re.I): return False
    if not (uk_feed or UK_GEO.search(t)): return False
    if NOT_UK.search(t) and not re.search(r"\b(northern ireland|belfast|derry)\b", t, re.I) and not UK_GEO.search(re.sub(r"\b(british|briton)s?\b", "", t, flags=re.I)): return False
    if not UK_SEC.search(t): return False
    sec = [m.group(0).lower() for m in UK_SEC.finditer(t)]
    if all(PROTESTY.fullmatch(x) for x in sec) and not is_unrest(t): return False   # "despite MPs' protests" is not unrest
    if re.search(r"\battacks?\b", t, re.I) and not re.search(r"\b(terror|knife|cyber|bomb|arson|drone|missile|police|acid|mass)\b", t, re.I) and len(UK_SEC.findall(t)) < 2:
        return False
    if UK_COURT.search(t) and not re.search(r"terror|espionage|spying for|palestine action|riot", t, re.I): return False
    return True

# ------------------------------------------------------------------ fetchers
def _gn(url):
    for i in range(2):
        try: return _get(url)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or i: raise
            time.sleep(8)
def _get(url, timeout=12):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=timeout)
    if r.status != 200: raise RuntimeError(f"HTTP {r.status}")
    return r.read(3_000_000).decode("utf-8", "replace")
def _ts(s):
    if not s: return None
    try: return parsedate_to_datetime(s).timestamp()
    except Exception: pass
    for f in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            import calendar, datetime
            d = datetime.datetime.strptime(s.replace(".000", ""), f)
            return d.timestamp() if d.tzinfo else calendar.timegm(d.timetuple())
        except Exception: continue
    try:
        import datetime; return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception: return None
def _rss(xml_text, feed_domain=None):
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        f = {}; src = None
        for ch in el:
            k = ch.tag.split("}")[-1]
            if k == "link" and ch.get("href"): f["link"] = ch.get("href")
            elif k == "source" and ch.get("url"): src = ch.get("url")
            elif k in ("title", "link", "pubDate", "date", "published", "updated") and (ch.text or "").strip(): f.setdefault(k, ch.text.strip())
        t = f.get("title"); link = f.get("link")
        if not t or not link: continue
        dom = urllib.parse.urlparse(src).netloc if src else (feed_domain or urllib.parse.urlparse(link).netloc)
        out.append({"title": t, "url": link, "domain": dom, "t": _ts(f.get("pubDate") or f.get("date") or f.get("published") or f.get("updated")),
                    "direct": not src})
    return out

UNREST_Q = ['(protest OR protesters OR riot OR rioters OR clashes OR "tear gas") when:7d',
            '(curfew OR crackdown OR "general strike" OR coup OR "martial law" OR "national guard") when:7d',
            '(protest OR protesters OR riot OR clashes) when:1d',
            '("anti-government protests" OR "riot police" OR "tear gas" OR "security forces" protesters) when:7d',
            '(protesters OR demonstrators) (killed OR arrested OR detained OR injured) when:7d',
            '(protest OR protesters OR "National Guard") (ICE OR police OR troops) when:3d']
UNREST_Q_INTL = [('(protest OR protesters OR riot OR clashes OR curfew) when:7d', "en-IN", "IN"),
                 ('(protest OR protesters OR riot OR clashes OR curfew) when:7d', "en-GB", "GB"),
                 ('(protest OR protesters OR riot OR clashes OR curfew) when:7d', "en-KE", "KE")]
UK_Q = ['(London OR UK OR Britain) (terror OR riot OR protest OR stabbing OR "cyber attack" OR "Met Police" OR disorder) when:7d',
        '(London OR UK OR Britain) (terror OR riot OR protest OR "cyber attack" OR "Met Police") when:1d',
        '(UK OR Britain OR British) ("national security" OR spy OR espionage OR sabotage OR "state threat" OR drones OR ransomware OR "cyber attack") when:7d',
        '(London OR Manchester OR Birmingham OR Glasgow) (police OR "armed police") (stabbing OR shooting OR attack OR evacuated OR "critical incident" OR violence) when:7d']
GN = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{hl0}"
RSS = [  # (url, domain, kinds, uk_feed)
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "bbc.co.uk", "u", False),
    ("https://feeds.bbci.co.uk/news/uk/rss.xml", "bbc.co.uk", "uk", True),
    ("https://feeds.bbci.co.uk/news/england/london/rss.xml", "bbc.co.uk", "uk", True),
    ("https://www.theguardian.com/uk-news/rss", "theguardian.com", "uk", True),
    ("https://www.theguardian.com/world/rss", "theguardian.com", "u", False),
    ("https://feeds.skynews.com/feeds/rss/uk.xml", "news.sky.com", "uk", True),
    ("https://feeds.skynews.com/feeds/rss/world.xml", "news.sky.com", "u", False),
    ("https://www.aljazeera.com/xml/rss/all.xml", "aljazeera.com", "u", False),
    ("https://rss.dw.com/rdf/rss-en-world", "dw.com", "u", False),
    ("https://www.france24.com/en/rss", "france24.com", "u", False),
    ("https://feeds.npr.org/1004/rss.xml", "npr.org", "u", False),
    ("https://www.cbsnews.com/latest/rss/world", "cbsnews.com", "u", False),
    ("https://feeds.nbcnews.com/nbcnews/public/world", "nbcnews.com", "u", False),
    ("https://www.standard.co.uk/news/london/rss", "standard.co.uk", "uk", True),
]
GDELT_Q = [("u", '(protest OR protesters OR riot OR clashes OR curfew OR crackdown OR "general strike" OR coup OR "martial law" OR "national guard")', "24h"),
           ("u", '(protest OR protesters OR riot OR clashes OR curfew OR crackdown OR "general strike" OR coup OR "martial law" OR "national guard")', "7d"),
           ("uk", '(London OR Britain OR "Met Police") (protest OR riot OR terror OR stabbing OR cyberattack OR disorder)', "7d")]
_gd = {"next": 0.0, "last": 0.0}
def _gdelt(q, span):
    if time.time() < _gd["next"]: raise RuntimeError("GDELT backing off after rate limit")
    wait = 12 - (time.time() - _gd["last"]) if _gd["last"] else 0
    if wait > 0: time.sleep(wait)
    _gd["last"] = time.time()
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
        {"query": q + " sourcelang:english", "mode": "artlist", "format": "json", "maxrecords": 250, "timespan": span, "sort": "datedesc"})
    try: txt = _get(url, timeout=25)
    except urllib.error.HTTPError as e:
        if e.code == 429: _gd["next"] = time.time() + 3600
        raise
    if txt.startswith("Please limit"): _gd["next"] = time.time() + 3600; raise RuntimeError("GDELT rate limit (429)")
    return [{"title": a.get("title"), "url": a.get("url"), "domain": a.get("domain"), "t": _ts(a.get("seendate")), "direct": True,
             "country": a.get("sourcecountry")} for a in (json.loads(txt or "{}").get("articles") or [])]

def fetch_all(log=None):
    """Network pass. Returns raw candidate items (kind 'u' unrest / 'uk') plus a per-source status list."""
    items, status = [], []
    def run(name, kind, fn, uk_feed=False):
        t0 = time.time()
        try:
            got = fn(); n = 0
            for it in got:
                it["kind"] = kind; it["uk_feed"] = uk_feed; it["via"] = name; items.append(it); n += 1
            status.append({"src": name, "ok": True, "n": n, "ms": int((time.time() - t0) * 1000)})
        except Exception as e:
            status.append({"src": name, "ok": False, "err": str(e)[:120], "ms": int((time.time() - t0) * 1000)})
    for url, dom, kind, ukf in RSS:
        run(dom + " RSS " + url.split("/")[-2 if url.endswith(".xml") else -1][:20], kind, lambda u=url, d=dom: _rss(_get(u), d), ukf)
    for q in UNREST_Q:
        time.sleep(3); run("Google News: " + q[:40], "u", lambda q=q: _rss(_gn(GN.format(q=urllib.parse.quote(q), hl="en-US", gl="US", hl0="en"))))
    for q, hl, gl in UNREST_Q_INTL:
        time.sleep(3); run(f"Google News {gl}: " + q[:30], "u", lambda q=q, hl=hl, gl=gl: _rss(_gn(GN.format(q=urllib.parse.quote(q), hl=hl, gl=gl, hl0="en"))))
    for q in UK_Q:
        time.sleep(3); run("Google News UK: " + q[:40], "uk", lambda q=q: _rss(_gn(GN.format(q=urllib.parse.quote(q), hl="en-GB", gl="GB", hl0="en"))))
    for kind, q, span in GDELT_Q:
        run(f"GDELT DOC 2.0 ({kind}, {span})", kind, lambda q=q, s=span: _gdelt(q, s))
    return items, status

# ------------------------------------------------------------------ filtering, dedupe, ranking
_STOP = set("a an the of in on at to for and or but is are was were be been as by with from after over into amid against new says say said its it this that "
            "their his her they he she who what how why when as up out more than not no".split())
def _bi(t):
    ws = [w for w in re.findall(r"[a-z0-9']+", (t or "").lower().replace("\u2019", "'")) if w not in _STOP]
    return {a + " " + b for a, b in zip(ws, ws[1:]) if len(a) > 2 and len(b) > 2}
def _toks(t): return {w for w in re.findall(r"[a-z0-9']+", (t or "").lower().replace("\u2019", "'")) if len(w) > 2 and w not in _STOP}
_GENERIC = set("police protest protests protesters riot clashes thousands hundreds dozens video watch breaking live update new after over as in at the a "
               "government president minister court national security forces army troops city cities streets man woman men women two three four five "
               "center centre square street house state university hospital park department office council home site data ai new york times "
               "monday tuesday wednesday thursday friday saturday sunday november october december january".split())
_NORM = {"french": "france", "paris": "france", "marseille": "france", "dutch": "netherlands", "amsterdam": "netherlands",
         "serbian": "serbia", "belgrade": "serbia", "spanish": "spain", "madrid": "spain", "czech": "czechia", "prague": "czechia", "iranian": "iran",
         "tehran": "iran", "israeli": "israel", "ukrainian": "ukraine", "russian": "russia", "german": "germany", "berlin": "germany", "italian": "italy",
         "polish": "poland", "tirana": "albania", "albanian": "albania", "lyon": "france", "british": "uk", "britain": "uk", "london": "uk", "philly": "philadelphia", "paraguayan": "paraguay"}
COUNTRIES = set(_NORM.values()) | set("albania serbia georgia kenya nigeria pakistan bangladesh india indonesia philippines thailand nepal sri iran iraq syria lebanon "
    "israel turkey greece spain portugal italy germany belgium switzerland zurich poland czechia hungary romania bulgaria moldova ukraine russia "
    "belarus mexico brazil argentina chile peru bolivia ecuador colombia venezuela paraguay haiti cuba madagascar mali niger senegal togo cameroon "
    "ghana ethiopia sudan uganda tanzania mozambique morocco tunisia egypt libya guinea-bissau guinea".split())
TOPIC_COUNTRIES = {"israel", "iran", "russia", "ukraine", "uk", "palestine", "gaza", "china", "us"}
def _props(t):
    ws = re.findall(r"\b[A-Z][A-Za-z\u00C0-\u017F'\u2019-]{2,}", t or "")
    return {_NORM.get(x, x) for x in (re.sub(r"['\u2019]s$", "", w.lower()) for w in ws)} - _GENERIC - _STOP
def _sim(a, b):
    if not a or not b: return 0.0
    i = len(a & b); return max(i / min(len(a), len(b)) if min(len(a), len(b)) >= 4 else 0, i / len(a | b))
SEV3 = re.compile(r"\b(killed|kills|dead|deaths?|died|martial law|coup attempt|attempted coup|military coup|state of emergency|terror attack|shot dead|massacre|fatal)\b", re.I)
SEV2 = re.compile(r"\b(riot\w*|clash\w*|tear gas|looting|curfew|crackdown|national guard|arrest\w*|stabb\w*|cyber[- ]?attack\w*|ransomware|injur\w*|terror\w*|"
                  r"water cannon|rubber bullets|troops|general strike|explosi\w*|bomb\w*)\b", re.I)
def rank_of(title, outlets):
    sev = 3 if SEV3.search(title) else 2 if SEV2.search(title) else 1
    r = 1 + sev + min(outlets, 4)
    if outlets < 2: r = min(r, 3)
    if sev < 3: r = min(r, 6)
    return max(1, min(r, 8))

def build_events(items, kind, now, horizon=7 * 86400):
    """Filter raw items to the topic, keep reputable outlets, clean headlines and group into events."""
    keep = []
    for it in items:
        if it.get("kind") != kind and not (kind == "uk" and it.get("kind") == "u"): continue
        dom, name = outlet(it.get("domain"))
        if not dom: continue
        t = it.get("t") or 0
        if not t or t < now - horizon or t > now + 3600: continue
        title = clean_headline(it.get("title"), name)
        if len(title) < 25: continue
        ok = is_unrest(title) if kind == "u" else is_uk(title, it.get("uk_feed") or (it.get("via", "").startswith("Google News UK") and dom in UK_DOMAINS
                                                                                and bool(UK_LOCAL.search(title))))
        if not ok: continue
        keep.append({"title": title, "url": it.get("url"), "direct": bool(it.get("direct")), "domain": dom, "outlet": name, "t": t, "tok": _toks(title), "pr": _props(title), "bi": _bi(title)})
    seen = set(); uniq = []
    for k in sorted(keep, key=lambda x: x["t"]):
        key = (k["domain"], k["title"].lower()[:80])
        if key in seen or k["url"] in seen: continue
        seen.add(key); seen.add(k["url"]); uniq.append(k)
    keep = uniq
    ev = []
    for k in keep:
        best = None
        for e in ev:
            if abs(k["t"] - e["t"]) > 30 * 3600: continue
            s = max(_sim(k["tok"], m) for m in e["toks"]); shp = len(k["pr"] & e["pr"]); shb = len(k["bi"] & e["bi"])
            same_country = bool(k["pr"] & e["pr"] & (COUNTRIES - TOPIC_COUNTRIES)) and kind == "u" and is_strong(k["title"]) and any(is_strong(i["title"]) for i in e["items"]) \
                and abs(k["t"] - e["t"]) <= 24 * 3600
            same_place = kind == "u" and bool((k["pr"] & e["pr"]) - TOPIC_COUNTRIES) and abs(k["t"] - e["t"]) <= 12 * 3600 and s >= 0.12 \
                and (is_strong(k["title"]) or PROTEST.search(k["title"]))
            if same_country or same_place or s >= 0.55 or (shp >= 2 and s >= 0.15) or (shp >= 1 and s >= 0.3) or (shb >= 1 and shp >= 1 and s >= 0.2):
                sc = s + 0.2 * shp
                if best is None or sc > best[0]: best = (sc, e)
        if best:
            e = best[1]; e["items"].append(k); e["toks"].append(k["tok"]); e["t1"] = max(e["t1"], k["t"]); e["pr"] |= k["pr"]; e["bi"] |= k["bi"]
            e["outlets"].setdefault(k["domain"], k["outlet"])

        else:
            ev.append({"title": k["title"], "url": k["url"], "direct": k["direct"], "domain": k["domain"], "t": k["t"], "t1": k["t"],
                       "items": [k], "toks": [k["tok"]], "pr": set(k["pr"]), "bi": set(k["bi"]), "outlets": {k["domain"]: k["outlet"]}})
    out = []
    WIRE = ("apnews.com", "reuters.com", "afp.com", "bbc.co.uk", "bbc.com")
    for e in ev:
        n = len(e["outlets"])
        if n < 2 and kind == "u" and not any(is_strong(i["title"]) or (is_us(i["title"]) and US_PHYS.search(i["title"])) for i in e["items"]):
            continue   # single-outlet mild protest abroad: not unrest (U.S. street protests at ICE sites, homes, landmarks still count)
        its = e["items"]
        # representative headline: the item most similar to the rest (medoid), wire/public broadcaster and direct links preferred
        sev = lambda i: 3 if SEV3.search(i["title"]) else 2 if SEV2.search(i["title"]) else 1
        rep_ = max(its, key=lambda i: (sev(i), round(sum(_sim(i["tok"], j["tok"]) for j in its if j is not i), 1), i["domain"] in WIRE, i["direct"], -len(i["title"])))
        url = rep_["url"] if rep_["direct"] else next((i["url"] for i in its if i["direct"]), rep_["url"])
        e["title"], e["url"] = rep_["title"], url
        out.append({"title": e["title"], "url": e["url"], "t": e["t"], "t1": e["t1"], "n_outlets": n,
                    "outlets": list(dict.fromkeys(e["outlets"].values()))[:4], "rank": rank_of(e["title"], n), "us": is_us(e["title"]) if kind == "u" else None})
    return out

# ------------------------------------------------------------------ cache
def _cache_path():
    d = os.environ.get("BN_STATE_DIR") or os.path.join(BASE, "data")
    try: os.makedirs(d, exist_ok=True)
    except Exception: d = "/tmp"
    return os.path.join(d, "unrest_ext_cache.json")
_C = {"v": None, "t": 0.0, "busy": False}
_lk = threading.Lock()
def refresh(now=None):
    now = now or time.time()
    items, status = fetch_all()
    # keep the previous GDELT pull if this pass could not reach it (rate limit), so a 429 doesn't drop world coverage
    prev = _C["v"] or _load() or {}
    failed = {s["src"] for s in status if not s["ok"]}
    if failed:   # a dead or rate-limited source keeps its last good pull (up to 7 days old) instead of dropping coverage
        old = [i for i in (prev.get("raw") or []) if i.get("via") in failed and (i.get("t") or 0) >= now - 7 * 86400]
        items += old
        for s in status:
            if s["src"] in failed: s["carried"] = sum(1 for i in old if i.get("via") == s["src"])
    v = {"t": now, "status": status, "raw": [{k: i.get(k) for k in ("title", "url", "domain", "t", "direct", "kind", "uk_feed", "via")} for i in items]}
    _C["v"], _C["t"] = v, now
    try:
        p = _cache_path(); tmp = p + ".tmp"
        with open(tmp, "w") as f: json.dump(v, f)
        os.replace(tmp, p)
    except Exception: pass
    return v
def _load():
    try:
        with open(_cache_path()) as f: return json.load(f)
    except Exception: return None
def _kick():
    with _lk:
        if _C["busy"]: return
        _C["busy"] = True
    def run():
        try: refresh()
        except Exception: pass
        finally: _C["busy"] = False
    threading.Thread(target=run, name="bn-unrest-feeds", daemon=True).start()
def raw(now=None):
    """Cached raw items; never blocks. Starts a background refresh when the cache is older than REFRESH."""
    now = now or time.time()
    if _C["v"] is None:
        v = _load()
        if v: _C["v"], _C["t"] = v, v.get("t") or 0
    if now - _C["t"] > REFRESH and os.environ.get("BN_UNREST_FEEDS", "1") != "0": _kick()
    return (_C["v"] or {}).get("raw") or []
def events(kind, now=None):
    now = now or time.time()
    try: return build_events(raw(now), kind, now)
    except Exception: return []
def status():
    v = _C["v"] or _load() or {}
    return {"t": v.get("t"), "sources": v.get("status") or []}

if __name__ == "__main__":
    import sys
    v = refresh()
    for s in v["status"]: print(("OK  " if s["ok"] else "ERR ") + s["src"], s.get("n", ""), s.get("err", ""), f'{s["ms"]}ms')
    for k in ("u", "uk"):
        ev = build_events(v["raw"], k, time.time())
        print("\n==", k, len(ev), "events")
        for e in sorted(ev, key=lambda e: -e["t"])[:60]:
            print(time.strftime("%m-%d %H:%M", time.localtime(e["t"])), e["rank"], e["n_outlets"], "US" if e["us"] else "  ", e["title"][:110], "|", ", ".join(e["outlets"]))

# ------------------------------------------------------------------ widget assembly (Wire stories + feed events, deduped)
def combine(wire, ext, days, day_fn, now, label, split_us=False):
    """wire: [{title,url,t,ut,rank,n,loc,us}] from The Wire; ext: build_events() output. Returns the widget dict the homepage JS reads."""
    evs = []
    for w in sorted(wire, key=lambda w: (-int(w.get("rank") or 0), -int(w.get("n") or 0))):
        wt = _toks(w["title"])
        if any(abs(v["t"] - w["t"]) <= 36 * 3600 and _sim(wt, v["tok"]) >= 0.6 for v in evs): continue   # same event twice on The Wire
        evs.append({"title": w["title"], "url": w["url"], "t": w["t"], "ut": w.get("ut") or w["t"], "rank": int(w.get("rank") or 0), "wire_n": int(w.get("n") or 0),
                    "outlets": [], "n_out": 0, "ext": False, "us": w.get("us"), "loc": w.get("loc"), "tok": _toks(w["title"]), "pr": _props(w["title"])})
    for e in ext:
        tok, pr = _toks(e["title"]), _props(e["title"]); hit = None
        for v in evs:
            if v["ext"] or abs(v["t"] - e["t"]) > 36 * 3600: continue
            s = _sim(tok, v["tok"]); shp = len(pr & v["pr"])
            if s >= 0.5 or (shp >= 2 and s >= 0.2): hit = v; break
        if hit:   # same event already on The Wire: keep our story page, add outlet count
            hit["outlets"] = e["outlets"]; hit["n_out"] = e["n_outlets"]; hit["rank"] = max(hit["rank"], e["rank"])
            hit["ut"] = max(hit["ut"], e["t1"]); continue
        evs.append({"title": e["title"], "url": e["url"], "t": e["t"], "ut": e["t1"], "rank": e["rank"], "wire_n": 0, "outlets": e["outlets"],
                    "n_out": e["n_outlets"], "ext": True, "us": e.get("us"), "loc": None, "tok": tok, "pr": pr})
    def agg(sel):
        d = {x: [0, 0] for x in days}; st = {x: [] for x in days}; n24 = 0; mx = 0; top = None
        for v in sel:
            k = day_fn(v["t"])
            if k in d: d[k][1 if v["rank"] >= 7 else 0] += 1; st[k].append(v)
            if v["ut"] >= now - 86400:
                n24 += 1; mx = max(mx, v["rank"])
                if top is None or (v["rank"], v["n_out"] + v["wire_n"], v["ut"]) > (top["rank"], top["n_out"] + top["wire_n"], top["ut"]): top = v
        return d, st, n24, mx, top
    def item(v):
        if v["ext"]:
            src = f'{v["n_out"]} outlet{"s" if v["n_out"] != 1 else ""} \u00b7 ' + ", ".join(v["outlets"][:3])
        elif v["n_out"]:
            src = f'The Wire + {v["n_out"]} outlet{"s" if v["n_out"] != 1 else ""}'
        else:
            src = f'The Wire \u00b7 {v["wire_n"]} source{"s" if v["wire_n"] != 1 else ""}' if v["wire_n"] else "The Wire"
        o = {"rank": v["rank"], "url": v["url"], "title": v["title"], "loc": v.get("loc"), "src": src, "t": v["ut"]}
        if v["ext"]: o["ext"] = 1
        if split_us: o["us"] = 1 if v["us"] else 0
        return o
    d, st, n24, mx, top = agg(evs)
    stories = {k: [item(v) for v in sorted(st[k], key=lambda v: (-v["rank"], -(v["n_out"] + v["wire_n"]), -v["ut"]))[:14]] for k in days}
    out = {"label": label, "n24": n24, "n7": sum(a + b for a, b in d.values()), "max24": mx, "days": [[k] + d[k] for k in days], "stories": stories,
           "top": ({"rank": top["rank"], "t": top["ut"], "url": top["url"], "title": top["title"], "loc": top.get("loc"), "ext": 1 if top["ext"] else 0} if top else None),
           "src": "The Wire + world news feeds", "n_feed": sum(1 for v in evs if v["ext"]), "n_wire": sum(1 for v in evs if not v["ext"])}
    if split_us:
        for key, sel in (("us", [v for v in evs if v["us"]]), ("world", [v for v in evs if not v["us"]])):
            d2, _, a24, m2, t2 = agg(sel)
            out[key] = {"n24": a24, "n7": sum(a + b for a, b in d2.values()), "max24": m2,
                        "top": ({"rank": t2["rank"], "t": t2["ut"], "url": t2["url"], "title": t2["title"]} if t2 else None)}
    return out
