"""Homepage topic cards (7-day bar charts): place matching, topic matchers, ET day bucketing and the empty-day QA check.

Display/feed layer only. Used by apple_v1.wire_groups / special_cards (Wire stories) and unrest_feeds (public feeds).

Bucketing rule (TOPIC-CARDS-1): a story is drawn on every Eastern Time calendar day it was active inside the 7-day window,
i.e. the ET day it was first seen AND the ET day it was last updated. The old code drew a story only on its first-seen day
while the "N stories in 24 hours" headline counted it by its last update, so a story first seen yesterday and updated
today said "1 story in 24 hours" over an empty today bar.
"""
import re

import et_days

# ------------------------------------------------------------------ place matching
# Homonyms are masked out before the place lists run, so "British Columbia", "New England" or "London, Ont." never count as the UK.
_MASK = [
    r"british\s+columbia\w*", r"british\s+virgin\s+islands?", r"british\s+indian\s+ocean", r"british\s+antarctic",
    r"new\s+england", r"new\s+south\s+wales", r"new\s+london", r"new\s+britain", r"new\s+wales",
    r"london,?\s+(?:ont\.?|ontario|ky\.?|kentucky|ohio|oh|ark\.?|arkansas|tx|texas|ca\b)", r"london\s+ontario", r"east\s+london,?\s+(?:south\s+africa|eastern\s+cape)",
    r"wales,?\s+(?:alaska|ak|wisconsin|wi|north\s+dakota|nd)", r"england,?\s+(?:arkansas|ar)", r"scotland\s+county", r"scotland,?\s+(?:sd|south\s+dakota|ct|connecticut)",
    r"lebanon,?\s+(?:pa\.?|pennsylvania|nh|n\.h\.|new\s+hampshire|oh\.?|ohio|tn\.?|tennessee|mo\.?|missouri|in\.?|indiana|or\.?|oregon|ky\.?|kentucky|va\.?|virginia|nj|new\s+jersey|ct|connecticut|il|illinois|ks|kansas|me|maine)(?![a-z])",
    r"lebanon\s+(?:county|valley|township|city\s+schools?|high\s+school)", r"new\s+lebanon", r"lebanon\s+junction",
    r"moscow,?\s+(?:idaho|id\.?|pa\.?|pennsylvania|tn|tennessee|vt|vermont)(?![a-z])", r"moscow\s+mule", r"university\s+of\s+idaho",
    r"odessa,?\s+(?:tx|texas|fl|florida|de|delaware|mo|missouri|ny|new\s+york|wa|washington)(?![a-z])", r"odessa\s+(?:american|high|police\s+department)",
    r"russian\s+river", r"russia,?\s+(?:ohio|oh|ny|new\s+york)(?![a-z])", r"jerusalem\s+artichokes?", r"jerusalem,?\s+(?:ny|new\s+york|ohio|oh)(?![a-z])",
    r"petersburg,?\s+(?:fl|florida|va|virginia|ak|alaska)(?![a-z])", r"st\.?\s+petersburg,?\s+(?:fl|florida)(?![a-z])",
    r"georgia,?\s+(?:usa|u\.s\.)", r"birmingham,?\s+(?:al\.?|ala\.?|alabama|mi\.?|michigan)(?![a-z])", r"manchester,?\s+(?:nh|n\.h\.|new\s+hampshire|ct|conn\.?|connecticut|tn|tennessee|vt|vermont|ky|kentucky|md|maryland|mo|missouri|ia|iowa|nj|new\s+jersey)(?![a-z])",
    r"bristol,?\s+(?:tn|tennessee|va|virginia|ct|conn\.?|connecticut|pa|pennsylvania|ri|rhode\s+island|in|indiana)(?![a-z])", r"newcastle,?\s+(?:nsw|australia|wy|wyoming|de|delaware|ok|oklahoma|pa|pennsylvania|wa|washington|ca|california|in|indiana)(?![a-z])",
    r"leicester,?\s+(?:ma|mass\.?|massachusetts|nc|north\s+carolina|vt|vermont|ny)(?![a-z])", r"plymouth,?\s+(?:ma|mass\.?|massachusetts|mn|minnesota|mi|michigan|nh|new\s+hampshire|in|indiana|wi|wisconsin|ct)(?![a-z])",
    r"cambridge,?\s+(?:ma|mass\.?|massachusetts|md|maryland|mn|ohio|oh|ontario)(?![a-z])", r"cardiff[- ]by[- ]the[- ]sea", r"glasgow,?\s+(?:ky|kentucky|mt|montana|de|delaware|va|virginia)(?![a-z])",
    r"edinburgh,?\s+(?:in|indiana|tx|texas)(?![a-z])", r"aberdeen,?\s+(?:sd|south\s+dakota|wa|washington|md|maryland|nc|ms)(?![a-z])", r"durham,?\s+(?:nc|n\.c\.|north\s+carolina|nh|new\s+hampshire)(?![a-z])",
    r"london\s+(?:breed|stock\s+exchange\s+group)",  # (people / listing names, not events in London)
]
_MASK_RX = re.compile(r"\b(?:" + "|".join(_MASK) + r")", re.I)
def mask_homonyms(s):
    return _MASK_RX.sub(" ", s or "")

UK_CORE_I = re.compile(
    r"\b(u\.k\.|united\s+kingdom|great\s+britain|britain|british|britons?|england|scotland|scottish|wales|welsh|northern\s+ireland|"
    r"london|londoners?|edinburgh|glasgow|belfast|cardiff|liverpool|leeds|sheffield|southport|swansea|dundee|coventry|bradford|"
    r"met\s+police|metropolitan\s+police|scotland\s+yard|mi5|mi6|gchq|downing\s+street|westminster|whitehall|keir\s+starmer|starmer|"
    r"home\s+office|home\s+secretary|house\s+of\s+commons|nhs\s+england|police\s+scotland|royal\s+navy)\b", re.I)
UK_CAPS = re.compile(r"\b(UK|RAF|NHS)\b")   # abbreviations count only in capitals
# Cities that share a name with large U.S./Commonwealth places: they count only when nothing in the text points elsewhere.
UK_AMBIG = re.compile(r"\b(birmingham|manchester|bristol|newcastle|nottingham|leicester|plymouth|cambridge|oxford|durham|portsmouth|brighton|aberdeen)\b", re.I)
ELSEWHERE = re.compile(
    r"\b(u\.s\.|usa|united\s+states|america|american|canada|canadian|ontario|quebec|alberta|vancouver|toronto|australia|australian|sydney|melbourne|"
    r"queensland|new\s+south\s+wales|nsw|new\s+zealand|south\s+africa|alabama|new\s+hampshire|connecticut|tennessee|virginia|massachusetts|michigan|kentucky|maryland|"
    r"pennsylvania|ohio|texas|florida|california|idaho|new\s+jersey|indiana|oregon|missouri|county|sheriff)\b", re.I)

def is_uk_place(t, loc=""):
    """True when the text names a place or institution in the United Kingdom (word boundaries, homonyms masked)."""
    blob = mask_homonyms(f"{t or ''} {loc or ''}")
    if UK_CAPS.search(blob) or UK_CORE_I.search(blob): return True
    return bool(UK_AMBIG.search(blob)) and not ELSEWHERE.search(f"{t or ''} {loc or ''}")

_IL = re.compile(r"\b(israel|israeli|israelis|gaza|gazans?|idf|hamas|hezbollah|west\s+bank|lebanon|lebanese|beirut|houthis?|yemen|yemeni|sanaa|"
                 r"netanyahu|tel\s+aviv|jerusalem|rafah|khan\s+younis|jenin|nablus|golan)\b", re.I)
_IR = re.compile(r"\b(iran|iranian|iranians|tehran|irgc|khamenei|araghchi|pezeshkian|isfahan|natanz|fordow)\b", re.I)
_RU = re.compile(r"\b(russia|russian|russians|ukraine|ukrainian|ukrainians|kyiv|kiev|kharkiv|kherson|zaporizhzhia|moscow|kremlin|putin|zelensky\w*|zelenskiy|"
                 r"donetsk|luhansk|donbas|crimea|crimean|odesa|odessa|dnipro|lviv|pokrovsk|kursk|belgorod|sevastopol|volgograd|rostov|bryansk|novorossiysk|"
                 r"tuapse|saratov|smolensk|voronezh|krasnodar|sumy|vinnytsia|mykolaiv|poltava|chernihiv|kramatorsk|kostiantynivka|bakhmut|avdiivka|"
                 r"kupiansk|huliaipole|zelenskyy)\b", re.I)
def is_il(t, loc=""): return bool(_IL.search(mask_homonyms(f"{t or ''} {loc or ''}")))
def is_ir(t, loc=""): return bool(_IR.search(mask_homonyms(f"{t or ''} {loc or ''}")))
def is_ru(t, loc=""): return bool(_RU.search(mask_homonyms(f"{t or ''} {loc or ''}")))

# ------------------------------------------------------------------ topic sanity (the scanner's category is sometimes wrong)
QUAKEISH = re.compile(r"\b(earthquake|magnitude\s*\d|m\s*\d+(?:\.\d+)?\s*(?:earthquake|quake)|seismic|tsunami)\b", re.I)
WEATHER = re.compile(
    r"\b(beach\s+hazards?|rip\s+currents?|sneaker\s+waves?|high\s+surf|small\s+craft|flood(?:s|ing|ed)?|flash\s+flood|heavy\s+rain|rainfall|drenching|"
    r"atmospheric\s+river|snow(?:fall|storm)?|blizzard|winter\s+storm|ice\s+storm|freez\w+|frost|tornado\w*|hurricane|tropical\s+storm|typhoon|cyclone|"
    r"thunderstorms?|wind\s+(?:advisory|warning|gusts?)|red\s+flag\s+warning|fire\s+weather|wildfires?|heat\s+(?:advisory|wave|warning)|"
    r"dense\s+fog|air\s+quality|special\s+weather\s+statement|hazardous\s+weather|weather\s+(?:service|statement|alert)|nws|evacuation\s+orders?)\b", re.I)
CONFLICT = re.compile(
    r"\b(war|wars|wartime|conflict|military|army|troops|soldiers|militants?|militia|insurgents?|rebels?|jihadi\w*|terror\w*|airstrikes?|air\s+strikes?|"
    r"strikes?|struck|missiles?|rockets?|drones?|shelling|shelled|artillery|bomb\w*|explosi\w*|attack\w*|offensive|invasion|invade\w*|ceasefire|truce|"
    r"hostages?|killed|kills|dead|deaths|casualties|wounded|massacre|clash\w*|fighting|battle\w*|front\s*line|occupied|occupation|siege|navy|naval|"
    r"warship|frigate|submarine|fighter\s+jets?|air\s+defen[cs]e|intercept\w*|sanctions|nuclear|weapons?|gunmen|gunfire|ambush\w*|raid\w*|coup|junta|"
    r"genocide|refugees?|displaced|annex\w*|mobiliz\w*|conscript\w*|pentagon|nato|idf|irgc|hamas|hezbollah|houthis?|kremlin|security\s+forces)\b", re.I)

def conflict_ok(t, loc=""):
    """A war/conflict-tagged story must read like conflict, not a weather/quake product the scanner mis-tagged."""
    s = f"{t or ''}"
    if QUAKEISH.search(s): return False
    if WEATHER.search(s) and not CONFLICT.search(re.sub(WEATHER.pattern, " ", s, flags=re.I)): return False
    return True

# Outbreaks (health group)
EBOLA = re.compile(r"\b(ebola|marburg|ervebo|sudan\s+virus\s+disease)\b", re.I)
MEASLES = re.compile(r"\bmeasles\b", re.I)
DISEASE = re.compile(
    r"\b(outbreaks?|virus|viral|cholera|influenza|flu\b|h5n1|h5n5|h7n9|h9n2|bird\s+flu|avian\s+(?:flu|influenza)|hpai|mpox|monkeypox|dengue|chikungunya|zika|"
    r"plague|pathogens?|epidemic|pandemic|polio|tuberculosis|\btb\b|meningitis|anthrax|rift\s+valley|mers|sars|covid\w*|coronavirus|nipah|lassa|"
    r"diphtheria|pertussis|whooping\s+cough|legionnaires|legionella|listeria|salmonella|e\.?\s*coli|norovirus|hepatitis|rabies|malaria|yellow\s+fever|"
    r"oropouche|screwworm|west\s+nile|rsv|infections?|cases\s+(?:rise|rising|surge)|disease\s+outbreak\s+news|who\s+(?:says|warns|declares))\b", re.I)
NOT_DISEASE = re.compile(r"\b((?:weather|storm|tornado|severe\s+weather|war|violence)\s+outbreaks?|computer\s+virus|viral\s+(?:video|post|clip|tiktok|moment|trend)|went\s+viral|"
                         r"goes\s+viral|go\s+viral|flu\s+(?:season\s+)?(?:shots?\s+)?clinic\s+hours)\b", re.I)
def is_ebola(t): return bool(EBOLA.search(t or ""))
def is_measles(t): return bool(MEASLES.search(t or ""))
def is_outbreak(t):
    t = t or ""
    if is_ebola(t) or is_measles(t) or NOT_DISEASE.search(t): return False
    return bool(DISEASE.search(t))

# Food and supply chain: food security, shortages, recalls, animal disease hitting food supply, shipping/ports, inputs.
FOOD = re.compile(
    r"\b(food\s+(?:shortages?|supply|supplies|prices?|bank|banks|insecurity|security|recalls?|crisis|rationing|aid|inflation|safety\s+alert|exports?|imports?)|"
    r"(?:supply\s+chain|supply-chain)(?!\s+(?:attack|compromise|hack|breach|malware|vulnerabilit\w*))|"
    r"grocery\s+(?:prices?|shortages?|bills?|costs?|inflation|recalls?)|groceries|"
    r"(?:product|mass|voluntary|nationwide|food|meat|poultry|egg|produce|beef|pork|chicken|cheese|milk|formula)\s+recalls?|recall\w*\s+(?:of\s+)?(?:\w+\s+){0,4}(?:over|due\s+to|after)\s+(?:listeria|salmonella|e\.?\s*coli|botulism|undeclared|contamination|foreign\s+material)|"
    r"listeria|salmonella|e\.?\s*coli|botulism|foodborne|food\s+poisoning|"
    r"snap\s+(?:benefits?|recipients?|payments?|funding|cuts?|program|households|card|ebt)|food\s+stamps|ebt\s+cards?|wic\s+(?:benefits?|program|funding)|"
    r"ports?\s+(?:strike|congestion|delays?|backlog|closures?|closed|shutdown|disruptions?)|dockworkers|dock\s+workers|longshore\w*|"
    r"shipping\s+(?:disruptions?|delays?|lanes?|traffic|routes?|rates|costs)|freight\s+rates|container\s+(?:rates|shipping)|red\s+sea\s+(?:shipping|attacks?)|"
    r"(?:diesel|fuel)\s+shortages?|baby\s+formula|infant\s+formula|egg\s+(?:prices?|shortages?|supply|supplies)|eggs\s+(?:prices?|shortage)|"
    r"meat\s?(?:packing\s+)?plants?|rail\s+strike|"
    r"grain\s+(?:exports?|shortages?|prices?|shipments?|deal|corridor|harvest)|wheat\s+(?:exports?|shortages?|prices?|harvest|crop)|corn\s+(?:prices?|harvest|crop)|"
    r"rice\s+(?:exports?|prices?|shortage|ban)|soybeans?\s+(?:prices?|exports?|purchases?)|fertili[sz]ers?|potash|urea|"
    r"crop\s+(?:failures?|losses?|damage)|harvests?\s+(?:fail\w*|loss\w*)|drought\s+(?:hits?|threatens?)\s+\w*\s*crops?|"
    r"famine|hunger\s+(?:crisis|alert|hotspots?|emergency|levels?)|starvation|malnutrition|acute\s+food|ipc\s+(?:phase|analysis|report)|food\s+price\s+index|"
    r"bird\s+flu|avian\s+(?:flu|influenza)|hpai|h5n1|poultry\s+(?:flocks?|farms?|culls?|outbreaks?)|(?:flocks?|birds|hens|chickens|turkeys)\s+(?:culled|depopulated|euthani[sz]ed)|cull\w*\s+(?:of\s+)?(?:\d[\d,]*\s+)?(?:birds|hens|chickens|poultry|turkeys|pigs|cattle)|"
    r"african\s+swine\s+fever|foot[- ]and[- ]mouth|screwworm|dairy\s+herds?|"
    r"strait\s+of\s+hormuz|hormuz.{0,40}(?:tanker|shipping|oil|trade|cargo)|(?:tanker|shipping|oil|trade|cargo).{0,40}hormuz|black\s+sea\s+(?:grain|shipping|ports?))\b", re.I)
_RECALL_VERB = re.compile(r"\brecalls?\s+(?:seeing|that|how|when|the\s+(?:moment|day|time)|hearing|being)\b", re.I)
_NOT_FOOD = re.compile(r"\b(snap\s+(?:election|poll|vote|judgment|decision|shot|back)|hunger\s+(?:games|strike\w*)|hungry\s+for|for\s+hunger|"
                       r"(?:software|open[- ]source|npm|pypi|github|code)\s+supply\s+chain|chip\s+supply\s+chain\s+(?:stocks?|earnings))\b", re.I)
def is_food(t):
    if not t or _RECALL_VERB.search(t) or _NOT_FOOD.search(t): return False
    return bool(FOOD.search(t))

# Nuclear threat (War group) and Election disputes (Elections group) keep their apple_v1 regexes; these wrap them for feeds.
def is_nuke(t):
    import apple_v1 as A
    return bool(re.search(A._NUK, t or "", re.I))
def is_disp(t):
    import apple_v1 as A
    t = t or ""
    return bool(A._elc_ok(t) and re.search(A._DSP, t, re.I) and not re.search(A._FOREIGN, t, re.I))

# ------------------------------------------------------------------ ET day bucketing
def active_days(first_ts, last_ts, days):
    """ET calendar days (inside `days`) a story was active: the day first seen and the day last updated."""
    out = []
    for ts in (first_ts, last_ts):
        if not ts: continue
        k = et_days.et_day(ts)
        if k in days and k not in out: out.append(k)
    return out

# ------------------------------------------------------------------ QA: no empty day on any card
def empty_days(card):
    """Days (YYYY-MM-DD) whose bar would draw empty. A card is a dict with days=[[day, low, high], ...]."""
    out = []
    for row in (card or {}).get("days") or []:
        if len(row) >= 3 and (row[1] or 0) + (row[2] or 0) <= 0: out.append(row[0])
    return out

TOPIC_CARDS = [("conf", "il"), ("conf", "ir"), ("conf", "ru"), ("conf", "uk"), ("conf", "other"),
               ("health", "ebola"), ("health", "measles"), ("health", "other"),
               ("hard", "unrest"), ("hard", "food"), ("spec", "nuke"), ("spec", "disp")]

def check_dash(dash, cards=TOPIC_CARDS):
    """{'group/key': [empty days]} for every topic card in an /api/apple/dash payload; missing cards report ['missing']."""
    bad = {}
    for g, k in cards:
        c = ((dash or {}).get(g) or {}).get(k)
        if not isinstance(c, dict) or not c.get("days"):
            bad[f"{g}/{k}"] = ["missing"]; continue
        e = empty_days(c)
        if e: bad[f"{g}/{k}"] = e
    return bad


# Feed items that are not news events (opinion, institutional notices, livestreams); celebrity takes on a war are not conflict news.
NOT_NEWS = re.compile(r"^(?:the\s+\w+\s+view\s+on|readers\s+write|letters?\b|opinion\b|editorial\b|comment\b|analysis:)|"
                      r"\b(webinar|commemorat\w*|leadership\s+framework|policy\s+basket|multidisciplinary\s+team\s+meeting|livestream\w*|podcast|"
                      r"country\s+brief|newsletter|job\s+(?:opening|vacanc\w+)|now\s+hiring|training\s+course)\b", re.I)
CELEB = re.compile(r"\b(singer|actor|actress|rapper|pop\s+star|celebrit\w+|musician|frontman|comedian|influencer)\b", re.I)

SPORTS = re.compile(r"\b(score[sd]?|fifty|century|wickets?|u-?19|under-19|paralympi\w*|olympi\w*|mma|ufc|boxing|bare-knuckle|fight\s+night|fighting\s+event|"
                    r"championships?|world\s+cup|league|tournament|match|vs\.?|innings|goalkeeper|striker|footballer)\b", re.I)
DOMESTIC = re.compile(r"\b(police\s+officers?|officers?\s+(?:injured|hurt|shot)|deput(?:y|ies)|sheriff|firefighters?|house\s+explosion|home\s+explosion|"
                      r"levels?\s+(?:a\s+)?(?:\w+\s+)?home|apartment|gas\s+leak|school\s+shooting|mall)\b", re.I)
