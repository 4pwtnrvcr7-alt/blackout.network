# Wire band data (design v3)

Two small files feed the bands at the top of The Wire. Edit them on the box (`/workspace/blackout/data/`); the sync push
(`render_rules.SYNC_JSON`) carries them to the public site, no deploy needed. If a file is missing, broken or has no valid
entries, its band is simply not shown. Nothing is ever filled in automatically.

## data/top_of_mind.json (up to 4 cards)
```json
{"updated": "2026-11-02T13:00:00Z",
 "cards": [{"id": "war", "title": "The war", "category": "war",
            "status": "One-line status", "latest": "The latest development", "why": "Why it matters now",
            "as_of": "2026-11-02T13:00:00Z", "level": "elevated",
            "source": {"name": "Reuters", "url": "https://..."}, "sources": [{"name": "AP", "url": "https://..."}],
            "link": "/midterms"}]}
```
Required per card: `title`, `status`, `latest`, `why`, `as_of` (ISO time) and at least one source with a `name` and an
http(s) `url`. `category`: war/conflict, unrest/migration, elections, economy (sets the illustration and accent).
`level` (optional): low, elevated, high, critical (high and critical add the red rank-7+ dot). `link` (optional) must be a
path on this site. A card older than 96 hours (`BN_TOM_MAX_AGE_H`) is hidden as stale. Keep it neutral and sourced.

## data/whats_coming.json (dated items, today to +14 days)
```json
{"updated": "2026-11-02T13:00:00Z",
 "items": [{"date": "2026-11-06", "time": "8:30 AM ET", "title": "Jobs report (October)", "detail": "",
            "category": "economy", "kind": "event", "source": {"name": "BLS", "url": "https://www.bls.gov/..."},
            "link": "/midterms"}]}
```
Required per item: `date` (YYYY-MM-DD, Eastern), `title`, and a source with an http(s) `url`. `kind`: event or hazard.
Items before today or more than 14 days out are skipped automatically, so future items can be added early.
