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

Share (Nov 28 2026): each item has a permalink at `/water/<id>` and the standard Wire/growth action set (Post on X, Copy link, native share, source link, permalink). Hashtags come from `x_share` (3-5 short popular tags plus place/entity names; never #News or #BlackoutNetwork). The share preview is a typographic `/og/share/water/<id>.png` card — no map or satellite image. The page itself has the same share row and the site Follow band. `og.VERSION` is unchanged.


## Grid Water layer (Nov 28 2026)

`/water` permanently redirects (301) to `/grid/water`. `/water/<id>` redirects to `/grid/water/<id>`, which opens The Grid with the Water layer and panel, scrolls to that item, and keeps the typographic share card at `/og/share/water/<id>.png`.

The Water panel reuses the site share set (Post on X, Copy link, native share, Source, Permalink, Follow). Buttons are pills. No yellow except the shared #293 Refresh fill on The Grid.

### Plant inventory (worldwide) and how it is served

Sources, each row cites its own:
- U.S.: EPA ECHO / Facility Registry Service, active SIC 4941 (water supply) and SIC 4952 (sewerage), EPA coordinates; U.S. territories carry their own country code.
- Canada: Environment and Climate Change Canada WSER reported data (Open Government Licence - Canada). The point is the reported final discharge point, and the row says so.
- Australia: Geoscience Australia National Wastewater Treatment Facilities 2026 (CC BY 4.0).
- Everywhere else, and gap fill in all of the above: OpenStreetMap `man_made=water_works` / `wastewater_plant` (ODbL), from Geofabrik country and U.S. state extracts (nodes and ways; multipolygon relations are skipped). Authoritative rows win; an OSM plant within 400 m (1.5 km in Canada) of an authoritative one is dropped.
- EEA Waterbase UWWTD (CC BY 4.0) is supported by the builder but `sdi.eea.europa.eu` is not reachable from the build box, so EU coverage is OSM only in this build.

Plant coordinates are never estimated; a system without a published point is not drawn as a plant.

Delivery: the inventory is one read-only SQLite file shipped as zipped base64 parts (`water.db.b64.N`, the same pattern as `gridtiles.b64.N`). `app/waterdb.py` decodes it once to a temp file and opens it `mode=ro&immutable=1`; requests read only the pages for their viewport.
- `/api/netmap/water?w&s&e&n&z` returns precomputed clusters below zoom 9 and up to 2,500 points at zoom 9+, with an LRU of encoded responses.
- `/api/water/item?id=` returns one decorated plant or advisory (permalink, Post on X, tags).
- `/api/water/map` is the slim advisory dot feed; `/api/water/data?limit=30&offset=N` pages the panel list, most severe first.

Rebuild: `tools/fetch_water_national.py` (Canada, Australia), Geofabrik extraction into the cache, then `tools/build_water_db.py --ship app/netmap_static`. Coverage is written to `docs/water-plants-coverage.md`.

Advisories (boil water, do not drink, compliance) come only from the live feeds — never invented.

The typographic Grid loader weights (`W8`) are unchanged. Nothing from the Water layer loads until the Water chip is on or `/grid/water[/id]` is opened.
