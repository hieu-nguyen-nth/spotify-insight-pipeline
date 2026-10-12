# One actual review through the complete pipeline

Review `4da2cf8f-b70a-4a44-b8a1-ca564bd6c756`: “Tooo many ads...it is user experience of 4 years”. Its full six-field original row hashes to `8ea655ee001a979dfe089f39e72d0ef94fe6596e0841a703d0d7fcd98c22a56d`; source metadata and exact quote were preserved. [Structured trace](real_review_trace.json) includes the source, validated record and actual request IDs.

| Stage | Saved result |
|---|---|
| Enrichment | Jev v3 topic usability, intent complaint, severity 2; local VADER sentiment 0.0, entity ads, needs_review=true. Topic/intent request 6747716d-6d5b-46a9-8586-ea7f373caa08; severity request a1c2a733-6642-4a95-848f-905d2324c35e. |
| Independent verification | Blind request c5e4eb08-4c69-46cc-96db-89f14e397999 received original text/rubric, without the first answer. Topic, intent and severity all agreed. This does not prove human accuracy. |
| Membership and aggregation | Saved member of issue_usability; contributes one complaint and two severity points. |
| Ranking | Usability rank 1: 5,862 members, integer severity sum/priority 15,949; mean severity 2.720744. Other members and the tie-break are reproducible from saved outputs. |
| Memo | The usability recommendation cites issue_usability_complaint_count, issue_usability_priority_score and the mean comparison cites issue_usability_mean_severity. This review contributes to those aggregates; the memo's illustrative quote is separately identified and does not claim this review reports background playback. |

Handling: retain needs_review=true; VADER's neutral score does not negate the explicit ad complaint. The ad annoyance supports minor-impact severity two. No initial labels were rewritten. The [planted-label replay](planted_review_label_replay.json) changes only a test copy to other/praise/1 and detects all three wrong fields against the already-saved blind prediction. It performs no fresh inference and changes no business aggregates.

An ambiguous case is `4327188d-1316-4de0-b330-7d64435b3fc5`: “So far good ...once I get it work with my Garmin ot would be great”. The original classified usability/request/1; blind request 10a5aa1c-5b26-4ef3-8b23-f65493778eda returned other/complaint/3. Garmin integration is desired, but a concrete failing operation is not described. The saved editorial decision preserves both answers, flags the ambiguity and does not silently substitute the verifier result. [Eight inspected disagreements](../completed_subset/verification_review.json) also disclose clearer complaint-precedence misses. Selection is completion-based; neither example establishes full-corpus prevalence.
