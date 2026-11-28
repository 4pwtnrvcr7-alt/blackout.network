"""Strict publish gate for social-only Wire rows (Bluesky firehose and Bluesky accounts).

Nov 27 2026 (Matt 11:09-11:10 PM ET): "Lots of BS coming through on Bluesky firehose."  A row whose sources are ALL social
(Bluesky and/or Mastodon) reaches the public Wire only when its text clearly reports a concrete event: an event
word AND a named entity AND a hard detail (CVE id, number, record count...). Replies, opinion, first-person chatter,
questions, trend spam, hashtag spam and short posts are dropped. When unsure, drop. A row that also has a non-social
source (news site, agency feed) is not touched. Nothing is deleted: the row is only hidden from the public Wire.

BN_WIRE_SOCIAL_GATE: "strict" (default) or "hide" (hide every social-only Bluesky row).  There is no "off".
Stateless and cheap; the caller caches the verdict per row.
"""
import json
import os
import re

_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
_URLISH = re.compile(r"https?://\S+|\b(?:www\.)?[a-z0-9-]+\.(?:com|org|net|io|dev|gov|co)\S*", re.I)
_FIRST = re.compile(r"\b(i|i'm|im|i've|i'd|i'll|me|my|mine|myself|we|we're|we've|our|ours|us|you|you're|youre|your|yours|ya|y'all|"
                    r"lol|lmao|lmfao|imo|imho|tbh|omg|wtf|smh|idk|ngl|gonna|wanna|gotta|ain't|aint|dude|folks)\b", re.I)
_OPINION = re.compile(r"\b(ironic|ironically|guess|shouldn't|should have|shouldn't have|don't forget|honestly|literally|apparently|"
                      r"probably|maybe|perhaps|seems like|seems pretty|it seems|pretty clear|so sad|sad that|of course|obviously|clearly|"
                      r"hopefully|imagine|thoughts|opinion|in my|agreed|agree|disagree|exactly|exactly this|bad take|hot take|"
                      r"wake up|sheep|libtard|maga|woke|idiots?|clowns?|stupid|insane|crazy|hellscape|propaganda|billionaires?)\b", re.I)
_DIGEST = re.compile(r"^\s*\d+/\d*\s|\bnews items\b|\b(?:industrial|daily|weekly|morning|evening)\b[^.]{0,25}\bbrief\b|\bweekly\b|\bround-?up\b|\bstory \d\b|\bnews (?:nov|dec|jan|feb)\w*\.? ?\d|daily (?:digest|roundup|recap|briefing)|top stories|"
                     r"headlines (?:today|roundup)|\bnewsletter\b|\bpodcast\b|\bepisode \d|\bthread\b|\bpart \d+/\d+|\b\d+/\d+ ?(?:\U0001F9F5|:)", re.I)
_SPAM = re.compile(r"#trends? today|click/?\s*tap|click here|tap below|follow (?:me|us)|subscribe|giveaway|retweet|\bRT @|#fyp|"
                   r"please provide|the excerpt only|as an ai|latest update for|link in bio|dm me|use code|promo code|free gratis", re.I)

# event families: (name, regex).  A post needs one.
_EVENTS = [
    ("cve", re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)),
    ("cyber", re.compile(r"\b(data breach|breached|breach of|ransomware|cyber ?attack|zero-day|0-day|malware|data leak|leaked|"
                         r"exposed (?:passwords|records|data)|hackers? (?:breached|gained|stole|claim|hit|exploit)|was hacked|were hacked|"
                         r"got hacked|ddos)", re.I)),
    ("quake", re.compile(r"\b(earthquake|quake|tsunami|magnitude|\bM ?\d\.\d)\b|\bM ?\d\.\d\b", re.I)),
    ("attack", re.compile(r"\b(missile|drone|airstrike|air strike|rocket|explosion|explosions|shooting|bombing|attack(?:s|ed)?|"
                          r"strike(?:s)?|intercepted|shelling)\b", re.I)),
    ("outage", re.compile(r"\b(power outage|outage|outages|blackout|grid failure|internet shutdown|offline)\b", re.I)),
    ("disaster", re.compile(r"\b(wildfire|hurricane|tornado|flood(?:ing)?|volcano|eruption|landslide|evacuat\w+|derail\w*|crash(?:ed)?|"
                            r"outbreak|plane crash|collapse[sd]?)\b", re.I)),
]
# a verb that says it HAPPENED (not "could", "might", "if")
_HAPPENED = re.compile(r"\b(confirmed|confirms|reported|reports|announced|issued|issues|hit|hits|struck|killed|injured|dead|died|targets?|targeted|"
                       r"claimed|claims|exposed|leaked|stole|stolen|took|offline|launched|intercepted|detected|disclosed|"
                       r"warning|evacuated|gained access|breached|compromised|hacked|patched|exploited|affected|impacted)\b", re.I)
_HYPO = re.compile(r"\b(could|might|may|would|if|should|can't|cannot|won't|whether|why|how|what if|rumou?r|unconfirmed|probable|possible|potential)\b", re.I)
_NOTENT = {"the", "a", "an", "this", "that", "these", "those", "breaking", "update", "alert", "news", "report", "reports", "today",
           "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
           "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "another", "some",
           "new", "major", "massive", "huge", "big", "just", "now", "and", "but", "for", "with", "from", "after", "during", "its",
           "his", "her", "their", "there", "here", "also", "per", "via", "osint", "cve", "cvss", "cyber", "hack", "hacked",
           "hackers", "hacker", "data", "security", "wordpress", "plugin", "vulnerability", "vulnerabilities", "score", "high",
           "critical", "severe", "warning", "outage", "attack", "missile", "launch", "iranian", "reports", "country", "category",
           "company", "platform", "claimed", "record", "records", "records:", "exposed", "passwords"}

def _mode():
    m = (os.environ.get("BN_WIRE_SOCIAL_GATE") or "strict").strip().lower()
    return "hide" if m == "hide" else "strict"

def social_only(links_raw):
    """True when every source of the row is Bluesky or Mastodon (a post network, not a newsroom or agency feed)."""
    try:
        ls = json.loads(links_raw) if isinstance(links_raw, str) else (links_raw or [])
    except Exception:
        return False
    names = []
    for x in ls:
        if isinstance(x, dict):
            names.append(str(x.get("source") or "").strip().lower())
    if not names:
        return False
    return all(n.startswith("bluesky") or n.startswith("mastodon") for n in names)

def _entities(text):
    t = _URLISH.sub(" ", text)
    out = set()
    for m in re.finditer(r"(?<![#@\w])([A-Z][A-Za-z0-9&.\-']{2,}|[A-Z]{3,})\b", t):
        w = m.group(1)
        if w.lower().strip(".'") in _NOTENT:
            continue
        # skip a capital that only starts a sentence
        s = m.start()
        pre = t[:s].rstrip()
        if (not pre or pre[-1] in ".!:|\n-–—\"“") and w[1:].islower():
            continue
        out.add(w.lower())
    return out

def verdict(text, category=None):
    """(ok, reason) for the text of one social-only row."""
    if _mode() == "hide":
        return False, "hide-all"
    raw = (text or "").strip()
    if (str(category or "").strip().lower() in ("", "other", "unknown", "general", "misc", "uncategorized")):
        return False, "other"
    plain = _URLISH.sub(" ", raw)
    plain = re.sub(r"\s+", " ", plain).strip()
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-./]*", plain)
    if len(plain) < 60 or len(words) < 8:
        return False, "short"
    if raw.startswith(("@", "\"", "“", "'", "‘", ">", "RT ", "Re:")):
        return False, "reply-or-quote"
    if "?" in raw or "？" in raw:
        return False, "question"
    if _DIGEST.search(raw):
        return False, "digest"
    if _SPAM.search(raw):
        return False, "spam"
    if len(re.findall(r"#\w+", raw)) >= 4:
        return False, "hashtag-spam"
    letters = [c for c in plain if c.isalpha()]
    if letters and sum(1 for c in letters if ord(c) < 128) < 0.9 * len(letters):
        return False, "non-english"
    if letters and sum(1 for c in letters if c.isupper()) > 0.45 * len(letters):
        return False, "caps"
    if _FIRST.search(plain):
        return False, "first-person"
    if _OPINION.search(plain):
        return False, "opinion"
    ev = [n for n, rx in _EVENTS if rx.search(raw)]
    if not ev:
        return False, "no-event"
    cve = bool(_CVE.search(raw))
    if not cve and _HYPO.search(plain):
        return False, "hypothetical"
    if not cve and not _HAPPENED.search(plain):
        return False, "no-happened-verb"
    ents = _entities(raw)
    if not cve and not ents:
        return False, "no-entity"
    detail = cve or bool(re.search(r"\d", plain))
    if not detail and len(ents) < 2:
        return False, "no-detail"
    return True, "ok"

def junk_row(title, category, links_raw):
    """True when the row must stay off the public Wire."""
    if not social_only(links_raw):
        return False
    return not verdict(title, category)[0]
