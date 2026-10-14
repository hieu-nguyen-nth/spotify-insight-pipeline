# Offline cost/runtime calculator

Run from the project root with Python 3.10+; this calculator uses only the standard library. The default replays real saved measurements and makes **no model calls, network requests or key reads**:

```sh
python3 cost/calculator.py
python3 cost/calculator.py --out cost/replay.json
python3 cost/calculator.py --budget 4.8 --verification-max 1000 --retry-fraction .05 --checkpoint-allowance .125
```

Read [the measured report](report.md) and [the completed 500 checkpoint](../reports/checkpoint500/report.md). Project from saved incremental 500 usage with `python3 cost/calculator.py --checkpoint-size 500 --checkpoint-allowance .12`; it uses 379 new distinct texts as the enrichment denominator and retains the original 500-row measurements. The default still replays the original cold/warm 100. Inputs are [100 pilot records](pilot_records.jsonl), [actual per-attempt calls](pilot_calls.jsonl), [cold/warm runs](pilot_runs.json), [usage](usage.csv), [editable dated rates](rates.csv), and [earlier project consumption](project_usage.json). Pilot logs are separate from full-corpus grading exports. The project snapshot includes the pilot, comparisons, historical failures and golden evaluation; it is calculated usage, not an account-balance statement or provider receipt.

Edit a copy of `rates.csv`, then pass `--rates /path/to/rates.csv`. API rates use USD per token; Jev's $0.042 per million input tokens is `0.000000042` per token, with output at zero. Doubling input/output API rates doubles replayed pilot API consumption and projected new API work without changing measured time. Historical already-incurred consumption stays fixed unless explicitly overridden with `--prior-spend`. Local API charges are zero; hardware/electricity and hosting remain **unknown**. Volume flags `--unique` and `--nonempty` change projections only. Other editable assumptions are the API budget, retry fraction, verifier sample cap and checkpoint allowance. Planning flags now include --max-workers (1–2), --output-token-cap (32–4096), --fallback-fraction (0–1), and optional --fallback-usd-per-review. Saved measurements remain one worker and 1,024 local output tokens; changing planned workers never divides measured duration. Nonzero unpriced fallback leaves projected cost/time unknown; an explicit fallback price is hypothetical, and execution fallback remains zero. The separate live 1/2-worker report is linked below; it is not applied as a full-pipeline speedup.

**Explicit inference command:** after locally configuring `TYPESAFE_API_KEY`, the pinned local model and both loopback runtimes described in the main README, a cold six-stage 100-review pilot can be deliberately started with:

```sh
./run.sh pilot-run --out reports/pilot100_optimized --scope pilot100_optimized --batch-size 50 --prompt-version v3 --additional-cap-usd .002 --execute-paid
```

The existing saved scope is warm and made zero new model calls in its measured repeat. A fresh scope intentionally incurs new calls; add `--interrupt-demo` only for a fresh scope to record an actual SIGINT after committed progress. Input stays the unchanged `cost_100.csv`. Never call this command from calculator imports or page loads. Requests have at most 50 original review texts; code adapts downward for payload size. The global SQLite ledger reserves spend before dispatch, shares rate limits, persists partial work, and stops on unknown paid usage. The saved production run used zero automatic retries. Revised dispatch supports one retry only for known-usage invalid/transient outcomes, with backoff/jitter and per-attempt accounting. Isolated transport fixtures demonstrate recovery; unknown usage still stops admission. No live failed-provider recovery is claimed. See the saved failure evidence for earlier local-runtime and memo-validation attempts.

The 10,000 checkpoint is also measured and exported. Use `python3 cost/calculator.py --checkpoint-size 10000 --checkpoint-allowance 0` for the latest incremental throughput (7,969 new distinct texts). Add `--completed-unique 8448` only when the separately checked full-source transfer inventory is applicable. This reduces future enrichment work, keeps prior incurred usage and original measurements unchanged, and leaves the deliberately no-reuse scenario unchanged. Do not carry an unmeasured checkpoint allowance after those stages are complete. See [10,000 evidence](../reports/checkpoint10000/report.md); extrapolation is not full execution.

Full-run exports are offline and separate from the original 100-review replay. After actual full completion and checking, `python3 cost/export_full.py` requires reconciled usage and writes `cost/full/`. The explicitly selected `--provisional` mode writes `cost/full_provisional/`, retaining the held failed request's null tokens/charge, known costs, liability hold, and any missing-usage checker flags. Full coverage must be exact, and other checker errors still block export. Neither full export exists: the user intentionally stopped classification. The $0.05 hold is not actual cost; no instructor checker pass is claimed.

The actual **244,582-review completed subset** has a separate [provisional accounting export](completed_subset/summary.json), generated offline with `python3 cost/export_subset.py`. It retains all 10,118 project attempts, including pilots, unused partial work and the failed request; known API consumption is **$3.671408118**, unknown charge/tokens remain null and the approved **$0.05 hold** is separate. The existing $5 credit purchase is cash spent, not another $5 to add to consumption. Actual downstream verification/analysis took 248.250 seconds and used $0.009579654 of API credit. The current clean-copy check passed 104 tests; see [test evidence](../reports/checklist_fixes/fresh_offline_tests.txt). Fresh full-run projections may exceed the current cap because they add future work to already-incurred usage; they do not authorize resumption.

[Actual one/two-worker comparison](../reports/worker_comparison/report.md) used identical 100-review inputs and fresh result caches: 20.285182 versus 19.352753 seconds, ten calls per condition and $0.001239714 each. Total additional consumption was $0.002479428. The small single-trial improvement supports retaining one production worker; it does not lower cost or establish full-stage scaling.

```sh
python3 cost/calculator.py --max-workers 2 --output-token-cap 512 --fallback-fraction .01
# Explicit hypothetical fallback price; not a new provider execution:
python3 cost/calculator.py --fallback-fraction .01 --fallback-usd-per-review .0002
# Separate comparison module defaults to plan preparation; repeat execution is guarded:
PYTHONPATH=src python3 -m spotify_pipeline.worker_comparison
```

[Complete pilot stage metadata](pilot_metadata.md) consolidates exact versions, inputs/outputs, usage, prices and cold/warm cache behavior. Measured and projected stage costs share the same billing function: uncached input, cached input and output are mutually exclusive. Reasoning already included in output is not billed again. The saved pilot reports no provider prompt-cache usage; regression fixtures exercise that billing category without changing pilot evidence.
