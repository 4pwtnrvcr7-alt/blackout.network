# Rollback — fix/20261110-home-stats-food-labels

Branch is based on `release/2026-11-09-trajpunct` (`b206547`). Do not force-push. One deploy per hour.

## Revert the site deploy
```
git checkout release/2026-11-09-trajpunct
# or: git revert <merge-or-tip-of-this-branch>
```
Then follow the usual BLACKOUT.NETWORK deploy checklist (backup first, one push).

## What this branch changes (all display/site-side)
- `app/story_display.py` — new display-time post-filter (category override, entertainment hide flag, WHERE headline fallback). Does not write the DB.
- Hooks in `app/server.py` (`clusters_out`, `/api/state` geo), `app/story.py` (`load`), `app/home_feed.py` (`row_ok`).
- Food card: `app/unrest_feeds.py` (`is_food`, `FOOD_Q`, GDELT food query, world-RSS copy as food candidates) and `app/apple_v1.py` (`UF.combine` like Civil unrest).
- Mobile Settings: `app/static/sitenav.js` / `sitenav.css` / `bn-apple.css` — close menu with `{noHist:true}`, portal `#bn_settings` to `document.body`, raise z-index while open.
- Menu “Top of The Wire”: `app/static/bn-v3.js` fills from `/api/apple/home` with an 8s timeout, then `/api/state`, then a non-loading fallback.
- Tests under `app/tests/test_story_display.py` and extensions to `test_home_feed.py`, `test_wire_groups.py`, `test_unrest_feeds.py`.

## What this branch does not change
- `scanner.py`, `push.py`, `jets.py`, `config.json`, `aviation_watch.py`, posting loops (`lean_post_timer`, `run_hour`).
- No DELETE of wire/cluster rows. Entertainment items are filtered from display only.
- No change to live Render from this box. The branch must be pushed by CoS after review.
- Public `/stats` is stale because `public_stats_loop` and `render_sync` stopped after the Nov 8 restore. Restarting `public_stats_loop.sh` only refreshes the box JSON. Do **not** start full `render_sync` or `start.sh` from the box (stale `blackout.db` would overwrite the live wire). A live `/stats` refresh needs a carefully scoped push of `social_public_stats.json` only, from the machine that owns sync.

## Box-side backups
Any box script edited for stats should be saved as `*.bak_20261110-stats` next to the original before the edit. This branch itself is the rollback point for repo files (`git checkout -- <file>` or revert the branch).
