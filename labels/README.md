# Human golden labels

Fill `golden_50_human.csv` yourself before the final evaluation. The six source columns are unchanged; fill only the seven answer columns. Do not use model-generated answers as human evidence. These answers never enter classification requests. Avoid consulting stars when interpreting the text.

| Column | How to label |
|---|---|
| topic | access, usability, playback, downloads, catalog, billing, support, other |
| intent | cancellation, complaint, request, praise, unclear; use that precedence |
| sentiment | −1 strongly negative, −0.5 negative, 0 neutral/unclear/balanced, 0.5 positive, 1 strongly positive; intermediate values permitted |
| severity | Integer 1–5, determined from reported impact |
| entities | JSON array of product/feature terms actually present, e.g. `["offline"]`; use `[]` when none |
| evidence_quote | Copy an exact source substring supporting the main label; do not rephrase |
| needs_review | `true` or `false`; mark missing context, ambiguity or language uncertainty |

Primary-topic rules: highest-severity supported specific problem; first mentioned on a tie. For praise, first specific praised feature. General praise/criticism is other. A paying customer reporting crashes is playback, not billing; a subscription that fails to activate is billing. Premium-only restrictions are billing. Topic boundaries appear in `specs/GRADING_CONTRACT.md`.

| Severity | Meaning | Illustrative text (not a dataset quote) |
|---|---|---|
| 1 | No problem; praise, unclear, neutral or pure request | “Please add a sleep timer.” |
| 2 | Annoyance or generic criticism without supported functional loss | “The new colors are ugly.” |
| 3 | Degraded/restricted function, use or workaround remains | “Search is slow, but I can still play my playlists.” |
| 4 | Core task clearly blocked | “I cannot log in at all.” |
| 5 | Explicit serious financial, privacy or data harm | “All my saved playlists were permanently deleted.” |

“I am uninstalling because this app is annoying” expresses cancellation, but does not establish severity 4 or 5. A bare boycott slogan is unclear unless a personal departure or product complaint is expressed. Do not invent impact from anger.

Evaluation plan: topic/intent agreement and confusion counts; severity exact agreement and MAE; sentiment MAE; ambiguous-case count; exact quote substring tests plus manual support inspection; unsupported entity inspection; assess needs_review as a prediction. Missing predictions stay in the denominator. If golden results influence changes, disclose the tuning and add fresh held-out examples. The first frozen evaluation is complete: [results and calibration review](../reports/golden50/report.md). Original human labels remain unchanged; any correction must preserve a versioned snapshot and reason.

