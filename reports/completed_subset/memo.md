# Spotify completed-subset decision memo

Investigate usability and playback together before allocating next-quarter product effort. Usability remains first in the required baseline for this completed subset, but the lead is sensitive to records marked for review. Usability has priority 15,949 across 5,862 complaint/cancellation reviews; playback has priority 15,278 across 4,157, with higher mean severity (3.675247 [issue_playback_mean_severity] versus 2.720744 [issue_usability_mean_severity]). Billing follows with priority 4,906 across 1,656 reviews. These are broad topic totals, not counts of any particular defect.

Scope: 244,582 completed original reviews from the stopped run. All 660,622 source rows were ingested; 13 empty texts were quarantined and 416,027 nonempty reviews have no complete classification. The subset was selected by completion status, not randomly: many complaint/cancellation reviews still need severity. The ranking describes the 15,825 classified complaint/cancellation reviews and must not be presented as Spotify-wide priorities.

The baseline priority is the integer sum of severity, equivalent to complaint_count × mean_severity before display rounding. Ties use ascending issue ID. Every contributing review ID is saved in membership.csv.

Usability leads playback by 671 priority points, or 4.4% of playback's baseline score. A separate [needs-review sensitivity diagnostic](ranking_sensitivity.md) excludes flagged records without changing the baseline: playback scores 9,792 and usability 7,482. There are 7,518 flagged complaint/cancellation reviews out of 15,825 (47.5%). This exclusion has its own selection bias and is not a corrected ranking; it shows that the first-place choice is not stable under this policy. All diagnostic numbers are reproducible from [ranking_sensitivity.json](ranking_sensitivity.json), separately from baseline claims.csv.

Blind verification: 1,000 completed reviews, 193 with at least one differing field. Topic agreement is 90.7%, intent 92.8%, severity 92.3%; severity mean absolute difference is 0.099. These compare two model tasks, not model accuracy against humans. Eight disagreements were inspected; some help requests describe explicit failures and expose a complaint-precedence weakness. Original labels remain unchanged. Golden human evaluation remains separately reported. Its 68% topic agreement is against the original student labels. After inspecting disagreements, the student labeler reports accepting the model's topic for the majority of disputed cases and continued with the frozen classifier. This qualitative judgment is not a rescored or independently adjudicated accuracy result; original labels and diagnostics remain intact.

## Evidence-grounded investigation candidates

The following symptoms are supported by selected source examples. Their broad-topic totals do not establish how common each symptom is, and no symptom-specific membership/count is claimed.

### issue_usability
Review background playback and exit controls. A cited reviewer reports unwanted background playback and concerns about permissions.

Broad group count: 5862 [issue_usability_complaint_count]; priority: 15949 [issue_usability_priority_score].

Original review ID: 183a4585-a071-467d-80d4-316bdcaa8a4c
> I would like to EXIT Spotify to when I close the app. Instead it keeps playing in the background. I continually have to find the app, scroll thru 50 settings to exit the app. I understand why Spotify does that..... As long as the app is open, Spotify can see all your contacts, texts, Personal data, etc. Spotify, keep your nose out of my phone and exit the app when I say so, not when you want

### issue_playback
Investigate crashes and account-security concerns. A cited reviewer reports crashes and alleges an account breach; neither is independently verified.

Broad group count: 4157 [issue_playback_complaint_count]; priority: 15278 [issue_playback_priority_score].

Original review ID: 450434fc-6242-4c3d-b688-89a11f43bf71
> The apps keeps crashing for some reason. Also account got data breached last time, talk about broken security.

### issue_billing
Review post-cancellation charges and dispute handling. A cited reviewer reports a charge after cancellation.

Broad group count: 1656 [issue_billing_complaint_count]; priority: 4906 [issue_billing_priority_score].

Original review ID: 01bc38c1-0d0b-4716-a3ed-a7fc3a0aa362
> It charged me after I canceled my plan long story short don't put your card on here

## Limits and wording review

Local Qwen generated issue names and recommendation drafts; code rendered the cited metrics. Editorial review produced this final memo, removed unsupported frequency/causal wording, and kept alleged privacy/security or billing harms unverified. The joint investigation priority and sensitivity discussion are post-run editorial additions using saved records, with no new model calls. Raw AI memo/recommendations and provider responses are retained. Selected examples were chosen by severity then original ID; they are not representative defect samples. These historical, self-selected reviews provide no observed revenue loss, confirmed cancellation, causal churn or verified breach evidence. Validate reproducible cases before committing a product roadmap.
