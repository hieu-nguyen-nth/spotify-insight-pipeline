# Measured 500-review checkpoint · October 11, 2026

> Historical development checkpoint. Statements about pending dispatch, deployment or injection tests describe the saved checkpoint date. For final scope, completed tests and provisional accounting, see the [current README](../../README.md) and [stopped-project cost summary](../../cost/completed_subset/summary.json). Original measurements and forecasts below are preserved.

**Completed and checked: all 500 original review IDs have valid saved outputs.** The full six-stage incremental checkpoint took **111.701 seconds** and used **$0.003668994** of calculated API usage, below the approved **$0.02 additional cap**. This used existing credit, not a new purchase. Its scope contains 479 distinct texts: 100 original results were reused, 379 new distinct texts were enriched, and 21 additional original IDs reuse exact-text results. One worker, at most 50 reviews per request, unchanged Jev configuration, no stronger fallback and zero automatic retries.

| Stage | Actual seconds | Actual work |
|---|---:|---|
| Prepare/ingest | 0.010 | 500 original rows |
| Enrich | 9.806 | 12 Jev requests; 379 new distinct texts; API $0.003548034 |
| Blind verify | 0.145 | 1 Jev request; 10 independently selected original texts; API $0.000120960 |
| Rank | 0.001 | Exact arithmetic on complaint/cancellation membership |
| Group/name | 46.695 | 1 local Qwen request |
| Memo | 54.946 | 3 local Qwen requests |

There were 17 actual model requests: 13 paid Jev and four local requests with zero API charges. Local compute/electricity cost remains unmeasured. This is an incremental checkpoint with cache reuse, not a cold 500-review benchmark. Throughput projections use **379 newly enriched distinct texts**, rather than dividing variable work by 500 and understating cost. All actual calls and token usage are retained in [the measured run](checkpoint_run.json) and [cost export](../../cost/checkpoints/500/calls.jsonl).

The [instructor checker passed](self_check.json): 500/500 valid completed outputs, zero missing/duplicate/unresolved IDs, 21 valid exact-text aliases, no arithmetic or source-integrity issues. The trace includes the actual earlier 100-review SIGINT/resume followed by checkpoint expansion; it does not claim a second interruption occurred at 500. The independently prompted verifier disagreed on **3/10** sampled reviews. This remains a diagnostic and does not establish a 30% corpus error rate. Initial classifications were not silently overwritten.

The accepted [memo](memo.md) ranks usability first (69 complaint/cancellation rows, severity sum 184), playback second (38, sum 141), and general/other concerns third (58, sum 117). These are checkpoint metrics, not full-corpus findings. Post-run evidence review removed an unmeasured satisfaction inference and unsupported crash-frequency wording, replacing them with reported symptoms and all consumed source examples. [Editorial changes](editorial_review.json) and raw generated memo/recommendations are retained; the corrections made no model calls and did not alter classifications or measured usage.

| Full-run forecast from this checkpoint · estimates only | New full API | Project total incl. prior usage and $0.12 remaining-checkpoint allowance | Estimated full runtime |
|---|---:|---:|---:|
| Exact-text reuse | $4.5449 | $4.6758 | 12,736 seconds · about 3.54 hours |
| No reuse | $6.1964 | $6.3273 | 17,300 seconds · about 4.81 hours |
| Reuse + 5% retries | $4.7721 | $4.9030 | 13,362 seconds · about 3.71 hours |

The base fits the $4.80 internal project API cap, while the retry scenario exceeds it. Earlier known project consumption is now **$0.010886988 across 62 paid requests**. These totals conservatively include all 484,189 distinct full-source texts as new work and a separate allowance for the unmeasured 10,000 step; valid transfer into the full run may reduce work, but full transfer/coverage must be verified before claiming savings. No full-corpus classification or deployment has run. Hardware/hosting costs remain unknown. Estimates use observed stage timing and rates; unchanged rates and sample costs are not proof that throughput is linear.

Next: prepare the fixed 10,000-review input, keep the classifier frozen, reuse the 479 validated originals, and measure before full dispatch. The proposed additional API cap is $0.20 from existing credit. Paid execution requires specific approval for that larger payload and cap. Continue enforcing original IDs/hashes/quotes, blind verification, bounded requests, shared rate/spend controls and atomic resume.
