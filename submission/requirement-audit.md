# Submission requirement audit after gap fixes

Basis: supplied assignment markdown, specs/GRADING_CONTRACT.md and specs/COST_CALCULATOR.md. The user-stopped 244,582-original scope remains frozen; these additions do not restart classification or alter golden answers. No automatic grade is claimed.

| Previously missing | Current evidence |
|---|---|
| Measured one/two workers | Actual same-100 live Jev comparison, fresh result caches and shared limits/reservations; peak overlap two, 20.29/19.35 seconds, total additional $0.002479428. Small single-trial difference, no full-pipeline speedup claim. reports/worker_comparison/report.md. |
| Recovery controls | One known-usage malformed/transient retry, bounded jitter/backoff, unknown-charge stop, isolated accounting/concurrency fixtures. 98 offline tests passed; fixture recovery is not claimed live provider recovery. reports/submission_review/recovery_controls.md. |
| Editable calculator limits | Planning worker/output/fallback controls, preserved actual measurements and unknown unpriced fallback; local generation cap is editable. cost/README.md. |
| Quote/entity support | All 50 inspected by the assistant, 11 semantic/language/temporal concerns and seven entity-omission examples; scores and original human labels unchanged. reports/golden50/quote_entity_inspection.json and CSV. |
| Wrong review label test | Separate test-copy topic/intent/severity all detected against an already-saved real blind answer. Explicit offline replay, zero new inference. reports/submission_review/planted_review_label_replay.json. |
| Review through every stage | Actual source/requests/verification/member/rank/claim walkthrough plus ambiguous handling case. reports/submission_review/real_review_trace.md. |
| Memo claim IDs | Added both existing mean-severity claim IDs, retained raw AI/editorial versions; refreshed checking, local storage and live database artifact. |
| Explicit rubric map | README D1–D4/T1–T3/W1–W3 links and disclosed limits. |
| Portable setup/replay | docs/SETUP.md and scripts/verify_offline.py; actual fresh-copy report records results, including dependency install versus network-blocked offline replay. |
| Versioned public distribution | [Public repository](https://github.com/hieu-nguyen-nth/spotify-insight-pipeline), [release](https://github.com/hieu-nguyen-nth/spotify-insight-pipeline/releases/tag/v1.0.0) and exact code/hash manifest published after explicit user approval. Unauthenticated archive downloads matched their prepared SHA-256; a fresh public checkout passed 98 tests and offline arithmetic/ranking replay. Student submits the repository URL through the course portal. |

Still disclosed: unchanged full-source checker remains review_required for 416,027 incomplete nonempty outputs and unavailable input/output tokens on request 03cb9c58-d8c1-4500-864e-4b9049ddbe6d. Completed-subset integrity and deterministic ranking are separately checked. Golden topic/intent/severity agreement 68%/92%/76% and sentiment MAE 0.4739 remain reported. Blind task agreement is not human accuracy. Completion-based selection prevents population conclusions.

Known project API consumption is $3.671408118; final total is null/provisional with the separate approved $0.05 hold inside $4.80. Existing $5 purchase funds this usage. No new purchase or classification restart is authorized.

Student actions: confirm the ≥100k coverage option and exact extended deadline with the instructor; inspect the disclosure and submit the public repository link through https://submissions-portal-eight.vercel.app. If genuine provider usage evidence is available, supply it locally for reconciliation; never invent the failed request's charge or tokens.
