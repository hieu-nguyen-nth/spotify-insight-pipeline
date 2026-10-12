# Frozen golden-50 evaluation · October 11, 2026

**Student review complete: proceed with the frozen configuration to the measured 500-review checkpoint.** The frozen optimized candidate produced all 50 predictions in 0.384 seconds through two actual Jev requests, with calculated API usage of **$0.000453810**, below the approved $0.003 cap. It used 49 distinct texts and one exact-text alias. Original IDs and hashes are retained. The source was the original unlabeled golden CSV; human answers never entered provider requests. The chosen configuration was frozen before scoring and has not been changed in response to these answers.

| Diagnostic against student human labels | Measured result |
|---|---:|
| Topic agreement | 34/50 · 68% |
| Topic macro F1, all eight labels | 0.3144 |
| Intent agreement | 46/50 · 92% |
| Intent macro F1, all five labels | 0.8036 |
| Severity exact agreement | 38/50 · 76% |
| Severity mean absolute error | 0.24 on the 1–5 scale |
| Sentiment mean absolute error | 0.4739 on the −1 to +1 scale |
| Needs-review agreement | 36/50 · 72% |
| Exact source substring quotes | 50/50 |

This is the student's independent benchmark, not the instructor's private benchmark. Downloads and support have zero human-labeled examples; their zero F1 values are included in the declared eight-label macro average. Small class counts limit class-level conclusions. Exact quote matching checks provenance, not semantic support; entity omissions and quote support still need manual review. The sentiment result suggests that local VADER is insufficiently aligned with these human judgments, Language and mixed-sentiment behavior still need inspection.

[Calibration review](calibration_review.csv) contains the 26 rows with a topic, intent or severity difference. Five human labels give severity above 1 to `request` or `unclear`; review their text and intent against the shared no-problem/pure-request rule. Human labels have been preserved unchanged in [the evaluated snapshot](human_labels_as_evaluated.csv). The model also assigns specific topics to some generic praise and confuses topic boundaries. Disagreements are review candidates, not proof that either side is correct.

Keep [the original score](evaluation.json), [frozen provenance](evaluation_provenance.json), [saved-payload validation](payload_integrity.json), raw handoffs and predictions. Any later correction of human labels needs an explicit version and reason, while retaining this score. Any model tuning informed by these golden answers must be disclosed and evaluated on a fresh human-labeled holdout excluded from prompts/examples. Do not rerun the same benchmark and present it as an untouched holdout.

Student decision: [review annotation](student_review_decision.json). Topic agreement depends on how the human labeler interprets the review and applies the shared rubric; a disagreement is not automatically a model error. The student who supplied these labels reports that, after inspecting the disputed cases, they agree with the model's topic classification for the majority of topic disagreements. That review was the reason for accepting the frozen classifier and continuing the experiment. Differences included unfamiliar-language/phrase interpretation and human topic omissions. This is a qualitative labeler judgment, not a new case-level adjudication or corrected accuracy estimate: no exact accepted-case tally was supplied, and the original 34/50 (68%) agreement remains reported. Human labels, predictions, model configuration and scores were not changed. Severity, sentiment and language limitations remain separate from this topic judgment.

A subsequent [assistant quote/entity inspection](quote_entity_inspection.json) reviewed all 50 actual texts without changing labels, prompts or the original scores. [Per-case notes](quote_entity_inspection.csv) flag 11 semantic, temporal or language concerns and seven entity-omission examples; no unsupported returned literal entity was found. This is qualitative assistant review, not additional human ground truth or a revised accuracy result.
