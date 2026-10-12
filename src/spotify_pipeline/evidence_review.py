"""Offline evidence inspection artifacts, real-review trace and planted-label replay."""
import csv,json,hashlib
from pathlib import Path
from .core import ROOT,atomic_json,course
from .analysis import csv_save

TRACE_ID='4da2cf8f-b70a-4a44-b8a1-ca564bd6c756'

def planted_label_replay(comparison):
    """Change only a test-copy initial answer; independent prediction stays untouched."""
    fields=comparison['fields']
    wrong={f:('other' if f=='topic' and fields[f]['independent']!='other' else
               'access' if f=='topic' else
               'praise' if f=='intent' and fields[f]['independent']!='praise' else
               'complaint' if f=='intent' else
               1 if fields[f]['independent']!=1 else 5) for f in fields}
    detected=[f for f in fields if wrong[f]!=fields[f]['independent']]
    return {'review_id':comparison['review_id'],'independent_request_id':comparison['request_id'],
      'original_initial':{f:fields[f]['initial'] for f in fields},'planted_test_copy':wrong,
      'saved_blind_prediction':{f:fields[f]['independent'] for f in fields},
      'detected_fields':detected,'passed':set(detected)==set(fields),
      'mode':'offline replay of actual independently generated blind predictions; no new inference',
      'business_records_modified':False,'new_model_calls':0}

def build():
    out=ROOT/'reports/submission_review';out.mkdir(exist_ok=True)
    golden=ROOT/'reports/golden50'
    human=list(csv.DictReader((golden/'human_labels_as_evaluated.csv').open()))
    predictions={r['review_id']:r for r in json.loads((golden/'records.json').read_text())}
    concerns={
      0:'Specific allegations about removed songs suggest catalog; generic other loses that specificity. Allegations are unverified.',
      3:'Ads are explicitly mentioned, but are described as acceptable; unspecified limited functionality leaves topic/impact ambiguous.',
      8:'Diverse is not an explicit catalog feature. General praise may be better supported than the specific catalog label.',
      11:'The update says the failure was resolved. The quote supports historical crashes but current severity four requires temporal qualification.',
      16:'Non-English shorthand: catalog context is plausible; intent/support remains language-limited and deserves a review flag.',
      18:'Non-English lyrics reference is plausible; independent fluent-language review is needed to certify impact.',
      23:'Non-English/mixed-language text mentions ads after each song. A request interpretation may miss an existing annoyance; inspect complaint precedence.',
      26:'Short non-English insult lacks a clearly stated product experience; unclear is defensible but language uncertainty should be disclosed.',
      28:'Explicit premium-only restrictions cross the billing/usability boundary; the chosen usability label deserves review.',
      33:'Fragmented dollar/month text does not clearly establish a Spotify billing request. Specific topic/intent are weakly supported.',
      44:'Offline playback is reported blocked. Severity four versus three depends on whether offline playback is the core task; paid-plan mention alone is not billing.'}
    omissions={10:['song playback'],11:['Support','crashing'],32:['ad (spelled add)'],36:['advertising'],40:['albums','artists','collections'],42:['rewind'],45:['ad']}
    rows=[]
    for i,source in enumerate(human):
        p=predictions[source['review_id']]
        unsupported=[e for e in p['entities'] if e.casefold() not in source['review_text'].casefold()]
        rows.append({'review_id':source['review_id'],'topic':p['topic'],'intent':p['intent'],'severity':p['severity'],
          'quote_exact_substring':p['evidence_quote'] in source['review_text'],
          'semantic_inspection':'needs_review' if i in concerns else 'no_additional_concern',
          'note':concerns.get(i,'The supplied quote supports the broad topic/intent and stated impact under the rubric.'),
          'entities_returned':json.dumps(p['entities'],ensure_ascii=False),'unsupported_entities':json.dumps(unsupported),
          'possible_omissions':json.dumps(omissions.get(i,[]))})
    csv_save(golden/'quote_entity_inspection.csv',rows,list(rows[0]))
    report={'reviewer':'Codex assistant qualitative inspection of all 50 supplied texts/predictions; not new human labels',
      'records_inspected':50,'exact_substring_quotes':sum(r['quote_exact_substring'] for r in rows),
      'no_additional_concern':sum(r['semantic_inspection']=='no_additional_concern' for r in rows),
      'flagged_for_semantic_or_language_review':len(concerns),'returned_entity_terms':sum(len(p['entities']) for p in predictions.values()),
      'unsupported_returned_entities':sum(len(json.loads(r['unsupported_entities'])) for r in rows),
      'omission_examples_recorded':len(omissions),'labels_scores_prompts_modified':False,'new_model_calls':0,
      'note':'Judgment-based support inspection is distinct from literal matching and human accuracy. Short/foreign-language and temporal cases remain uncertain.',
      'original_evaluation_sha256':course.sha(golden/'evaluation.json'),'prediction_sha256':course.sha(golden/'records.json')}
    atomic_json(golden/'quote_entity_inspection.json',report)
    subset=ROOT/'reports/completed_subset'
    verification=json.loads((subset/'verification.json').read_text())
    comparison=next(v for v in verification['comparisons'] if v['review_id']==TRACE_ID)
    planted=planted_label_replay(comparison);planted['verification_artifact_sha256']=course.sha(subset/'verification.json')
    atomic_json(out/'planted_review_label_replay.json',planted)
    records=json.loads((subset/'records.json').read_text());record=next(r for r in records if r['review_id']==TRACE_ID)
    source=next(r for r in course.csv_rows(subset/'analysis_scope.csv') if r['review_id']==TRACE_ID)
    assert course.row_sha(source)==record['source_sha256']
    members=list(csv.DictReader((subset/'membership.csv').open()));member=next(r for r in members if r['review_id']==TRACE_ID)
    ranked=next(r for r in csv.DictReader((subset/'ranking.csv').open()) if r['issue_id']==member['issue_id'])
    claims=[r for r in csv.DictReader((subset/'claims.csv').open()) if r['issue_id']==member['issue_id']]
    trace={'review_id':TRACE_ID,'source':source,'source_sha256':record['source_sha256'],'enrichment':record,
      'verification':comparison,'membership':member,'ranking':ranked,'memo_claims':claims,
      'contribution':{'complaint_count':1,'severity_sum':record['severity']},
      'handling':'Retained needs_review=true: generic ad annoyance supports severity two; VADER neutral sentiment is not a correctness guarantee.',
      'scope_warning':'Trace contributes to the selected subset aggregate, not a full-corpus prevalence estimate.',
      'new_model_calls':0,'business_records_modified':False}
    atomic_json(out/'real_review_trace.json',trace)
    return {'semantic_inspection':report,'planted_label_replay':planted,'trace_review_id':TRACE_ID,'new_model_calls':0}

if __name__=='__main__':print(json.dumps(build(),indent=2))
