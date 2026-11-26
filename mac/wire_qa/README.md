# Wire post-publish QA (Mac)
Independent of the site's pre-publish validator. Standard-library Python, read-only HTTP, no paid APIs.
KeepAlive launchd daemon `com.blackout.wireqa`: a pass every ~10 s; only items it has not seen; one cached `/api/wire_tl?limit=40` read per pass
(conditional headers sent), then the Full Story page + og image head for each new item. Errors / 429 / 503 back off 10 s -> 5 min.

Checks: og card is a photo PNG (60 KB+), not the text fallback / map / satellite; category matches the text; the photo fits the category
(photo facts from the signed `/internal/wire/qa`); location words appear in the text, no agency codes; 3-5 tags, no function words /
fragments / #News; write-up has 25+ real words beyond the headline and boilerplate; headline not cut on a dangling word; Full Story page 200.

Holds: a failing item is held through the signed `/internal/wire/qa` hold list (off the Wire list; the story page stays, as with every
other hold). The key is read from `~/blackout_mac/.env` (BN_SYNC_SECRET, the sync's own) at run time; never copied or printed. With no key:
nothing is held, the failure is logged and `FLAG_qa_unheld.txt` is written. A rule failing >60% of a batch of 8+ is treated as a QA fault:
flagged, not held. Holds are re-checked every 5 min and released when they pass; the whole list is re-sent every 5 min (site restarts).

Files: `~/blackout_mac/wire_qa/logs/YYYYMMDD.jsonl` (one line per item), `wire_qa.log`. Pause: `touch ~/blackout_mac/wire_qa/OFF`.
Turn a rule off: `BN_QA_RULES_OFF=thin-writeup` in the plist environment. Install: `bash install.sh`. Remove: `bash uninstall.sh`.
