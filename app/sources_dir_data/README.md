# Global Sources directory data (blackout.network)

Gzipped NDJSON shards, one row per real reference source: `[sid, name, url, category, kind, country_iso2, registry, detail, link_checked_date?]`.
Built on 2026-10-31 by the box from open downloads (no accounts, $0): ROR data dump (CC0), Wikidata SPARQL (CC0), WMO OSCAR/Surface,
FDSN station web services (EarthScope/IRIS, EIDA nodes, GeoNet, SCEDC, NCEDC, AusPass, Raspberry Shake), CelesTrak SATCAT, NOAA NCEI HOMR
radar list, NOAA NDBC, NOAA CO-OPS, USGS Water Services, EUMETNET OPERA, RIPE Atlas, FIRST.org teams API, Radio Browser and data.europa.eu.
Deduplicated by normalized URL; entries already in the monitored catalog are left out. A random + per-registry sample was link-checked and
dead links removed (see meta.json). These are directory/reference entries only: the scanner does not read them.
The Docker build turns these shards into sources_dir/directory.db (SQLite + FTS5) with `python3 sources_directory.py --build`.
