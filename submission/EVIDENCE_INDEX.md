# Current grading evidence index

Use current repository source and tracked reports. The **v1.0.0 evidence ZIP** is the frozen execution evidence; download it from the [public release](https://github.com/hieu-nguyen-nth/spotify-insight-pipeline/releases/tag/v1.0.0) and extract in the repository root with `unzip -n submission-evidence.zip -d .`. This fills missing large files without replacing later reviewed documents. [Archive manifest](https://github.com/hieu-nguyen-nth/spotify-insight-pipeline/releases/download/v1.0.0/manifest.json) contains exact checksums/sizes. [Latest revision manifest](checklist_revision_manifest.json) describes these repairs; [saved-result revision](saved_result_revision_manifest.json), [first editorial revision](review_revision_manifest.json) and [original run manifest](final_run_manifest.json) preserve the sequence. Do not use the historical source ZIP in place of current source.

| Required grading file | Access and purpose |
|---|---|
| [run.json](../grading/run.json) | Final stopped run, model/settings and phases. |
| [ingestion.json](../grading/ingestion.json) | Full original profile: 660,622 source IDs, 660,609 nonempty, 13 empty. |
| `grading/records.jsonl` | Large file inside the evidence ZIP; 244,582 completed originals plus 13 quarantines. |
| [membership.csv](../grading/membership.csv) | Every issue-to-review member. |
| [ranking.csv](../grading/ranking.csv) | Counts, severity sums, mean and reproducible baseline priority. |
| [claims.csv](../grading/claims.csv) | Material issue-level claim IDs and numbers. |
| [calls.jsonl](../grading/calls.jsonl) | Actual attempts, outcomes, input IDs, model/config and reported or missing usage. |
| [checkpoint_before.json](../grading/checkpoint_before.json) | Saved interruption progress. |
| [checkpoint_after.json](../grading/checkpoint_after.json) | New completed work after unchanged-settings resume. |

The ZIP also supplies large completed records/analysis CSV, full-run handoffs and cost usage. The [download inventory](../reports/checklist_fixes/delivery_check.json) checks all nine grading paths and README evidence links against current files or exact archive entries. Source and evidence are public; no login/API key is required. The full original raw CSV is supplied by the [course dataset](https://haas-ai-classes-fall-26.vercel.app/assignment5.html), with [source link and checksum](../dataset/manifest.json).

| Requirement | Current inspectable evidence |
|---|---|
| Roles, instructions, input/output schemas | [Architecture and diagram](../ARCHITECTURE.md), [common labels/examples](../labels/README.md), [course contract](../specs/GRADING_CONTRACT.md), [frozen configuration](../reports/completed_subset/configuration.json), saved handoffs in ZIP. |
| Golden comparison and inspected failures | [Original human labels](../reports/golden50/human_labels_as_evaluated.csv), [predictions](../reports/golden50/records.json), [evaluation](../reports/golden50/evaluation.json), [error inspection](../reports/result_review/README.md), [production overlap](../reports/checklist_fixes/golden_export_coverage.json). |
| Blind/adversarial verification | [1,000-review verifier](../reports/completed_subset/verification.json), [inspected differences](../reports/completed_subset/verification_review.json), [real Jev injection outcomes](../reports/robustness/primary_jev/results.json), [offline planted-label replay](../reports/submission_review/planted_review_label_replay.json). |
| Traceable decision and calculations | [Real source-to-memo trace and ambiguous case](../reports/submission_review/real_review_trace.md), [memo with claim IDs](../reports/completed_subset/memo.md), [raw AI memo](../reports/completed_subset/memo_ai_raw.md), [membership/ranking sensitivity](../reports/completed_subset/ranking_sensitivity.md). |
| Real calculator pilot and controls | [Per-stage cold/warm metadata](../cost/pilot_metadata.md), [all 100 statuses](../cost/pilot_records.jsonl), [all calls](../cost/pilot_calls.jsonl), [usage](../cost/usage.csv), [rates](../cost/rates.csv), [calculator/offline commands](../cost/README.md), [recovery evidence](../reports/submission_review/recovery_controls.md). |
| Interruption and resume | [Recording](../reports/pilot100_optimized/resume.cast), checkpoints above, per-attempt initial/resume phases. |
| Clean setup, tests and recalculation | [Fresh install and 104 tests](../reports/checklist_fixes/clean_environment_check.json), byte-identical membership/ranking/claims, [setup](../docs/SETUP.md). |
| Deployed database/backend/dashboard | [Database upload](../reports/deployment/database_upload_completed_subset.json), [database schema/access](../database/README.md), [local UI and public baseline checks](../reports/checklist_fixes/live_verification.json), [public dashboard](https://spotify-review-analysis-one.vercel.app). |
| Credentials and privacy | [Current scan](../reports/checklist_fixes/security_check.json), blank .env.example, ignored .env, no tracked real env files. Original frozen history retains some personal path metadata. |

Full-source self-check remains **review_required**: 416,027 incomplete classifications and one failed request with unavailable input/output tokens. [Current check](../reports/checklist_fixes/full_source_check.json) keeps the instructor checker unchanged. The ≥100K option is achieved, but the full-source coverage formula and any instructor interpretation remain disclosed. No private-benchmark score, full completion or reconciled final bill is claimed. The student submits the repository URL through the course portal.
