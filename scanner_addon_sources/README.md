# scanner_addon_sources/

Backup copy of the Blackout Network box scanner's add-on source files (t238, 2026-10-31).

- `sources_ext.py` — the scanner's add-on/extended sources module (`EXT_SOURCES`), including the four sources activated on 2026-10-31: Chile CSN (sismologia.cl, M4.0+), CERT-EU security advisories RSS, JPCERT/CC English alerts RSS, Canadian Centre for Cyber Security alerts & advisories RSS.
- `source_candidates.json` — the candidate source list (CENAPRED marked failed vetting: bot-check page, no feed).

The live scanner runs on the box (`/workspace/blackout`) and syncs results to this site. These files are **not** used by the Render web node: the Dockerfile only copies `app/`, so this folder has no runtime effect. Contains no secrets or keys.
