# Pipeline architecture and achieved scope

```mermaid
flowchart TD
  CSV[Full source: 660,622 original rows] --> PREP[Python/SQL: parse, hash, profile, deduplicate]
  PREP --> SOURCE[(Local source database and 13 empty quarantines)]
  PREP --> QUEUE[Pending IDs derived from persisted state]
  QUEUE --> TOPIC[Jev: bounded topic and intent choices]
  TOPIC --> SEVERITY[Jev: severity for complaint/cancellation]
  TOPIC --> RULE[Code: severity one for no-problem intents]
  SEVERITY --> SAVE[Validate IDs, schema and quotes; save atomically]
  RULE --> SAVE
  SAVE --> STATE[(Shared SQLite: results, partials, calls, rate/spend reservations)]
  STATE --> FREEZE[User stop: freeze 244,582 completed originals]
  FREEZE --> VERIFY[Separate blind Jev task: 1,000 completed reviews]
  VERIFY --> DIAG[Code comparison; retain both predictions and inspect disagreements]
  FREEZE --> GROUP[Code: 15,825 complaint/cancellation memberships and aggregates]
  GROUP --> RANK[Code: integer severity sums; stable issue-ID ties]
  RANK --> QWEN[Local Qwen: bounded issue names and cited recommendations]
  QWEN --> REVIEW[Review claims and quotes; retain raw AI and editorial corrections]
  DIAG --> CHECK[Subset integrity and unchanged full-source checker]
  REVIEW --> CHECK
  CHECK --> EXPORT[grading/ and cost/ with scope and unknown usage disclosed]
  CHECK --> DB[(Supabase Free: private processed rows and stored analysis)]
  DB --> API[Vercel Python backend: published saved dashboard artifact]
  API --> UI[Dashboard: metrics, rankings, reviewed recommendations and source examples]
```

The orchestrator owns input/output paths, record accounting, validation, cache keys, pending work, checkpointing, request admission and budgets. Models judge bounded language; code owns arithmetic. Exact-text reuse matches model, effort, prompt and schema and retains direct original provenance. The measured pilot demonstrates real interruption/resume and zero-call warm replay. One worker was used for paid business classification. A separate authorized live benchmark tested one and two workers under the same limits/cache conditions: peak 1/2, 20.29/19.35 seconds, equal consumption. Its single-trial time difference is not a sustained pipeline speedup; no provider Batch discount is claimed.

The common stage handoffs are saved review IDs/text plus rubric → validated labels → blind predictions/disagreements → membership and aggregates → deterministic ranking/claims → bounded metrics and quote packs → raw AI and reviewed recommendations. Local sentiment uses pinned VADER. Source ratings are metadata, and human golden answers never enter model payloads.

Requests contain at most 50 reviews. Shared transactional rate/spend reservations precede network I/O. Known project API usage plus the separately authorized $0.05 unknown-charge hold stays within $4.80. A new unknown charge stops dispatch. There are zero stronger-model fallbacks. The saved production run used no automatic retries; the revised dispatcher caps known-usage invalid/transient retries at one with backoff/jitter, while unknown outcomes stop admission. Tests use isolated transport fixtures; the actual paid transient failure and its still-unknown charge remain disclosed. Actual failed attempts are retained, not converted into successes or zero usage.

The user requested stopping after the current request. A tested SQLite admission gate blocked increasing reservations while allowing the in-flight request to settle. The worker saved its results and removed its own lock; no in-flight request was signaled. The gate then became an explicit stopped `enrich` role, permitting only the already-authorized verification and local analysis. Scheduled follow-ups are paused. Classification does not resume automatically after billing reconciliation.

Full-file ingestion and completed analysis are different scopes. The stopped subset contains completed originals only; partial outputs and unexpanded duplicate aliases remain outside the final analysis. Selection depends on intent and execution stage, so it is not representative. The unchanged full-source checker reports missing outputs and unavailable usage. Subset integrity checks verify source/provenance/arithmetic but do not certify semantic accuracy or award a grade.

Supabase stores every completed subset row privately and saves six analysis artifacts. Public access is limited to published aggregates and selected quotes. The backend uses a publishable read key; no model key, database-admin URI or password is deployed. Dashboard visits read saved data and do not run inference. Client COPY uploads are resumable and measured against a 450 MiB safety stop; no paid upgrade is authorized.

The [post-run editorial review](reports/completed_subset/ranking_sensitivity.md) uses saved records to test sensitivity to `needs_review` flags. It changes neither required baseline nor classifications and introduces no model calls. The revised memo recommends investigating usability and playback together because the first-place group changes in this diagnostic. Current repository prose and the [revision manifest](submission/review_revision_manifest.json) are later than the frozen v1.0.0 execution package; the live dashboard retains its original baseline artifacts.

Topic agreement is measured against the original student labels. The student reports accepting the model topic for most disputed cases after reviewing the disagreements, which motivated continuing with the frozen configuration. This qualitative review is recorded separately from original scores and does not constitute a new accuracy measurement.
