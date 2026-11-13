"""Pre-send QA gate for newsletter issues (t1134).

The live 7 AM Nov 9 brief went out with every ANALYSIS lead cut mid-sentence ("...around the strait even"). This gate reads the
rendered email the way a reader does and blocks a live send when any headline or lead looks cut:

  * a bold ANALYSIS lead / subhead that does not end in terminal punctuation
  * any headline, lead or labelled paragraph that ends on a dangling word ("even", "of", "the", "busiest", ...)
  * any rendered headline/lead that is a strict prefix of a longer source string (analyst note) with no ellipsis
  * labelled body paragraphs (WHAT HAPPENED, ANALYSIS, TRAJECTORY, CONFIDENCE, WHAT TO DO) that stop without punctuation
  * plain-text part lines with the same problems

Visible ellipsis cuts ("...") are reported as warnings, not blockers: the reader can see the text was shortened.
check(subject, html, text, sources) -> {"ok": bool, "blockers": [...], "warnings": [...]}. Pure function, no I/O.
"""
import re, html as _html

DANGLING = set("""a an the of and or but nor to in on at for with from as by into onto over under after before amid
 its their his her our your my this that these those which who whom whose than then even if when while because
 so such very more most less least about around across between among against toward towards via per
 is are was were be been being has have had will would can could should may might must do does did
 not no only also just still yet both either neither each every some any all many much few several""".split())
SUPERLATIVE = re.compile(r"(?:iest|(?<!\b[bwr])est)$")   # busiest, largest, biggest ... but not best/west/rest
_ABBR_END = re.compile(r"(?:\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Mr|Mrs|Ms|Dr|St|Sen|Rep|Gov|Gen|Jr|Sr|No|vs)|\b(?:[A-Z]\.){1,3}[A-Z]?)$")
TERMINAL = tuple(".!?\u2026\"'\u201d\u2019)")
LABELS = ("WHAT HAPPENED", "ANALYSIS", "TRAJECTORY", "CONFIDENCE", "WHAT TO DO")
SUPERLATIVE_OK = set("best west rest test guest interest forest protest contest arrest request harvest honest modest manifest suggest".split())


def _txt(fragment):
    t = re.sub(r"<br\s*/?>", " ", fragment or "", flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", _html.unescape(t)).strip()


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _last_word(s):
    w = re.findall(r"[A-Za-z0-9'\u2019-]+", s or "")
    return w[-1].lower().strip("'\u2019-") if w else ""


def _dangling(s):
    s = (s or "").rstrip()
    if not s or s.endswith(("\u2026", "...")): return None
    if s.endswith(TERMINAL) and not re.search(r"\b(?:a|an|the|of|and|or|to|with|for|from)[.!?]$", s, re.I):
        return None   # a punctuated sentence may end on "in" / "yet" / "be"; only a cut one cannot
    core = s.rstrip(".!?\"'\u201d\u2019)")
    lw = _last_word(core)
    if not lw: return None
    if lw in DANGLING: return lw
    if SUPERLATIVE.search(lw) and lw not in SUPERLATIVE_OK and len(lw) > 4: return lw
    return None


def _prefix_of(shown, sources):
    """shown is a strict, cut-short prefix of some longer source string (and does not say so with an ellipsis)."""
    if not shown or shown.rstrip().endswith(("\u2026", "...")): return None
    if shown.rstrip().endswith(TERMINAL[:3]): return None   # a whole sentence that opens a longer text is not a cut
    a = _norm(shown)
    if len(a) < 12: return None
    lead = re.sub(r"\s+", " ", shown).strip().lower()
    for src in sources or ():
        b = _norm(src)
        if len(b) > len(a) + 2 and b.startswith(a + " "):
            raw = re.sub(r"\s+", " ", str(src)).strip()
            # Nov 13: a headline that is the source's whole first sentence minus its full stop ("... between London and Paris"
            # from "... between London and Paris. French authorities ...") is not a cut.
            if raw.lower().startswith(lead) and raw[len(lead):len(lead) + 1] in (".", "!", "?"):
                continue
            return src
    return None


def extract(html_):
    """Pull what a reader sees as headlines, leads and labelled paragraphs out of the rendered HTML."""
    h = html_ or ""
    heads = [_txt(m.group(1)) for m in re.finditer(r'<a\s[^>]*class="bnt bnh1"[^>]*>(.*?)</a>', h, re.S)]
    # layout v2 (round 2): headlines are plain text (the tappable link sits right-aligned under the story), marked data-bn-h
    heads += [_txt(m.group(1)) for m in re.finditer(r'<div\s[^>]*class="bnt bnh1"[^>]*data-bn-h="1"[^>]*>(.*?)</div>', h, re.S)]
    heads = [re.sub(r"^\d+\.\s*", "", x) for x in heads if x]
    tops = [re.sub(r"^\d+\.\s*", "", _txt(m.group(1))) for m in re.finditer(r'<b style="font-weight:700">(\d+\..*?)</b>', h, re.S)]
    deks = [_txt(m.group(1)) for m in re.finditer(r'<b style="display:block;[^"]*">(.*?)</b>', h, re.S)]
    labelled = []
    for m in re.finditer(r'<span style="display:block;[^"]*">([A-Z][A-Z &]+)</span>(.*?)</p>', h, re.S):
        lab = m.group(1).strip()
        if lab in LABELS:
            body = re.sub(r'<b style="display:block;[^"]*">.*?</b>', "", m.group(2), flags=re.S)
            labelled.append((lab, _txt(body)))
    return {"headlines": heads, "top": tops, "deks": deks, "labelled": labelled}


def check(subject, html_, text="", sources=(), title_sources=None):
    B, W = [], []
    ex = extract(html_)
    src = [s for s in (sources or ()) if isinstance(s, str) and s.strip()]
    tsrc = src if title_sources is None else [s for s in title_sources if isinstance(s, str) and s.strip()]
    for kind, items in (("headline", ex["headlines"]), ("top-3 headline", ex["top"])):
        for t in items:
            d = _dangling(t)
            if d: B.append(f"{kind} ends on dangling word '{d}': {t!r}")
            p = _prefix_of(t, tsrc)
            if p: B.append(f"{kind} is a cut-short prefix of {p[:120]!r}: {t!r}")
            if t.endswith("\u2026"): W.append(f"{kind} shortened with a visible ellipsis: {t!r}")
    for t in ex["deks"]:
        if not t.endswith(TERMINAL): B.append(f"ANALYSIS lead has no terminal punctuation: {t!r}")
        d = _dangling(t)
        if d: B.append(f"ANALYSIS lead ends on dangling word '{d}': {t!r}")
        p = _prefix_of(t, src)
        if p: B.append(f"ANALYSIS lead is a cut-short prefix of {p[:120]!r}: {t!r}")
    for lab, t in ex["labelled"]:
        if not t: B.append(f"{lab} paragraph is empty"); continue
        tail = re.sub(r"\s*Guide:.*$", "", t) if lab == "WHAT TO DO" else t
        if not tail.rstrip().endswith(TERMINAL) and not _ABBR_END.search(tail.rstrip()):
            B.append(f"{lab} paragraph ends without punctuation: ...{tail[-90:]!r}")
        d = _dangling(tail)
        if d: B.append(f"{lab} paragraph ends on dangling word '{d}': ...{tail[-90:]!r}")
    s = (subject or "").strip()
    core = re.sub(r"\s*\+\s*\d+\s+more$", "", s)
    d = _dangling(core)
    if d: B.append(f"subject ends on dangling word '{d}': {s!r}")
    if "\u2026" in core: W.append(f"subject shortened with a visible ellipsis: {s!r}")
    for ln in (text or "").splitlines():
        L = ln.strip()
        m = re.match(r"^(TRAJECTORY|WHAT HAPPENED|WHAT TO DO):\s*(.*)$", L)
        if m:
            body = re.sub(r"\s*Guide:.*$", "", m.group(2))
            if body and not body.endswith(TERMINAL): B.append(f"text part {m.group(1)} line ends without punctuation: ...{body[-90:]!r}")
            dd = _dangling(body)
            if dd: B.append(f"text part {m.group(1)} line ends on dangling word '{dd}': ...{body[-90:]!r}")
    seen = set(ex["headlines"] + ex["top"] + ex["deks"] + [t for _, t in ex["labelled"]])
    body = re.sub(r"(?is)<(style|script|head)[^>]*>.*?</\1>", " ", html_ or "")
    for blk in re.split(r"(?i)</?(?:p|div|td|li|h[1-6]|tr|table|br)[^>]*>", body):
        t = _txt(blk)
        if len(t) < 25 or t in seen or len(t.split()) < 8: continue   # short blocks are headings and labels
        p = _prefix_of(t, src)
        if p: B.append(f"text block is a cut-short prefix of {p[:120]!r}: {t[-120:]!r}")
        elif not re.search(r"[.!?\u2026:)\"\u201d]$", t):
            d = _dangling(t)
            if d: W.append(f"text block ends on '{d}' with no punctuation (check): ...{t[-100:]!r}")
    if not ex["headlines"]: W.append("no story headlines found in HTML (layout changed? gate could not read cards)")
    try:
        import story_gates as SG
        for kind, items in (("headline", ex["headlines"]), ("top-3 headline", ex["top"])):
            for t in items:
                if t and not SG.is_english_headline(t):
                    B.append(f"{kind} is not English (translate or drop): {t!r}")
                if t and SG.is_hard_blocked({"title": t}):
                    B.append(f"{kind} is a hard-blocked story (French SMIC / minimum wage): {t!r}")
        for lab, t in ex["labelled"]:
            lab_u = (lab or "").upper()
            if lab_u in ("WHAT HAPPENED", "ANALYSIS") and t:
                what = t if lab_u == "WHAT HAPPENED" else ""
                anal = t if lab_u == "ANALYSIS" else ""
                if SG.is_template_filler(what, anal, ""):
                    B.append(f"{lab} is template filler (restates headline or rank, no real facts): ...{t[:140]!r}")
        body_txt = text or ""
        if SG.is_hard_blocked({"title": body_txt, "body": body_txt}):
            B.append("hard-blocked French SMIC / minimum-wage story appears in the text part")
        for ln in body_txt.splitlines():
            L = ln.strip()
            if L.startswith("WHAT HAPPENED:") and SG.is_template_filler(L.split(":", 1)[-1], "", ""):
                B.append(f"text part WHAT HAPPENED is template filler: ...{L[15:140]!r}")
            if L.lower().startswith("analysis:") and SG.is_template_filler("", L.split(":", 1)[-1], ""):
                B.append(f"text part Analysis is template filler: ...{L[9:140]!r}")
            m = re.match(r"^\d+\.\s+\[.*?\]\s+(.*)$", L)
            if m and not SG.is_english_headline(m.group(1)):
                B.append(f"text part headline is not English (translate or drop): {m.group(1)!r}")
    except Exception as err:
        W.append(f"story_gates QA check skipped: {type(err).__name__}: {err}"[:200])
    return {"ok": not B, "blockers": B, "warnings": W, "counts": {k: len(v) for k, v in ex.items()}}


def duplicate_events(issue):
    """NL-DEDUPE-2 (Matt, Nov 13 2026): blockers for any two items in one issue that share a cluster/story id or match the
    same-event heuristic (event_dedupe.same_event). newsletter.merge_same_event() folds these before layout, so a hit here
    means the merge missed one and the issue must not go out as is."""
    import newsletter as N
    out = []
    for sa, a, sb, b, why in N.same_event_pairs(issue):
        ta = (a.get("display_title") or a.get("title") or "")[:90]; tb = (b.get("display_title") or b.get("title") or "")[:90]
        out.append(f"duplicate event ({why}): {sa} {a.get('cluster_id')} {ta!r} and {sb} {b.get('cluster_id')} {tb!r}")
    return out


def titles_from_issue(issue):
    """Full headline strings only (analyst headline, raw title): a card headline is compared with these, not with body text."""
    out = []
    for key in ("main", "updates", "follow", "politics", "notable", "developing", "watchlist"):
        for it in issue.get(key) or []:
            for f in ("display_title", "title"):
                if it.get(f): out.append(str(it[f]))
    return out


def sources_from_issue(issue):
    """Full source strings the renderer had: analyst headlines, takeaways, why-it-matters, raw titles."""
    out = []
    for key in ("main", "updates", "follow", "politics", "notable", "developing", "watchlist"):
        for it in issue.get(key) or []:
            for f in ("display_title", "title", "why"):
                if it.get(f): out.append(str(it[f]))
            a = it.get("analyst") or {}
            for f in ("takeaway", "analysis", "outlook", "what"):
                if a.get(f): out.append(str(a[f]))
    for a in ((issue.get("analysis") or {}).get("items") or []):
        for f in ("takeaway", "analysis", "outlook", "what", "title"):
            if a.get(f): out.append(str(a[f]))
    return out
