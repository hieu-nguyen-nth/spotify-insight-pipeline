"""Persist checked analysis and dashboard artifacts locally without inference."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from .core import ROOT,atomic_json,course,valid_record
from .lean import CONTROL,control
from .analysis import ranking

def csv_rows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))

def save(outdir,control_path=CONTROL):
    out=Path(outdir);run=json.loads((out/'enrichment_run.json').read_text())
    records=json.loads((out/'records.json').read_text());scope=run['scope'];cfg=run['label_config']
    if run['stop_reason']!='completed' or len(records)!=run['nonempty_reviews']:
        raise ValueError('Persist a complete, explicit analysis scope only.')
    if len({r['review_id'] for r in records})!=len(records):raise ValueError('Duplicate analysis IDs.')
    db=control(control_path)
    try:
        for record in records:
            saved=db.execute('SELECT * FROM lean_parts WHERE scope=? AND label_config=? AND review_id=?',(scope,cfg,record['review_id'])).fetchone()
            if not saved or json.loads(saved['part_json']).get('record')!=record:
                raise ValueError('Analysis records differ from committed classifier outputs.')
            valid_record(record,saved)
        membership,ranked,claims=ranking(records)
        for name,expected in [('membership.csv',membership),('ranking.csv',ranked),('claims.csv',claims)]:
            actual=csv_rows(out/name)
            wanted=[{k:str(v) for k,v in row.items()} for row in expected]
            if actual!=wanted:raise ValueError('Saved arithmetic differs from records: '+name)
        pack=json.loads((out/'aggregate_evidence.json').read_text());recommendations=json.loads((out/'recommendations.json').read_text())
        lookup={r['review_id']:r for r in records};claim_lookup={c['claim_id']:c for c in claims}
        ranked_lookup={r['issue_id']:r for r in ranked}
        if len(pack['issues'])!=len(ranked) or {i['issue_id'] for i in pack['issues']}!=set(ranked_lookup):
            raise ValueError('Evidence-pack issue IDs differ from ranking.')
        for issue in pack['issues']:
            if any(issue.get(k)!=v for k,v in ranked_lookup[issue['issue_id']].items()):
                raise ValueError('Evidence-pack metrics differ from ranking.')
            for evidence in issue['evidence']:
                record=lookup[evidence['review_id']]
                if 'issue_'+record['topic']!=issue['issue_id'] or evidence['quote'] not in record['evidence_quote']:
                    raise ValueError('Dashboard evidence differs from its source issue.')
        for recommendation in recommendations:
            if any(claim_lookup[c]['issue_id']!=recommendation['issue_id'] for c in recommendation['claim_ids']):
                raise ValueError('Recommendation cites another issue metric.')
            if any('issue_'+lookup[rid]['topic']!=recommendation['issue_id'] for rid in recommendation['evidence_review_ids']):
                raise ValueError('Recommendation cites another issue source.')
        profile=json.loads((out/'ingestion_report.json').read_text())['profile']
        analysis_run=json.loads((out/'analysis_run.json').read_text()) if (out/'analysis_run.json').exists() else {}
        full=analysis_run.get('is_full_corpus',False)
        if full and (len(records)!=660609 or profile['counts']['records']!=660622 or profile['counts']['empty_review_text']!=13):
            raise ValueError('Full dashboard requires all nonempty source outputs and the exact source profile.')
        verification=None
        subset=json.loads((out/'scope_manifest.json').read_text()) if (out/'scope_manifest.json').exists() else None
        if subset:
            from .subset import saved_review
            integrity=saved_review(db)
            if integrity['status']!='pass' or integrity['completed_count']!=len(records) or course.sha(out/'records.json')!=subset['records_sha256']:
                raise ValueError('Check the frozen completed subset before saving it.')
        if full:
            from .artifact_review import saved_full_review
            verification=saved_full_review(db)
        quarantined=13 if full else 0
        bundle={'dataset':{'scope':scope,'is_full_corpus':full,'analysis_count':len(records)+quarantined,
                           'source_sha256':profile['file_sha256'],'label_config':cfg},
                'overview':{'completed':len(records),'quarantined_in_analysis':quarantined,
                            'intent_counts':dict(Counter(r['intent'] for r in records)),
                            'topic_counts':dict(Counter(r['topic'] for r in records)),
                            'severity_counts':dict(Counter(str(r['severity']) for r in records)),
                            'needs_review_count':sum(r['needs_review'] for r in records)},
                'ranking':ranked,'claims':claims,'issue_evidence':pack['issues'],'recommendations':recommendations,
                'limitations':[('All supplied source rows accounted for; empty texts quarantined.' if full else 'Development checkpoint, not full-corpus results.'),'Broad topic groups are not root-cause clusters.',
                               'Sentiment is local VADER; human agreement diagnostics remain separate.',
                               'Local AI prose was reviewed against source quotes; editorial corrections are disclosed.']}
        if verification:
            bundle['verification']=verification
            if not verification['checker_passed']:
                bundle['limitations'].append('Instructor checker remains review_required solely because usage is unavailable on the documented failed request. Mechanical coverage and ranking checks passed; failed-request usage and API cost status are disclosed separately.')
        if subset:
            bundle['dataset'].update(scope_mode='user_stopped_subset',source_corpus_rows=subset['source_corpus_rows'],
              source_nonempty_reviews=subset['source_nonempty_reviews'],source_corpus_sha256=subset['source_corpus_sha256'],uncompleted_nonempty_reviews=subset['uncompleted_nonempty_reviews'])
            bundle['limitations'][0]=subset['limitations']
            bundle['limitations'].append('All 660,622 source rows were ingested; 13 empty texts are quarantined separately from this analysis. The original full-source checker remains review_required for missing outputs and unavailable failed-request usage; no full-corpus pass is claimed.')
            bundle['verification']={'completed_subset_integrity':integrity['status'],'checker_status':integrity['instructor_checker_status'],
              'issue_counts':integrity['instructor_checker_issue_counts'],'full_source_coverage':integrity['full_source_coverage'],'cost_status':'provisional_pending_failed_request_reconciliation'}
        artifacts={'dashboard':bundle,'ranking':ranked,'claims':claims,'recommendations':recommendations,
                   'aggregate_evidence':pack,'memo':(out/'memo.md').read_text()}
        db.executescript('''CREATE TABLE IF NOT EXISTS stored_analysis(
             scope TEXT NOT NULL, artifact_kind TEXT NOT NULL, sha256 TEXT NOT NULL, artifact_json TEXT NOT NULL,
             PRIMARY KEY(scope,artifact_kind));
             CREATE TABLE IF NOT EXISTS stored_membership(
             scope TEXT NOT NULL,review_id TEXT NOT NULL,issue_id TEXT NOT NULL,PRIMARY KEY(scope,review_id));''')
        db.execute('BEGIN IMMEDIATE')
        try:
            for kind,value in artifacts.items():
                raw=course.canonical(value);digest=hashlib.sha256(raw.encode()).hexdigest()
                db.execute('INSERT OR REPLACE INTO stored_analysis VALUES(?,?,?,?)',(scope,kind,digest,raw))
            db.execute('DELETE FROM stored_membership WHERE scope=?',(scope,))
            db.executemany('INSERT INTO stored_membership VALUES(?,?,?)',[(scope,r['review_id'],r['issue_id']) for r in membership]);db.commit()
        except BaseException:db.rollback();raise
        atomic_json(out/'dashboard.json',bundle)
        return {'scope':scope,'stored_artifacts':len(artifacts),'stored_membership_rows':len(membership),'completed_records':len(records),'new_model_calls':0,'database':'local shared SQLite; live deployment pending'}
    finally:db.close()
