# Actual one-worker versus two-worker Jev comparison

The same unchanged 100 development reviews were sent to `api.typesafe.ai/v1/systemone` under both conditions, in ten-review requests using the frozen Jev v3 blind-verification rubric. Neither condition reused saved results. Both used the same shared SQLite request/token limiter and spend reservations, including the existing $0.05 unknown-charge hold. No business records changed; enrichment remains stopped.

| Actual condition | One worker | Two workers |
|---|---:|---:|
| Completed reviews | 100 | 100 |
| Requests / failed attempts | 10 / 0 | 10 / 0 |
| Wall-clock seconds | 20.285182 | 19.352753 |
| Reviews per second | 4.929707 | 5.167223 |
| Peak simultaneous requests | 1 | 2 |
| Provider input tokens | 29,517 | 29,517 |
| Provider output tokens | 18,786 | 18,785 |
| Calculated API consumption | $0.001239714 | $0.001239714 |

Two workers took about 4.6% less time (1.048× speedup) in this single sequential comparison. This does not establish a sustained or full-pipeline speedup: small-sample variation, provider load, rate limits, and warm provider state were not separately controlled. We measured fresh result caches, not guaranteed cold provider prompt caches. Three reviews had a differing field across conditions; this is model variation, not a concurrency correctness failure. All 100 original IDs were returned exactly once in each condition. Output tokens are recorded but the dated Jev output rate is zero.

Total incremental consumption was **$0.002479428**, below the explicitly approved **$0.01** additional allowance and the unchanged **$4.80** global ceiling. Existing known project consumption became **$3.671408118**; the separate $0.05 liability hold remains unresolved. No new unknown charge occurred. A 1.1-second rate-window cooldown preceded each measured condition and was excluded from both durations.

The evidence supports retaining one worker as the conservative production choice. More workers did not lower cost, and this small gain does not justify rerunning the completed corpus. [Raw report](report.json), [one-worker calls](1/calls.jsonl), [two-worker calls](2/calls.jsonl), [authorization](authorization.json), request/response handoffs and predictions are saved. The explicit comparison command refuses to repeat an existing run; its default mode only prepares a plan.
