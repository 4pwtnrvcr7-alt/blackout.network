# Story brief writer — v3 narrative fields

BLACKOUT.NETWORK hourly “Story brief writer” routine
Last updated: 17 Nov 2026, America/New_York

This spec extends the existing desk brief, it does not replace it. The v2 fields
(`headline`, `what_happened`, `why_it_matters`, `analysis`, `rank_why`, `risk`,
`risk_why`, `if_true`, `if_false`, `what_to_do`, `confidence`, `confidence_why`,
`sources`, `written_at`) stay required so older pages and the newsletter gate
keep working. When Story v3 is on (`BN_STORY_V3=1`), `/wire/<cluster_id>` also
reads an optional `story` object and renders a full narrative page.

Edit only `/workspace/launch/story_reports/desk/briefs.json` (back it up first).
The box builder (`tools/story_reports/build.py`) copies `story` through into
`data/story_reports.json`. Do not push that file yourself.

## Research rules (unchanged, non-negotiable)

1. Open our story page and the cited source articles. Read the article text.
   Never write from headlines alone.
2. Every fact and number must appear in a source listed in `sources` (or in
   `story.sources`). No invented numbers, quotes, dates or figures. Attribute
   claims (“WHO said…”, “Barr said…”). Single-source claims are labelled as
   coming from that source, not as independently confirmed.
3. Word rules: never “verified”, “first” as a boast, “before the news”,
   “BREAKING”, hype or scare words. Use “sourced”. Political items stay
   strictly neutral. No anniversary / “today in history” framing. Never name
   the site owner. No internal notes. No scoring jargon in any prose field
   (no “severity 65/100”, “rank 7/10”, “item(s)”, “source family”).
4. If the material is thin, say so honestly (“we have only this WHO notice”;
   “we have not yet written the background”). Do not pad with general knowledge
   that is not in the cited sources.
5. Average reader, human prose. A full v3 story is longer than a v2 brief:
   about 600–1,000 words across the four sections, not the old 250–350 total.

## New optional object: `story`

```json
"story": {
  "headline": "One plain sentence with the key fact (page H1). Under about 140 characters. No hype.",
  "dek": "One or two short sentences under the headline. Adds something the headline does not already say.",
  "written_at": "2026-11-17T21:40:00Z",
  "hero": {
    "image": "/wire2/static/img/sv3_<slug>_hero.webp",
    "image_mobile": "/wire2/static/img/sv3_<slug>_hero_m.webp",
    "video": "/wire2/static/vid/sv3_<slug>_hero.mp4",
    "alt": "Honest description of what the image actually shows."
  },
  "sections": {
    "happened": "Narrative of what happened, with dates, names, places and attribution. Several short paragraphs, separated by blank lines.",
    "background": "History of the topic, only from cited sources. How we got here. What the disease, storm, legal instrument or market actually is.",
    "analysis": "Why it matters, blast radius, spread and confirmation. Whether we agree with the scanner rank, in plain language. Never scoring jargon.",
    "watch": "What would change the picture next, as signposts, not predictions stated as fact. Practical guidance for an ordinary reader when there is any."
  },
  "images": [
    {
      "src": "/wire2/static/img/sv3_<slug>_hero.webp",
      "alt": "Honest alt text.",
      "role": "hero",
      "credit_id": "short-id-for-/credits"
    }
  ],
  "sources": [
    {"url": "https://official.example/report", "label": "WHO Disease Outbreak News, 13 Nov 2026"}
  ]
}
```

- `written_at` is UTC ISO. The builder still drops briefs older than 21 days and
  re-queues ones older than 24 hours when new reports arrive — rewrite `story`
  in the same pass as the v2 fields.
- `hero.video` is optional. Phones, and `prefers-reduced-motion`, always use the
  still. Never ship a video without a still.
- `hero` may be omitted. The page then falls back to the existing Wire catalogue
  image for that category, which is often illustrative, not this event.
- If `story` or a section is missing, the page falls back to the v2 fields
  (`what_happened`, `why_it_matters`, `analysis`, `if_true` / `if_false` /
  `what_to_do`). It will not invent a background section.

## What each section must contain

**Headline and dek.** The headline is a sentence, not a scanner title
(“Middle East respiratory syndrome (MERS) – Qatar” is a label, not a story).
The dek is the bottom line in plain language.

**What happened.** A chronological narrative with dates. Who, what, where,
when, and who said so. Include the inconvenient details (a first test that was
negative, a landfall window that is still wide, a figure that is only current
as of a given day).

**Background and history.** What this thing is, and how we got here, from
cited sources only: first identification, fatality figures with their caveats,
prior storms this month, earlier outbreaks of the same virus, the difference
between Bundibugyo and Zaire ebolavirus, and so on. If you cannot source the
history, omit the section and say in analysis that the background is still
thin.

**Our analysis.** Why it matters; who is in the blast radius; whether the
story is spreading or confirmed; whether we think the scanner over- or
under-ranked it, in prose (“we think a 7 over-ranks this, because the
patients recovered and there was no spread”), not as a formula. Separate a
regional emergency from the risk to a general reader in the United States
when that is the honest read.

**What to watch next.** Signposts (a follow-up WHO notice, an IMD upgrade,
new Fed guidance), plus practical advice. Start with “No action is needed in
the United States” when that is true.

## Images

- Public domain or Creative Commons, or an original diagram or map we made.
  U.S. government work (CDC, NIAID, NASA, NOAA, USGS, Federal Reserve
  publications) is public domain. Log every asset in
  `/workspace/previews/story_v3/IMAGE_LEDGER.md` and on `/credits#stories`.
- Never put a credit, “illustrative”, or source line on the image itself.
  Credits live only on `/credits`.
- Never fabricate imagery of real events: no invented photographs of patients,
  wreckage, landfall, or officials. A laboratory micrograph, a satellite image
  of this storm, or an original diagram from cited coordinates is honest. An
  ISS photo of a different hurricane passed off as this one is not — if you
  must use a same-kind image, it does not belong in `story.hero` (the older
  Wire catalogue already handles illustrative fallbacks).
- Grade or crop a licensed still if needed for the dark theme; say so on
  `/credits` (“graded monochrome for this page”).
- Do not repeat the same image on two stories, or twice on one page.
- Hero stills: 1920×1080 desktop, 720×1280 phone. Looping desktop video, if
  any, is a short muted Ken Burns of that still, or licensed footage of the
  same subject.

## Workflow

1. Back up: `cp briefs.json briefs.json.bak_$(date -u +%Y%m%dT%H%MZ)`.
2. Read `needs_brief.json`. Newsletter stories first, then highest rank.
   For v3, also rewrite the current top stories so each has a full `story`
   block, not only a v2 brief.
3. Research, then edit with a script that loads, updates and re-dumps JSON
   (`json.dump(..., ensure_ascii=False, indent=1)`).
4. Validate: `python3 -c "import json; json.load(open('briefs.json'))"`.
5. Do not push. The story_reports loop builds and pushes. Do not touch the
   scanner, `push.py`, `blackout.db` (except `mode=ro` reads), newsletter
   templates, the shared header, or the posting timer.

## Flag and preview

- Production stays off until Matt approves a push with `BN_STORY_V3=1`.
- Local preview: `/workspace/previews/story_v3/preview_server.py`
  (http://127.0.0.1:8763/wire/<id>, add `?v3=0` for the previous card).
