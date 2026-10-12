# Measured 10,000-review checkpoint · October 11, 2026

The accepted frozen configuration completed all 10,000 reviews in **321.593 seconds (5 minutes 22 seconds)** for **$0.074998392 calculated API usage**, within the approved $0.20 incremental cap. The instructor checker passed 10,000/10,000 outputs, with 1,552 valid exact-text aliases and no missing, duplicate, invalid or unresolved output IDs. This is a development checkpoint, not full-corpus completion or certified semantic accuracy.

| Stage | Actual seconds | Actual API USD | Work |
|---|---:|---:|---|
| Preparation | 0.070 | 0 | Preserved fixed input/hash; validated cache transfer |
| Enrichment | 209.471 | 0.074874240 | 239 Jev requests; 7,969 new distinct texts |
| Blind verification | 0.173 | 0.000124152 | 10 original texts, 1 independent Jev request |
| Ranking | 0.009 | 0 | Deterministic arithmetic |
| Group names | 54.505 | 0 API | 1 local Qwen request |
| Recommendations/memo | 56.331 | 0 API | 3 bounded local Qwen requests |

The input contains 8,448 distinct texts. Enrichment reused 479 validated original results from the 500 checkpoint; 7,969 distinct texts were new. There were 244 actual model requests, including 240 paid Jev calls and four local calls, one worker, at most 50 reviews per request, no stronger fallback and no automatic retry. Local hardware/electricity costs are unknown. The blind verifier disagreed on 2/10 reviews; predictions were retained unchanged. This small model-agreement diagnostic is not a human-accuracy estimate.

| Ranked issue group | Complaint/cancellation rows | Severity sum / priority |
|---|---:|---:|
| Usability | 1,370 | 3,681 |
| Other | 1,269 | 2,594 |
| Billing | 759 | 2,208 |

There are 4,494 complaint/cancellation membership rows across all groups. Ranking includes every original row, including exact-text aliases, orders severity sum descending and breaks ties by issue ID ascending. These are broad topic groups, not discovered root causes or full-population estimates. Quoted reviews describe user reports, not verified harm. Reviews cannot establish revenue loss or observed churn.

Post-run evidence review corrected unsupported notification/access wording, an overly generic privacy summary, and a causal inference from billing counts. [Raw recommendations](raw_generated_recommendations.json), [raw memo](raw_generated_memo.md) and [editorial reasons](editorial_review.json) are retained. No additional model calls or classifier changes were made. Six accepted dashboard/analysis artifacts and 4,494 normalized membership rows were actually saved in local SQLite; a cloud database/dashboard has not been deployed.

Known calculated project API consumption is **$0.085885380 across 302 paid attempts**, with zero unresolved usage and zero reservations at the saved snapshot. This includes previous experiments/failures, golden evaluation and all measured checkpoints. It is calculated usage, not a provider receipt or balance. The student reports buying $5 credit; no additional purchase was made.

The 10,000-based full-run forecast without cross-scope reuse is $4.647589 total project API usage and about 3.60 hours. A separately verified cache inventory found 8,448 same-ID/hash/text/configuration original results eligible for full-source transfer. These 8,448 originals have now been copied into the full scope, with original request provenance retained, leaving 475,741 distinct texts for new enrichment. The calculator supports this explicit credit in [the cache-aware forecast](full_forecast_with_cache.json); predictions remain estimates. Full distinct texts average 98.57 characters versus 87.59 here, and label mix, request sizes and sustained runtime can change costs. With validated cache credit, the base project API estimate is $4.568215 (about 3.53 hours), and the 5% retry case is $4.792331, narrowly within $4.80; without that credit, the retry case exceeds the cap. Production must stop before a new reservation exceeds the cap and must reconcile any unknown charge; no full paid dispatch has occurred.

Evidence: [actual measured run](checkpoint_run.json), [instructor checker](self_check.json), [saved verification](verification.json), [ranking](ranking.csv), [accepted memo](memo.md), [saved dashboard](dashboard.json), [actual usage export](../../cost/checkpoints/10000/calls.jsonl). The interruption trace in scoped grading is the actual earlier 100-review SIGINT/resume followed by measured expansions; no new interruption at 10,000 is claimed.

Full preparation is saved in [the execution plan](../full_run/execution_plan.json). No new full-source model calls were made. The machine had about 3.84 GiB free; initial execution requires 6 GiB to allow for SQLite/WAL, raw response evidence and atomic grading exports. Free roughly another 3 GB before dispatch. A specific full payload/cap approval has been requested and is pending. The primary Jev synthetic checks are prepared, not executed.
