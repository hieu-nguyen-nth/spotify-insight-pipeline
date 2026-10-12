# Spotify Insight Pipeline

[Live dashboard](https://spotify-review-analysis-one.vercel.app) · [Decision memo](reports/completed_subset/memo.md) · [Saved execution evidence](https://github.com/hieu-nguyen-nth/spotify-insight-pipeline/releases/tag/v1.0.0) · [Fresh setup](docs/SETUP.md)

**244,582 original reviews are fully classified.** All **660,622** source rows were ingested and preserved, **13** empty texts were quarantined, and **416,027** nonempty reviews remain incomplete. The achieved scope exceeds the supplied assignment's **at least 100,000** option. Other sections and the unchanged checker retain full-corpus wording; [scope and deadline clarification](reports/scope_change/scope_decision.json) remains an instructor decision. This is a stopped production subset, not a complete 660K classification run.

**Selection limitation:** completion depended on processing stage and intent. Praise/request/unclear reviews often finished before complaints awaiting severity. Counts, complaint share and ranking describe this subset only; they are not population estimates. The [memo](reports/completed_subset/memo.md) recommends investigating usability and playback together before committing next-quarter effort.

## Results and evaluation

| Broad issue | Complaint/cancellation reviews | Baseline priority: severity sum |
|---|---:|---:|
| Usability | 5,862 | 15,949 |
| Playback | 4,157 | 15,278 |
| Billing | 1,656 | 4,906 |

The baseline includes all **15,825** completed complaint/cancellation reviews, one issue per common topic, and equals count × unrounded mean severity. Sort descending by integer severity sum, then ascending issue ID. [Membership](reports/completed_subset/membership.csv), [ranking](reports/completed_subset/ranking.csv) and [claim IDs](reports/completed_subset/claims.csv) trace every number. Broad topic counts do not measure the prevalence of a specific defect; quoted symptoms are investigation candidates, not proven causes.

**Sensitivity:** usability's lead is **671 points (4.4% of playback's score)**. Excluding `needs_review` records only in a separate diagnostic reverses the order: playback **9,792**, usability **7,482**. Of complaint/cancellation records, **7,518/15,825 (47.5%)** carry that flag. This exclusion introduces its own bias; it does not replace the required baseline or correct labels. See [reproducible diagnostic](reports/completed_subset/ranking_sensitivity.md).

| Frozen human-50 diagnostic | Result |
|---|---:|
| Topic agreement with original human labels | 34/50 · 68% |
| Intent agreement | 46/50 · 92% |
| Severity exact agreement / mean absolute error | 38/50 · 76% / 0.24 |
| Sentiment mean absolute error on −1 to +1 | 0.4739 |
| Needs-review agreement | 36/50 · 72% |
| Exact source-substring quotes | 50/50 |

**Why the experiment continued:** topic agreement depends on the human labeler's interpretation of the review and rubric. After inspecting the disagreements, the student who supplied the human labels reports agreeing with the model's topic classification for the majority of disputed cases. The student therefore accepted the frozen classifier and continued. The 68% figure measures agreement with the original labels; it is not an adjudicated accuracy score. This follow-up is qualitative, with no new case-level tally. Original labels, predictions, scores and prompts remain preserved. See [golden results and error analysis](reports/golden50/report.md) and [student decision](reports/golden50/student_review_decision.json). [All topic disagreements and the largest sentiment errors](reports/result_review/README.md) now have saved assistant observations, clearly separated from the student’s human decisions. Sentiment and language limitations remain separate from topic acceptance.

The [blind verifier](reports/completed_subset/verification.json) re-labeled 1,000 completed-review texts without seeing original predictions: **193** had a differing field; topic/intent/severity agreement was **90.7%/92.8%/92.3%**, severity mean absolute difference **0.099**. This is a separate Jev task, not a different model or human accuracy measurement. [Eight inspected disagreements](reports/completed_subset/verification_review.json) include complaint-versus-request precedence failures. Original labels were retained. Human answers were excluded from payloads and prompt tuning; quote/entity support was inspected separately.

## Live result and model responsibilities

[Spotify Review Analysis](https://spotify-review-analysis-one.vercel.app) requires no login or model key. Search an issue, select its ranking row, or use “Read source evidence.” The deployed Python backend retrieves saved dashboard data from Supabase; visits make no inference calls. The verified upload stored **244,582 private rows**, **15,825 memberships** and **six artifacts**. Only published aggregates/recommendations/selected quotes are public. [Database setup](database/README.md), [live checks](reports/deployment/live_completed_subset_check.json) and [browser evidence](reports/deployment/browser_completed_subset_check.json) document the baseline. The dashboard presents the joint usability/playback investigation recommendation and a separate sensitivity table alongside the unchanged baseline. Each leading recommendation cites three saved examples. [Saved-result audit](reports/result_review/README.md) documents all nine quote/membership checks and the golden disagreement/sentiment inspection; the original execution presentation remains preserved.

[Architecture](ARCHITECTURE.md): Python/SQL preparation and exact-text deduplication → Jev topic/intent → conditional severity → separate blind verification → code membership/ranking → local Qwen issue names and recommendation drafts → editorial review. Source ratings remain metadata. Local **VADER** supplies sentiment, and code extracts explicit entity terms and validates quotes. Models interpret language; code owns arithmetic, state and dispatch.

| Role | Saved configuration |
|---|---|
| Classify / blind verify | `jev-1.13.0`, frozen `conditional-severity-v3`, ≤50 reviews per request, one production worker, zero stronger fallbacks and zero automatic retries in the saved run. |
| Local issue naming / writing | `qwen2.5:3b-instruct-q4_K_M`, pinned digests, temperature 0, seed 7, non-thinking, 1,024-token output cap. |

**Local writing:** Qwen generated issue names and recommendation drafts; code rendered metrics and editorial review produced the final memo. [Raw recommendations](reports/completed_subset/recommendations_ai_raw.json) and [raw AI memo](reports/completed_subset/memo_ai_raw.md) are retained. Local API charges are **zero**; hardware/electricity costs are unmeasured. [Setup](docs/SETUP.md) supplies exact runtime/model digests. Suitable local models are permitted by the assignment.

Matching model/prompt/schema/effort is required for exact-text reuse with direct original provenance. The 10K checkpoint demonstrated **1,552** aliases; the final subset contains completed originals only. Pending IDs derive from SQLite; validated batches save atomically and shared rate/spend reservations precede dispatch. [Real interruption/resume](reports/pilot100_optimized/resume.cast) demonstrates no relabeling of saved records. The revised dispatcher allows one known-usage invalid/transient retry with backoff/jitter; [recovery fixtures](reports/submission_review/recovery_controls.md) are distinct from production execution. Unknown charges stop dispatch.

[One/two-worker comparison](reports/worker_comparison/report.md): **20.29/19.35s** on the same 100 texts, equal **$0.001239714** usage per condition. This single trial does not establish sustained speedup or a Batch API discount.

## Offline inspection and reproduction

Use the current repository source. The **v1.0.0 release is the original frozen execution package**; its archived prose predates the follow-up review. Download its [complete evidence ZIP](https://github.com/hieu-nguyen-nth/spotify-insight-pipeline/releases/download/v1.0.0/submission-evidence.zip), then extract with **`unzip -n`** to fill absent large records/handoffs while preserving current tracked reports. [Distribution instructions](submission/README.md) explain current source versus archived execution evidence.

Python **3.10+** is required; recorded runs used **3.12**. Follow [fresh setup](docs/SETUP.md) for dependencies, CSV input and stage commands. The calculator is standard-library-only. These replay commands need no model key, paid call or network:

```sh
mkdir -p work
python3 cost/calculator.py --out work/cost_replay.json
./run.sh replay-ranking --records reports/completed_subset/records.json --out work/ranking_replay
python3 scripts/ranking_sensitivity.py --records grading/records.jsonl --out work/ranking_sensitivity.json
python3 scripts/audit_saved_evidence.py --records grading/records.jsonl --out work/result_review_replay
```

Compare replayed membership/ranking/claims against the saved files. [Subset integrity](reports/completed_subset/subset_integrity.json) checks source IDs/hashes/quotes, committed labels, real bounded-request provenance and arithmetic; [ranking replay](reports/completed_subset/ranking_replay_check.json) is byte-identical. [Clean-environment checks](reports/submission_review/clean_environment_check.json) used no credentials/state, with network blocked during calculator/ranking replay. Model reruns are separately explicit; classification remains stopped and scheduled follow-ups paused.

The [course dataset](https://haas-ai-classes-fall-26.vercel.app/assignment5.html) full CSV SHA-256 is `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`. The [manifest](dataset/manifest.json), [ingestion](reports/full/ingestion.json) and [quarantines](reports/full/quarantine.jsonl) identify the input. To run the unchanged checker:

```sh
python3 vendor/check_submission.py reference --full /path/to/spotify_reviews_18months.csv --analysis /path/to/spotify_reviews_18months.csv --out work/full_reference.json
python3 vendor/check_submission.py check --reference work/full_reference.json --submission grading --out work/full_check.json
```

Expected result: [**`review_required`**](reports/completed_subset/instructor_full_source_check.json), for **416,027** missing/incomplete outputs and unavailable input/output tokens on one failed request. Subset integrity is a separate check, not a full-corpus pass or automatic grade. The unchanged full-corpus coverage formula gives **0.4962/1**; applying the ≥100K option remains an instructor decision.

## Measured time and provisional cost

The actual **100-review cold pilot** took **102.185s** and used **$0.001058946** API credit; the warm repeat took **0.179s**, with **zero new model calls**. [Historical pilot/checkpoint report](cost/report.md), [editable calculator and rates](cost/README.md), [500](reports/checkpoint500/report.md) and [10K](reports/checkpoint10000/report.md) measurements include stage usage and base/conservative projections. Projections are scenarios, not executions.

| Recorded production phase | Wall seconds |
|---|---:|
| First classification process, stopped on failed request | 4,341.19 |
| Resumed classification, stopped at the student's request | 7,348.16 |
| Completed-subset verification/ranking/local generation | 248.25 |

These are separately measured phases, not a fabricated uninterrupted full-corpus runtime. Downstream analysis made **20** paid verifier requests and **four** local generation calls, using **$0.009579654** API credit. [Runtime details](reports/submission_review/runtime_summary.md) identify runs and exclusions.

[Known project API consumption](cost/completed_subset/summary.json) is **$3.671408118**, including pilots, partial work, comparisons, failures and verification, funded by the existing **$5 TypeSafe credit purchase**. Do not add purchase and consumption as independent expenses. One failed request still has unknown charge/tokens; the approved **$0.05 liability hold** is an allowance inside the **$4.80 API ceiling**, not a measured charge. Final total remains null/provisional. Local compute/electricity and hosting invoices are unmeasured; Supabase Free and Vercel Hobby host the result. [Failed-call and reconciliation evidence](reports/full_run/reconciliation/hold_authorization.json) is preserved. Reconciliation does not restart classification.

## Rubric evidence map

| Criterion | Evidence |
|---|---|
| D1 accessible code/setup | [Setup](docs/SETUP.md), [distribution](submission/README.md), [clean checks](reports/submission_review/clean_environment_check.json). |
| D2 architecture/provenance | [Architecture](ARCHITECTURE.md), [rubric/examples](labels/README.md), [real review trace](reports/submission_review/real_review_trace.md). |
| D3 checked calculations | [Ranking](reports/completed_subset/ranking.csv), [claims](reports/completed_subset/claims.csv), [integrity](reports/completed_subset/subset_integrity.json). |
| D4 recommendation/alternatives | [Memo](reports/completed_subset/memo.md), [sensitivity](reports/completed_subset/ranking_sensitivity.md), [raw AI prose](reports/completed_subset/memo_ai_raw.md). |
| T1 human evaluation/errors | [Golden report](reports/golden50/report.md), [student review](reports/golden50/student_review_decision.json), [quote/entity inspection](reports/golden50/quote_entity_inspection.csv). |
| T2 independent/adversarial checks | [Blind verification](reports/completed_subset/verification.json), [planted-label replay](reports/submission_review/planted_review_label_replay.json), [injection tests](reports/robustness/primary_jev/results.json). |
| T3 calculator/recovery | [Pilot](cost/report.md), [calculator](cost/README.md), [recovery tests](reports/submission_review/recovery_controls.md), [98 tests](reports/submission_review/offline_tests.txt). |
| W1 coverage/classification | [Full ingestion](reports/full/ingestion.json), [scope](reports/completed_subset/scope_manifest.json), [full-source check](reports/completed_subset/instructor_full_source_check.json). |
| W2 stages/resume | [Stage commands](docs/SETUP.md), saved role handoffs, [resume recording](reports/pilot100_optimized/resume.cast). |
| W3 ranking/database/live result | [Ranking replay](reports/completed_subset/ranking_replay_check.json), [upload](reports/deployment/database_upload_completed_subset.json), [live dashboard](https://spotify-review-analysis-one.vercel.app). |

[Submission audit](submission/requirement-audit.md) and [follow-up revision manifest](submission/review_revision_manifest.json) distinguish original execution evidence from later explanatory changes. Submit the repository URL through the course portal; portal submission is the student's final step.
