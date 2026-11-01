# scanner_addon_sources/

Backup copy of the Blackout Network box scanner's add-on source files (t238, 2026-10-31; updated t248).

- `sources_ext.py` — the scanner's add-on/extended sources module (`EXT_SOURCES`), including the four sources activated on 2026-10-31: Chile CSN (sismologia.cl, M4.0+), CERT-EU security advisories RSS, JPCERT/CC English alerts RSS, Canadian Centre for Cyber Security alerts & advisories RSS.
- t248 (2026-10-31): six directory-slice sources vetted in t238 and approved by Matt: EMSC FDSN events (M4.5+), GFZ GEOFON RSS (M4.5+), INGV FDSN events (M3+), USGS HANS elevated volcanoes (level changes only; state file `hans_state.json` lives on the box, not here), IODA country/region internet outages (filtered), MeteoAlarm Severe/Extreme warnings.
- `source_candidates.json` — the candidate source list (CENAPRED marked failed vetting: bot-check page, no feed).

The live scanner runs on the box (`/workspace/blackout`) and syncs results to this site. These files are **not** used by the Render web node: the Dockerfile only copies `app/`, so this folder has no runtime effect. Contains no secrets or keys.

t414 (2026-11-01): +9 approved sources (JTWC, AFAD, PAGASA, CERT-FR, UKHSA, Geoscience Australia, Taiwan CWA, NCSC-NL, HKCERT); ReliefWeb API v2 skipped (needs an approved appname; RSS stays). scanner_freshness.py = box watchdog (stale if no scan within 2x interval or a source failing 6h+), writes sources_freshness.json + logs/scanner_freshness.json.
t414b: +5 (NOAA SPC, CDC travel notices, Copernicus EMS, WOAH, InciWeb wildfires-only).
