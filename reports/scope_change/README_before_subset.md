# Spotify Insight Pipeline

**Current milestone: full production resumption authorized and started; costs remain provisional.** All 660,622 source rows were ingested; 660,609 nonempty texts require classification and 13 empty texts are quarantined. The stopped run preserved 122,621 fully classified originals and 199,448 distinct topic/intent outputs. Known project API usage at resume was $1.490034630. The user explicitly approved continuing with the existing failed request's charge still unknown and a $0.05 liability hold inside the unchanged $4.80 cap. Original failed outcome and missing token/charge fields are preserved. Any new unknown usage stops dispatch again. See [hold authorization](reports/full_run/reconciliation/hold_authorization.json) and [failure review](reports/full_run/failure_review.json). Measured pilots and the checked 10,000 checkpoint are complete; the checkpoint dashboard is live. Full grading and publication remain pending.

## Evidence and decisions

- [Cost/runtime report](cost/report.md), [offline calculator](cost/README.md), and [dated editable rates](cost/rates.csv).
- [Measured 10,000-review report](reports/checkpoint10000/report.md), [actual usage](cost/checkpoints/10000/calls.jsonl), and [10,000-review checker](reports/checkpoint10000/self_check.json).
- [Measured 500-review report](reports/checkpoint500/report.md), [saved run](reports/checkpoint500/checkpoint_run.json), and [500-review checker](reports/checkpoint500/self_check.json).
- [Golden evaluation and calibration review](reports/golden50/report.md): frozen configuration, original human answers, predictions, actual usage and label disagreements.
- [100-review grading checker](reports/pilot100_optimized/self_check.json), [interruption/resume recording](reports/pilot100_optimized/resume.cast), and [saved grounded memo](reports/pilot100_optimized/memo.md). These are pilot outputs, not full-corpus results.
- [Full ingestion profile](reports/full/ingestion.json), [ingestion measurements](reports/full/ingestion_report.json), [13 quarantines](reports/full/quarantine.jsonl), [dataset checks](reports/dataset_checks.json), and [readiness](reports/readiness.json).
- [Actual synthetic robustness results](reports/robustness/results.json) and [offline tests](reports/foundation_tests.txt). Two actual primary Jev injection cases passed; live transient-error retry recovery remains pending. See [primary Jev evidence](reports/robustness/primary_jev/results.json).
- [Historical four-design comparison](reports/cost_optimization/report.md). Earlier smoke/experimental outputs and rejected memos are retained as historical evidence, not the selected final results.

## Local setup and offline use

Use Python 3.10+; the measured environment is Python 3.12 with pinned VADER 3.3.2. The standalone cost calculator needs only the standard library. For enrichment and local analysis:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
python3 cost/calculator.py
./run.sh evaluate
```

`run.sh` prefers the project virtual environment; set `SPOTIFY_PYTHON` if necessary. Get the supplied course dataset and keep raw CSVs in ignored `data/` or outside Git. The manifest and unchanged development samples are included. On the development machine the full input is `/Users/hieunguyen/Downloads/spotify-insight-dataset/spotify_reviews_18months.csv`.

```sh
./run.sh check-dataset --directory /path/to/spotify-insight-dataset
./run.sh ingest --input /path/to/spotify-insight-dataset/spotify_reviews_18months.csv --db work/full.sqlite --out reports/full/ingestion_report.json --manifest dataset/manifest.json
./run.sh full-status
```

`full-status` reads the frozen production scope in the shared ledger; the historical source ingestion report remains an ingestion-only snapshot. Source strings and instructor row hashes are preserved. SQLite uses WAL and full synchronization; committed progress can resume on the same checksum. Exact-text reuse attaches direct original IDs, hashes and configuration provenance. Human answers remain outside all payload builders; review stars and other metadata are never classifier inputs.

## Deliberate inference

Put `TYPESAFE_API_KEY` in your ignored local `.env` using a local editor. Never include keys in Git, browser code or logs. The fixed Jev choice route is pinned to `jev-1.13.0`, at most 50 reviews per request, one worker, with adaptive smaller payloads and no stronger fallback. A shared transactional ledger in `work/control.sqlite` reserves spend before I/O, settles real provider usage with saved results, shares rate limits and stops on unresolved paid outcomes. Unknown charges require reconciliation. Production currently has no automatic transient retry; that recovery demonstration remains outstanding. Historical paid-enrich/cost-probe dispatch entry points are retired; their offline replay remains available.

For the complete pilot, local issue names/recommendations use `qwen2.5:3b-instruct-q4_K_M`. Start Ollama on loopback port 11434 with that downloaded model; the analysis code checks its exact digest through `/api/tags`. Start a compatible llama.cpp server on loopback port 11435 using the same GGUF and alias. The measured CPU command (binary/model locations vary by machine) is:

```sh
llama-server --model /path/to/model.gguf --alias qwen2.5:3b-instruct-q4_K_M --device none --n-gpu-layers 0 --no-kv-offload --no-op-offload --ctx-size 8192 --host 127.0.0.1 --port 11435
./run.sh pilot-run --out reports/pilot100_optimized --scope pilot100_optimized --batch-size 50 --prompt-version v3 --additional-cap-usd .002 --execute-paid
```

The saved measured scope is warm; a fresh scope intentionally makes new calls. `--interrupt-demo` records a real SIGINT and resume only on a fresh scope. The original six-stage ordering is prepare/deduplicate → fixed-label enrichment → blind verification → aggregate/group → deterministic ranking → grounded memo. Code computes issue membership/claims; the local model names broad topic groups and writes bounded top-three recommendations from those metrics and exact quotes. No paid inference runs during calculator replay or dashboard viewing. Local inference has no API charges; compute/electricity costs are unknown.

To prepare arbitrary input enrichment without sending it:

```sh
./run.sh ingest --input /path/to/reviews.csv --db work/custom.sqlite --out work/custom_ingestion.json
./run.sh lean-pilot --db work/custom.sqlite --out work/custom_prepared --scope custom --batch-size 50 --prompt-version v3
```

Adding `--execute-paid` and an explicit `--additional-cap-usd` deliberately admits paid work. Preparations and experiments must not exceed the remaining project ledger cap. Scaling is never automatic. The independent verifier receives original text and a separate rubric prompt without initial predictions; disagreements are preserved. Sentiment uses local VADER and needs-review is a disclosed heuristic, both evaluated rather than assumed accurate.

## Deployment and completion status

Local processed results and checked analysis artifacts are persisted in SQLite. Rebuild the saved dashboard artifact without inference with `./run.sh save-analysis --out reports/checkpoint10000`.

The user-created **Supabase Free** project `Spotify Review Analysis` (`fkgdvovprcryjoodxyrh`) has the normalized schema, private 10,000-review checkpoint rows, 4,494 issue memberships and six analysis artifacts. [Upload evidence](reports/deployment/database_upload_checkpoint10000.json) and [backend/data/privacy checks](reports/deployment/database_backend_check.json) record actual verification. The public backend returns saved dashboard metrics, recommendations and selected source quotes; complete review/configuration/membership tables deny anonymous reads. Only checkpoint dashboard artifacts were approved for publication. Vercel Hobby deployment is live and verified. The local CLI created deployment `dpl_3TEzyzBm9psap3Bha7WxQ4YHE8Db` in `HAN/spotify-review-analysis`; connector access to the new project was unavailable, so the same scoped CLI was used. [Live verification](reports/deployment/live_check.json) confirms the page, backend and assets return 200 and the API equals the accepted Supabase artifact. Browser checks verified checkpoint metrics, rank-preserving filtering and recommendation-linked source quotes.

**Live URL:** [Spotify Review Analysis](https://spotify-review-analysis-one.vercel.app). **Access:** open directly; no login or model key is required. Use the issue search, select a ranked issue, or choose “Read source evidence” on a recommendation. The page currently shows the checked **10,000-review development checkpoint**, not full results. Empty quarantines show zero within this checkpoint; the full source has 13. Page visits make no inference calls.

[Verified live screenshot](reports/deployment/dashboard-live.jpg). Full results will replace the checkpoint only after full coverage, evidence review, instructor checking and database import.

The student reviewed and accepted the frozen golden disagreements; original scores and answers remain unchanged. Both required 500 and 10,000 checkpoints are complete. [The measured 10,000 report](reports/checkpoint10000/report.md) records actual timing, usage, verification and evidence review. The calculator can credit only validated full-source cache originals:

```sh
python3 cost/calculator.py --checkpoint-size 10000 --checkpoint-allowance 0 --completed-unique 8448
```

Remaining order: finish and inspect the actual full run; review blind verification and raw memo/evidence; export root `grading/` and run the full checker; privately import full processed data within measured storage limits, deploy/test backend/dashboard; publish code/evidence and deliver the repository URL. Validated reuse copied 8,448 original checkpoint outputs with request provenance into production. The user approved the full payload and $4.80 project cap, disk space was freed, and the primary Jev synthetic tests passed for $0.000065772. Full dispatch was explicitly resumed with the user-approved $0.05 liability hold for the one existing failed request; any new unresolved charge stops the run. Status/follow-up checks are scheduled every 15 minutes and notify only on meaningful changes. Prepared commands are:

```sh
./run.sh jev-robustness                        # offline preparation
./run.sh full-run                              # offline preparation/cache transfer
./run.sh full-status                           # offline progress/spend
./run.sh jev-robustness --execute-paid --additional-cap-usd .003
./run.sh full-run --execute-paid --project-cap-usd 4.80
./run.sh full-check                            # after completion, offline checker
./run.sh save-analysis --out reports/full_run   # after evidence review, offline database persistence
```

The last two inference commands deliberately send the approved original/synthetic payloads. Synthetic records are excluded from business data. Verification samples up to 1,000 original texts in bounded batches and caches each completed batch for resume. The primary synthetic test completed. Full execution resumed under the documented narrow liability-hold exception; run locks still prevent duplicates. The $4.80 internal API cap sits within the reported $5 credit purchase and $10 out-of-pocket ceiling. With validated original reuse, full-run API estimates are $4.568215 for the project base case and $4.792331 with 5% retries, both narrow. Longer full texts and sustained latency can change estimates; the cap stops dispatch. Without cross-scope reuse, the retry scenario exceeds the cap. Reviews do not establish revenue loss or observed churn.


After the actual full run and checker pass, export saved full usage/runtime without inference using `python3 cost/export_full.py`. This writes `cost/full/` while retaining the original cold/warm pilot replay. It refuses incomplete production or unreconciled usage.


## Failed-request reconciliation

The actual full run stopped on a network/HTTP failure with no provider usage response. Atomic results remain saved. Provider evidence is required before releasing the reservation; original failed outcome and unknown fields remain in the audit trail. `./run.sh reconcile-usage --evidence /path/to/real_provider_evidence.json` validates evidence offline. Only `--apply` settles the existing failed call, once, without model calls or invented token values. See the null-valued [evidence template](reports/full_run/reconciliation/evidence_template.json). Under the original settlement path, after all unknown usage/reservations are settled and no run lock is active, the already authorized `./run.sh full-run --execute-paid --project-cap-usd 4.80` resumes unfinished stages while reusing committed outputs. The original cap cannot increase. All 85 offline tests pass, including estimate rejection, rate mismatch, active-run protection and duplicate settlement. Future transport failures now save safe exception/status/errno diagnostics; the earlier failure detail was not recorded and is not reconstructed.

[Stopped-run integrity check](reports/full_run/partial_integrity.json): all 122,621 saved completed originals passed ID/hash/quote/configuration/request checks without model calls. This validates preserved partial work; it does not claim full coverage or semantic accuracy.

## Authorized provisional resumption

The user reported a rounded $3.52 balance and explicitly chose to resume while keeping the failed request's charge unknown. [Saved authorization](reports/full_run/reconciliation/hold_authorization.json) covers only request `03cb9c58-d8c1-4500-864e-4b9049ddbe6d`. The shared ledger now holds $0.05 rather than its original $0.001333962 estimate, leaving $3.259965370 of the $4.80 cap at resume. This hold is not billed usage; known costs, null actual charge/tokens and the provider balance observation remain separate. Final cost is provisional until provider evidence resolves the failed request. New unknown failures stop dispatch.

`authorize-unknown-hold --authorization reports/full_run/reconciliation/hold_authorization.json` previews this documented exception offline; only `--apply` adjusts the liability reservation, without inference. Application is atomic/idempotent and refuses active or in-flight runs. Exact provider reconciliation later releases the entire $0.05 hold and retains its authorization record. The 85 passing offline tests include cap enforcement, new-unknown stop, hold idempotence and later evidence reconciliation. Do not start a duplicate while the full run lock is active.

Once the full run completes, run the unchanged checker. Its contract explicitly reports unavailable usage on failed calls; missing token values remain null and must be disclosed. `python3 cost/export_full.py --provisional` then exports to `cost/full_provisional/` only if full coverage is exact and every checker check passes except missing usage on the explicitly held request. It retains `review_required` and its exact flags, keeps total API cost null, lists known usage and the $0.05 hold separately, and preserves raw failed-call data. It cannot certify a complete invoice. Other checker findings, new unknown charges, active runs and incomplete outputs block export. Default `python3 cost/export_full.py` still requires a passing checker and fully reconciled usage and writes `cost/full/`. Neither mode calls providers or changes the original pilot replay. The provisional command was actually tested against the unfinished run and refused export; no full-run cost files have been produced.

Full publication readiness now verifies the unchanged checker and the fingerprints of every graded file before saving/exporting full artifacts. Exact full coverage is mandatory. If the only findings are unavailable token fields on the explicitly approved failed request, the original `review_required` status, flag details and cost status are saved in dashboard metadata and displayed as a limitation. Other flags, changed files, stale reconciliation evidence, new unknown charges or active runs block publication. The raw checker is preserved; this exception does not claim a checker pass or semantic label accuracy. All 85 offline tests passed, including planted findings, changed ranking files, false pass claims and stale provider evidence. Actual full readiness was tested and remains blocked because production is incomplete; no full database upload or dashboard replacement occurred.
