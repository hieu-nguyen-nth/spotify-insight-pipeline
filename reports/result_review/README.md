# Saved-result improvements · October 12, 2026

The completed scope remains **244,582 original reviews**. No classification, verifier or local generation was rerun. Source labels, original human answers, prompts, membership, ranking and baseline claims remain frozen. The dashboard and memo now recommend investigating usability and playback together, show the separate review-flag sensitivity scenario, and cite three saved examples per leading broad group. Symptoms are investigation candidates; neither the nine examples nor broad-topic totals measure defect prevalence.

[Recommendation evidence](recommendation_evidence.csv) links all nine selected quotes to original review IDs, issue membership, saved severity, review flags and source hashes. All nine references passed the offline audit. The `quote_json` CSV field preserves exact source text with JSON escaping, including original whitespace and line breaks. These are the existing high-severity examples, selected by severity then ID; they are not a random or representative sample. Privacy/security and charge allegations remain unverified.

## Case inspection without relabeling

[Case review](golden_case_review.json) includes all **16 topic disagreements** and the **ten largest sentiment errors** from the frozen human-50 set. Assistant observations are separate from the student's qualitative acceptance. No individual human decision is invented: `student_case_decision` remains null. The student's statement that most disputed model topics were accepted remains in [the original decision record](../golden50/student_review_decision.json). This explains continuation without asserting a new accuracy score. Original agreement stays **68%**.

Several disagreements follow explicit rubric boundaries: ads belong to usability; lyrics and recommendations belong to catalog; offline playback belongs to downloads. Other examples combine lyrics with seeking controls, ad volume with playback, or organization with catalog content. Short and non-English texts retain uncertainty. A case can be plausibly labeled differently under a one-topic rubric; these assistant observations are not independent human adjudication.

Sentiment MAE remains **0.4739** on −1 to +1. The error inspection finds:

| Saved case | Human / VADER | Observation |
|---|---:|---|
| `215463ae-95b7-4481-8747-1754b68f31fa` | −1 / +0.872 | Historical praise coexists with present playback failures. |
| `d2f3874f-d15d-4a2f-bb97-4f1213defa46` | −1 / +0.6808 | Expensive/unusable service is scored positively. |
| `1fc8b08f-7d6a-472f-b317-8ceb28d00f22` | +1 / −0.3595 | “No ads” is positive absence of a problem. |
| `723f07de-9881-4049-8680-1a9e25652914` | −0.25 / +0.8176 | A resolved update and an old failure mix different times. |
| `a972945c-6601-4108-882a-afe986866a7b` | +1 / 0 | One-word praise receives no sentiment. |

The full ten-case table retains exact source texts and measured errors. These are qualitative interpretations, not tested explanations of individual lexicon contributions. VADER sentiment is a diagnostic field, **not an input to issue priority**. The recommendation rests on complaint/cancellation membership, severity sums, source examples and the separately disclosed sensitivity scenario. Sentiment is not used to estimate churn, revenue or population satisfaction.

## Reproduce without model calls

From the current repository, add missing large evidence files from the v1.0.0 ZIP with `unzip -n`, then run:

```sh
python3 scripts/audit_saved_evidence.py --records grading/records.jsonl --out work/result_review_replay
```

Compare the three outputs with [checks.json](checks.json), [golden_case_review.json](golden_case_review.json) and [recommendation_evidence.csv](recommendation_evidence.csv). The audit validates golden source hashes, unchanged dashboard baseline fields, exact input-record SHA-256, all cited issue memberships and quotes. It calculates discrepancies against the preserved original answers; it performs no inference and changes no labels. Assistant interpretations are reproducible from [follow-up notes](../golden50/follow_up_case_notes.json).

[Original dashboard](../submission_review/dashboard_before_result_revision.json) and [original recommendations](../submission_review/recommendations_before_result_revision.json) preserve the pre-update presentation. The v1.0.0 archive and its original manifest remain historical execution evidence. Current live checks and revision hashes are recorded separately; the frozen full-corpus check remains `review_required`.
