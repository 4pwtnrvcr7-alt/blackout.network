# Water treatment status tracker (/water), preview

Preview branch only. Not routed in the menu, `noindex`. Read-only, keyless, no paid API, no new Render service.

| Layer | Source | Cost / key | Location | Refresh |
|---|---|---|---|---|
| Boil / do-not-drink notices (AK) | Alaska DEC "Boil Water and Do Not Drink Notice – Open" ArcGIS layer (`dec.alaska.gov/arcgis/rest/services/EH/BWN_DND`) | free, no key | agency point | 10 min cache |
| Boil advisories (MB) | Government of Manitoba, Current BWAPWS + Current BWA SPWS ArcGIS layers (OpenMB licence) | free, no key | agency point | 10 min |
| Boil advisories (NL) | Government of Newfoundland and Labrador, Boil Advisories ArcGIS layer | free, no key | agency point | 10 min |
| Health-based violations, U.S. systems over 3,300 people | EPA ECHO SDWA REST services (`echodata.epa.gov/echo/sdw_rest_services`, SDWIS data) | free, no key | county centre (U.S. Census Gazetteer 2023, public domain); labelled as such | 6 h |
| Sewage plants in significant noncompliance (8+ of 12 quarters) | EPA ECHO CWA REST services (ICIS-NPDES), SIC 4952, major permits | free, no key | EPA plant coordinates | 6 h |
| News reports | Google News RSS (two queries, last 5 days, keyword-gated) | free, no key | not pinned (no reliable place) | 20 min |

Every item carries a link to its record (ArcGIS record page, ECHO detailed facility report, or the article).
A source that fails keeps its last good copy and is shown as unavailable. Nothing is estimated or filled in.

Refresh: `GET /api/water/data?fresh=1` re-pulls every source older than 60 s, in parallel, and the response lists which sources were pulled;
a tap inside the 60 s floor says "Already current".

Considered, not used: Indigenous Services Canada short-term advisories (HTML table, no coordinates), Texas TCEQ boil-water list (blocked from the box),
GDELT (rate-limited to one request per 5 s), municipal ArcGIS boil layers (hundreds of separate utilities, each needing its own vetting),
EPA SDWIS/Envirofacts VIOLATION table (no coordinates; ECHO returns the same systems with county FIPS).

Rollback: nothing is deployed from this branch. Closing the PR and deleting the branch removes it. No stored state, no localStorage keys, no new env vars.
Tests: `python3 app/tests/test_water.py`. Rebuild centroids: `python3 tools/build_county_centroids.py`.
