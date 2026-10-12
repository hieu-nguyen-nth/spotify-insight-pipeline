# Spotify completed-subset decision memo

Investigate usability and playback together before allocating next-quarter product effort. Usability remains first in the required baseline for this completed subset, but the lead is sensitive to records marked for review. Usability has priority 15,949 across 5,862 complaint/cancellation reviews; playback has priority 15,278 across 4,157, with higher mean severity (3.675247 [issue_playback_mean_severity] versus 2.720744 [issue_usability_mean_severity]). Billing follows with priority 4,906 across 1,656 reviews. These are broad topic totals, not counts of any particular defect.

Scope: 244,582 completed original reviews from the stopped run. All 660,622 source rows were ingested; 13 empty texts were quarantined and 416,027 nonempty reviews have no complete classification. The subset was selected by completion status, not randomly: many complaint/cancellation reviews still need severity. The ranking describes the 15,825 classified complaint/cancellation reviews and must not be presented as Spotify-wide priorities.

The baseline priority is the integer sum of severity, equivalent to complaint_count × mean_severity before display rounding. Ties use ascending issue ID. Every contributing review ID is saved in membership.csv.

Usability leads playback by 671 priority points, or 4.4% of playback's baseline score. A separate [needs-review sensitivity diagnostic](ranking_sensitivity.md) excludes flagged records without changing the baseline: playback scores 9,792 and usability 7,482. There are 7,518 flagged complaint/cancellation reviews out of 15,825 (47.5%). This exclusion has its own selection bias and is not a corrected ranking; it shows that the first-place choice is not stable under this policy. All diagnostic numbers are reproducible from [ranking_sensitivity.json](ranking_sensitivity.json), separately from baseline claims.csv.

Blind verification: 1,000 completed reviews, 193 with at least one differing field. Topic agreement is 90.7%, intent 92.8%, severity 92.3%; severity mean absolute difference is 0.099. These compare two model tasks, not model accuracy against humans. Eight disagreements were inspected; some help requests describe explicit failures and expose a complaint-precedence weakness. Original labels remain unchanged. Golden human evaluation remains separately reported. Its 68% topic agreement is against the original student labels. After inspecting disagreements, the student labeler reports accepting the model's topic for the majority of disputed cases and continued with the frozen classifier. This qualitative judgment is not a rescored or independently adjudicated accuracy result; original labels and diagnostics remain intact.

## Evidence-grounded investigation candidates

The following symptoms are supported by three selected source examples per broad group. The examples were selected by severity then original ID, and do not establish symptom prevalence. [Recommendation evidence](../result_review/recommendation_evidence.csv) verifies all nine review memberships and exact saved quotes.

### issue_usability
Investigate exit, navigation and local-file controls. Three selected reviews describe background playback/exit controls, zoomed navigation and unexpected local-file handling.

Broad group count: 5862 [issue_usability_complaint_count]; priority: 15949 [issue_usability_priority_score]. These totals are not counts of the symptoms below.

Original review ID: 183a4585-a071-467d-80d4-316bdcaa8a4c
> I would like to EXIT Spotify to when I close the app. Instead it keeps playing in the background. I continually have to find the app, scroll thru 50 settings to exit the app. I understand why Spotify does that..... As long as the app is open, Spotify can see all your contacts, texts, Personal data, etc. Spotify, keep your nose out of my phone and exit the app when I say so, not when you want

Original review ID: 37c2d3d7-9ee2-45e4-83dd-2f6a22e798a4
> Why is everything so zoomed in now? It makes it much harder to use. Also, Spotify is recognizing audio files on my phone despite it not having permission to look at my files.

Original review ID: 4011e2d3-9eba-4a42-8dc6-f33f1b127946
> For some reason this app is now trying to open all of my personal audio without my permission and there is no option to stop it. It is not my default audio player and I can not open it any other way. Horrible.

### issue_playback
Investigate crashes, device connections and streaming data use. Selected reviews report crashes, unexpected device connections and unusually high mobile-data consumption.

Broad group count: 4157 [issue_playback_complaint_count]; priority: 15278 [issue_playback_priority_score]. These totals are not counts of the symptoms below.

Original review ID: 450434fc-6242-4c3d-b688-89a11f43bf71
> The apps keeps crashing for some reason. Also account got data breached last time, talk about broken security.

Original review ID: 82160961-72d8-47c1-b322-4257c94f0ab5
> Other devices has been connecting to my phone.. my bluetooth isnt even on.
> How is this even happening?

Original review ID: ab09a91d-546f-4b72-9e89-60105f3f529f
> Today I was driving and streaming some podcasts, and somehow Spotify managed to EAT UP 10 GBs OF DATA in less than 3 hours!! 10!!! Completely unacceptable 😡 Now I have very limited data left for 2 weeks until my next billing period.

### issue_billing
Review post-cancellation charges and dispute handling. Two selected reviews report charges after cancellation; another alleges an unauthorized charge. These reports require verification.

Broad group count: 1656 [issue_billing_complaint_count]; priority: 4906 [issue_billing_priority_score]. These totals are not counts of the symptoms below.

Original review ID: 01bc38c1-0d0b-4716-a3ed-a7fc3a0aa362
> It charged me after I canceled my plan long story short don't put your card on here

Original review ID: 0327424f-5ab1-42d7-aefa-b021dc049420
> Taking money out my bank without permission I'm ripping

Original review ID: 0c52d3c7-401e-4b55-b051-5837924840b3
> I cancelled my free trial but they still charged my credit card

## Limits and wording review

Local Qwen generated issue names and recommendation drafts; code rendered the cited metrics. Editorial review produced this final memo, removed unsupported frequency/causal wording, and kept alleged privacy/security or billing harms unverified. The joint investigation priority, sensitivity discussion and expansion to nine source examples are post-run editorial additions using saved records, with no new model calls. Sentiment does not enter the severity-sum priority formula; its documented errors do not drive this recommendation. Raw AI memo/recommendations and provider responses are retained. Selected examples were chosen by severity then original ID; they are not representative defect samples. These historical, self-selected reviews provide no observed revenue loss, confirmed cancellation, causal churn or verified breach evidence. Validate reproducible cases before committing a product roadmap.
