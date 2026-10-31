blackout.network: Games tab (served by ../games.py at /api/games/*)

All 26 games, the engine, the pixel art and the sound effects in this folder were written from scratch for this
dashboard (Oct 31, 2026). No third-party code, sprites, fonts, music, ROMs or emulators are used, and nothing
is loaded from a CDN. Pixel art is drawn in code with a PICO-8-like 16-color palette. Sounds are synthesized
live with the browser's Web Audio API (oscillators and filtered noise), so there are no audio files.
Game names are generic. Each game's card notes the classic that inspired it. Those titles are trademarks of their
owners, are used only descriptively, and this project has no affiliation with them.

Files
  engine.js      shared runtime: canvas scaling, 3x5 pixel font, sprites, WebAudio SFX, mute, start/pause/game-over
                 screens, localStorage high scores and best times, keyboard capture and release, one game at a time
  g_*.js         one file per game; each calls BNG.register({...})
  app.js/app.css Games tab UI: grid of cards with live canvas thumbnails, search box and category chips, player panel
games.py serves app.js, app.css and bundle.js (engine.js plus every g_*.js, concatenated).
Data saved: browser localStorage only (keys starting with bn_games_). Nothing is sent to any server.
