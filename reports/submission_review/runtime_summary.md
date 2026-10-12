# Actual time and provisional cost

These are separately measured phases, not a fabricated uninterrupted end-to-end full-corpus execution.

| Recorded phase | Actual wall seconds |
|---|---:|
| First full-classification process, stopped on failed request | 4341.188652 |
| Resumed classification process, safely user-stopped | 7348.162629 |
| Completed-subset blind verification/ranking/local generation | 248.249875 |
| Separate one-worker 100-review benchmark | 20.285182 |
| Separate two-worker same-100 benchmark | 19.352753 |

The classification-process timers include their own preparation/dispatch/state work and use different run IDs; human waiting, development, pilots, database upload and deployment are not an invented total added to these. The completed subset is 244,582 original reviews. Full-source throughput/projections are scenarios, not completion evidence. The real cold/warm 100-stage measurements remain in cost/report.md.

All project accounting (pilots, earlier comparisons, unused partial classifications, verification and new worker comparison) records 10,118 attempted calls, including 10,093 TypeSafe attempts. Known API consumption is $3.671408118. Actual total remains null because one paid request's charge/tokens are unavailable. Its approved $0.05 liability hold is separate and within $4.80, not a measured charge. The user's existing $5 credit purchase funds consumption; do not add the two as independent expenses. Local compute/electricity and hosting invoices are unmeasured; Free/Hobby hosting is the configured plan.
