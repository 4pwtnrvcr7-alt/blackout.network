# Rollback — agency feeds added to the Wire registry (branch `registry-data`)

- Prepared: 01:05 AM ET, Saturday Nov 28 2026
- PREVIOUS registry-data head (PREVIOUS_MAIN for this branch): `de64276b488b04d35af51c290ac421d6d7c159d8` (registry module v5; registry JSON version 202611280206, 1301 feeds, unchanged since `1d70268`)
- Backup branch: `release/2026-11-28-pre-agency-feeds-backup` @ `de64276b488b04d35af51c290ac421d6d7c159d8`
- Change: `sources_registry.json` 1301 -> 1343 feeds (+42 official agency feeds, `batch: 6`, `fam` starting `agency:`), plus notes in `registry_notes/`.
- No Render deploy: Render auto-deploys `main` only. This branch is read by the Mac scanner (raw.githubusercontent.com, ~10 min pull + ~5 min CDN cache), so no site restart, no downtime, no `og.VERSION` change.

## Full rollback
```
git revert --no-edit <squash sha> && git push origin HEAD:registry-data
```
or restore the pre-change file: `git checkout de64276 -- sources_registry.json && git commit -m "revert agency feeds" && git push origin HEAD:registry-data`.
The scanner picks the old registry up within ~15 min; items already ingested stay on the Wire as normal rows (nothing deleted).

## Partial kills
- One feed: set `"off": true` on its entry (module drops `off` feeds), or add its id to `sources_registry_disabled.json` on the Mac.
- All agency feeds: remove entries whose `fam` starts with `agency:` (jq: `.feeds |= map(select(.fam|startswith("agency:")|not))`).

## Not changed
scanner.py scoring, push.py, jets.py, config.json, aviation_watch.py, QA gates, brief gate, publish gate, writer min rank (5), writer cap ($5.00/day), og.VERSION, main.

## Leftover state
None client-side. Scanner-side: ingested alerts remain in blackout.db like any other source.
