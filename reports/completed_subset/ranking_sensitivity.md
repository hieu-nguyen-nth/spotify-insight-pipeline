# Ranking sensitivity: records marked for review

The required baseline remains unchanged: usability ranks first with 15,949 severity points, playback second with 15,278. The 671-point margin is 4.4% of playback's baseline score. A separate diagnostic excludes completed records with `needs_review=true` and recomputes the same severity-sum rule. This changes the winner to playback. Investigate both groups before allocating next-quarter effort; this check does not establish a replacement ranking.

| Broad issue | Baseline count | Baseline severity sum | Unflagged count | Unflagged severity sum |
|---|---:|---:|---:|---:|
| Usability | 5,862 | 15,949 | 2,887 | 7,482 |
| Playback | 4,157 | 15,278 | 2,555 | 9,792 |
| Billing | 1,656 | 4,906 | 598 | 1,768 |
| Other | 1,843 | 3,857 | 1,179 | 2,396 |
| Catalog | 1,084 | 3,027 | 409 | 1,172 |
| Access | 603 | 2,378 | 394 | 1,576 |
| Downloads | 572 | 2,001 | 269 | 978 |
| Support | 48 | 143 | 16 | 42 |

The frozen 244,582 completed records include 59,633 review flags. Among the 15,825 complaint/cancellation records, 7,518 are flagged (47.5%). The stored flag reflects low choice confidence or the declared neutral/non-ASCII language heuristic; it is neither calibrated error probability nor proof that a label is wrong. Excluding flags changes the selected record mix and introduces its own bias. Both scenarios also retain the original completion-based selection limitation. Neither is a population estimate or a human-accuracy measurement.

Run from the repository root after extracting the original execution evidence with `unzip -n`:

```sh
python3 scripts/ranking_sensitivity.py --records grading/records.jsonl --out work/ranking_sensitivity.json
```

The standard-library script streams saved JSONL, checks duplicate IDs and flag/severity types, and makes no network/model calls. Compare its output with [ranking_sensitivity.json](ranking_sensitivity.json). The input SHA-256 is `10456fc611a0eb420793557a9ea7aece0e2e3b806a032f8d577046f6be401762`, matching the unchanged grading records. The baseline count and severity sums match [ranking.csv](ranking.csv). Diagnostic quantities are explicitly separate from the required [claims.csv](claims.csv); original membership, ranking, labels, prompts and golden scores were not modified.
