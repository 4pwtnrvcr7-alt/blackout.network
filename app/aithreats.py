"""🤖 AI Threats tab (listed in the main nav since t233; deep link blackout.network/#ai). 2026-10-31, t231.
AI hacking, rogue bots/agents, AI-enabled or AI-related cyber attacks, deepfake fraud and influence ops, model jailbreak / prompt
injection / poisoning, AI supply-chain compromises, AI in weapons. Scanner clusters (blackout.db, read-only) are kept when the
classifier below finds an AI term AND a threat term (or one strong AI-threat term on its own). Ranks/scores are the scanner's own.
Extra feeds (collected on the box into tabfeeds.db by tabfeeds.py): AI Incident Database RSS, The Hacker News RSS (AI-filtered).
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py or config.json."""
import re
import tabfeeds as T

TAB = "ai"; TITLE = "AI Threats"
# --- AI terms. Case-SENSITIVE "AI"/"LLM" so "Al", "said", "j'ai", "AIDS", "Air India", "aid" never match.
AI_CS = re.compile(r"(?<![\w'’.-])(?:A\.I\.|AI|AGI|GenAI|LLMs?)(?![\w'’]|\.\w)")
AI_CI = re.compile(r"\b(?:artificial[- ]intelligence|machine[- ]learning|large[- ]language[- ]models?|language[- ]models?|foundation[- ]models?|"
    r"generative[- ]ai|gen[- ]ai|chat ?gpt|gpt-?[345o]\w*|openai|anthropic|deepseek|chatbots?|ai[- ]chatbots?|deep ?fakes?|deep-fakes?|"
    r"voice[- ]clon\w*|cloned voices?|prompt[- ]injections?|agentic|ai[- ]agents?|autonomous[- ]agents?|neural[- ]networks?|"
    r"(?:model|data|training[- ]data)[- ]poisoning|microsoft copilot|github copilot|copilot ai|google gemini|gemini ai|"
    r"claude (?:ai|code|opus|sonnet|haiku)|grok (?:ai|chatbot)|xai's grok|mistral ai|hugging ?face|midjourney|stable diffusion|langflow|langchain|ollama|"
    r"comfyui|mlflow|vllm|llama\.cpp|open ?webui|flowise|anythingllm|model context protocol|mcp servers?|ai[- ](?:powered|driven|enabled|"
    r"assisted|generated|written|made|based|equipped|guided|controlled|crafted|fueled|fuelled))\b", re.I)
# --- threat context
THREAT = re.compile(r"\b(?:hack\w*|attack\w*|breach\w*|malware|ransomware|infostealer|exploit\w*|vulnerab\w*|cve-\d|zero[- ]day|0-day|"
    r"phish\w*|scam\w*|fraud\w*|impersonat\w*|espionage|spy(?:ing|ware)?|intrusions?|compromis\w*|stole|stolen|steal\w*|leak\w*|"
    r"exfiltrat\w*|backdoor\w*|jailbr[eo]ak\w*|poison\w*|rogue|misuse\w*|weaponi[sz]\w*|disinformation|misinformation|propaganda|"
    r"influence (?:op\w*|campaign\w*)|manipulat\w*|threat actors?|cyber\w*|botnets?|supply[- ]chain|malicious|abus\w*|extort\w*|sextortion|"
    r"harass\w*|surveil\w*|drones?|weapons?|missiles?|targeting|sabotag\w*|outages?|nonconsensual|non-consensual|csam|"
    r"blackmail|ddos|hijack\w*|takeover|unauthori[sz]ed|wiper|crypto ?(?:theft|heist|drain\w*)|heist|fake (?:video|audio|image|news)|"
    r"election interference|out of control|went rogue|self-replicat\w*|autonomous(?:ly)? (?:hack|attack|replicat)\w*)\b", re.I)
# --- strong AI-threat terms (enough on their own)
STRONG = re.compile(r"\b(?:deep ?fakes?|deep-fakes?|voice[- ]clon\w*|cloned voices?|prompt[- ]injections?|(?:model|data|training[- ]data)[- ]poisoning|"
    r"rogue (?:ai|bots?|agents?|models?|chatbots?)|ai (?:jailbreak\w*|worm\w*|malware|phishing|scam\w*|fraud|hack\w*|attack\w*|swarm\w*)|"
    r"(?:llm|ai|model)[- ]jailbreak\w*|jailbr[eo]ak\w* (?:the |an? )?(?:ai|llm|model|chatbot|chatgpt|claude|gemini|grok)\w*|"
    r"ai[- ](?:powered|driven|enabled|assisted|generated|crafted|fueled|fuelled) (?:cyber\w*|attack\w*|malware|ransomware|phishing|scam\w*|"
    r"fraud|hack\w*|intrusion\w*|espionage|disinformation|propaganda|botnet\w*|exploit\w*|deepfake\w*|campaign\w*|influence))\b", re.I)
# chatter that matches both lists but is not a threat report
NEG = re.compile(r"\b(?:ai (?:bubble|stocks?|boom|hub|startup|summit|earthquake)|ipo|stock market filing|earnings|shares (?:jump|plunge|fall|rise)\w*|"
    r"raises \$|funding round|valuation|webinar|careers?|bias check|reconstructions?|epidemiolog\w*|token consumption|career ladder|job (?:market|losses)|workforce|daily roundup|tech digest|evening digest|morning digest|newsletter|intelligence explosion|explosion of content|evaporat\w*)\b", re.I)
KINDS = [  # first match wins
    ("deepfake", "Deepfakes & AI fraud", re.compile(r"deep ?fake|deep-fake|voice[- ]clon|cloned voice|impersonat|scam|fraud|sextortion|synthetic (?:media|identit)|fake (?:video|audio|image)", re.I)),
    ("model", "Model jailbreak & exploitation", re.compile(r"jailbr[eo]ak|prompt[- ]injection|poison|model (?:theft|weights|extraction|inversion)|adversarial|guardrail", re.I)),
    ("rogue", "Rogue AI, bots & agents", re.compile(r"rogue|agentic|ai[- ]agents?|autonomous[- ]agents?|out of control|went rogue|self-replicat|misaligned|chatbot", re.I)),
    ("supply", "AI supply-chain compromise", re.compile(r"supply[- ]chain|hugging ?face|pypi|\bnpm\b|malicious (?:model|package|extension|plugin)|mcp server|model context protocol|langflow|langchain|ollama|comfyui|mlflow|vllm|llama\.cpp|open ?webui|flowise|anythingllm", re.I)),
    ("cyber", "AI-enabled cyber attacks", re.compile(r"attacker|malicious|trojan|hack|breach|malware|ransomware|infostealer|exploit|vulnerab|cve-|zero[- ]day|phish|intrusion|espionage|cyber|backdoor|botnet|leak|exfiltrat|ddos|wiper|heist|stole", re.I)),
    ("influence", "AI influence ops & disinformation", re.compile(r"disinformation|misinformation|propaganda|influence|manipulat|election|ai video|ai-generated (?:video|image)", re.I)),
    ("weapons", "AI in weapons & warfare", re.compile(r"drone|weapon|missile|military|targeting|strike|air defen", re.I)),
]
KIND_LABEL = {k: l for k, l, _ in KINDS}; KIND_LABEL["other"] = "Other AI risk"

def _kind(text):
    for k, _, rx in KINDS:
        if rx.search(text): return k
    return "other"

HASHTAGS = re.compile(r"(?:^|\s)#\s?[\w-]+")
NEAR = 160   # an AI term and a threat term must sit within this many characters of each other, in the same title / brief / post

def _unit(text):
    """One title, brief or post. Hashtag lists (# AI # cybersecurity ...) are dropped: tag spam is not a report."""
    t = HASHTAGS.sub(" ", text or "")
    strong = [m.group(0) for m in STRONG.finditer(t)]
    if strong: return strong
    if NEG.search(t): return None
    ai = [(m.start(), m.group(0)) for r in (AI_CS, AI_CI) for m in r.finditer(t)]
    if not ai: return None
    th = [(m.start(), m.group(0)) for m in THREAT.finditer(t)]
    hits = [w for p, w in th if any(abs(p - q) <= NEAR for q, _ in ai)]
    return [w for _, w in ai] + hits if hits else None

def _snip(text, words, n=220):
    t = re.sub(r"\s+", " ", HASHTAGS.sub(" ", text or "")).strip()
    i = min([j for j in (t.find(w) for w in words) if j >= 0] or [0])
    a = max(0, i - n // 3)
    return ("…" if a else "") + t[a:a + n] + ("…" if a + n < len(t) else "")

def classify_units(units, kind_text=None):
    why, first = [], None
    for u in units:
        w = _unit(u)
        if w:
            why += w
            if first is None: first = (u, w)
    if not why: return None
    kt = kind_text or "\n".join(units)
    if first and first[0] not in kt: kt = kt + "\n" + first[0]
    return {"kind": _kind(kt), "why": list(dict.fromkeys(why)), "match": _snip(first[0], first[1])}

def classify_text(text): return classify_units([text])

def classify(d):
    if NEG.search(d["title"] or "") and not STRONG.search(d["_text"]): return None
    units = [d["title"] or "", d["brief"] or ""] + d["_text"].split("\n")[2:]
    return classify_units(units, (d["title"] or "") + "\n" + (d["brief"] or ""))

# ------------------------------------------------------------------ extra feeds (box)
def _filtered(raw, require_ai=True):
    out = []
    for x in raw:
        txt = x["title"] + "\n" + T.clean(x["summary"], 2000)
        m = classify_text(txt)
        if not m:
            if require_ai: continue
            m = {"kind": _kind(txt), "why": ["AI incident (curated database)"]}
        out.append(dict(x, kind=m["kind"], why=m["why"][:6]))
    return out

def f_aiid():
    raw = T.rss("https://incidentdatabase.ai/rss.xml")
    for x in raw:   # the item links to the news report; the description ends with the AIID citation URL
        m = re.search(r"https://incidentdatabase\.ai/cite/\d+[#\w]*", x["summary"] or "")
        if m: x["extra"] = {"links": [{"source": "AIID citation", "url": m.group(0)}]}
    return _filtered(raw, require_ai=False), f"{len(raw)} in feed; all kept (every entry is a documented AI incident)"
def f_thn():
    raw = T.rss("https://feeds.feedburner.com/TheHackersNews")
    out = _filtered(raw)
    return out, f"{len(raw)} in feed; {len(out)} matched the AI classifier"

FEEDS = {
    "aiid": {"label": "AI Incident Database", "url": "https://incidentdatabase.ai/rss.xml", "fn": f_aiid, "official": False, "category": "AI incident"},
    "thn": {"label": "The Hacker News (AI-filtered)", "url": "https://feeds.feedburner.com/TheHackersNews", "fn": f_thn, "official": False, "category": "cyber"},
}

def handle_get(path, qs):
    if path.startswith("/api/ai/"): return T.serve_static(path[len("/api/ai/"):])
    if path == "/api/ai":
        code, body = T.page(TAB, classify, FEEDS, qs, TITLE)
        if code == 200: body["kinds"] = KIND_LABEL
        return code, body
    return 404, {"error": "not found"}
