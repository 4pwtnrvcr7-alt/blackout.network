# Meshtastic integration: pre-publish check (blackout-network-pre-publish-check)

Scope: /mesh, /mesh/chat, /mesh/guide, the Energy Grid "Mesh network drop-offs" card, and the Push to Mesh share button and modal.
Screenshots (390 and 1440, dark and light, plus iOS 390): /workspace/launch/team/review/meshtastic/shots/ (26 PNGs).

## A. Images and frames: PASS
- The only imagery is map tiles: OpenFreeMap dark and positron through MapLibre 5.24.0 with SRI, the same as the Crime page. No OSM tile servers are used, and attribution is shown.
- No generated images, logos or radio photos. The icons are inline SVG.
- 0 px horizontal overflow and no page errors at 390 or 1440 in either theme.
- Light-mode yellow text is recolored to ink, and pressed segments to #FFC21A, by bn-apple.js's contrast fixer. That is site-wide house behavior, so it was accepted.
- Screenshots of chat and Push to Mesh use a **QA MOCK RADIO** labeled on screen. No device was connected and nothing was transmitted. The mock only activates through window.__BN_MESH_MOCK, which no production page sets.

## B. Text: PASS
- No emojis in the new pages. The menu entry uses the same emoji-to-icon conversion (bn-icons) as the other menu items.
- Owner's name absent. No banned or placeholder words (TODO, lorem, undefined, NaN).
- Drop-off signals are labeled single-source, watchlist, unconfirmed. The rank is capped at 5 in both the collector and the API, and they never auto-raise to high severity.
- A stale feed (over 20 minutes old) or a global outage of the feed itself (30% or more of the world silent) produces no signals and shows a "feed stale" note.
- The guide cites meshtastic.org for every section and includes the full trademark statement plus "We do not sell radios or use affiliate links." The footer carries the trademark and non-affiliation note.
- Legal text covers US 915 MHz under unlicensed Part 15, and ham mode under Part 97 (no encryption, call-sign ID). It is informational, not legal advice.
- Chat states its support limits: Chrome or Edge on desktop or Android, with Web Bluetooth or Web Serial. iOS Safari is not supported; those users are pointed to the official app.
- Push to Mesh states "BLACKOUT.NETWORK never sends anything to the mesh" and requires a preview and an explicit Send.

## C. Links: PASS
All 33 external URLs on the new pages, scripts and docs returned 200 on 2026-11-12, around 1:40 AM ET. They cover:
- meshtastic.org docs (19 pages);
- client.meshtastic.org and flasher.meshtastic.org;
- the App Store (id1586432531) and Google Play (com.geeksville.mesh);
- github.com/meshtastic/js, meshmap.net, openfreemap.org, openmaptiles.org and openstreetmap.org/copyright;
- unpkg and jsdelivr (MapLibre).

The one non-200 was keestalkstech.com, an author URL inside a bundled library's license comment that is never shown to users.

The app deep links follow the official docs: `meshtastic:///messages` (iOS, opens the app with no text) and `meshtastic://meshtastic/share?message=` (Android). The undocumented iOS text scheme was not invented.

## Privacy
- Map nodes are reduced to 2-decimal coordinates, role, hardware type, minutes since last heard, and a short name of at most 4 ASCII characters. No node IDs and no long names.
- The collector state stores only salted hashes plus activity bits.
- Chat is kept in browser memory only (200 messages at most). There is no export and no server storage. The optional public feed is OFF; if enabled, it masks emails and phone numbers and shows senders as "!xxxx".

## Tests
- 32 tests pass (test_meshnet: 12, test_signal_map, test_story_report), run in a throwaway server copy.
- py_compile and `node --check` are clean on all new and edited files.
