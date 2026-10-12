"""Freeze and audit an explicitly user-stopped production subset; never classify."""
import csv
import json
import os
import shutil
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .core import ROOT,atomic_json,course,ingest,valid_record
from .lean import control,settings
from .analysis import jsonl_save,ranking

SCOPE='completed_subset'
OUT=ROOT/'reports'/SCOPE
INPUT=ROOT/'work/completed_subset_source.sqlite'
CSV=OUT/'analysis_scope.csv'
LIMIT='Completion-based subset, not a random sample. Praise/request/unclear records finished earlier; many complaints/cancellations remain without severity. Metrics and rankings apply only to these completed records.'

def freeze():
    """Offline only. Preserve exact saved records and every real call ID."""
    decision=json.loads((ROOT/'reports/scope_change/scope_decision.json').read_text())
    config,cfg=settings(50,'v3');db=control()
    try:
        if db.execute('SELECT 1 FROM run_locks').fetchone() or db.execute("SELECT 1 FROM calls WHERE outcome='in_flight'").fetchone():
            raise ValueError('Wait for the original worker and its last request to exit.')
        # Keep classification disabled while permitting the already-authorized verifier.
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR REPLACE INTO stopped_roles VALUES(?,?)',('enrich',decision['decision']))
        db.execute('DROP TRIGGER IF EXISTS user_requested_dispatch_stop');db.commit()
        records=json.loads((ROOT/'reports/full_run/records.json').read_text())
        if len(records)!=decision['completed_reviews'] or len({r['review_id'] for r in records})!=len(records):
            raise ValueError('The stopped worker export differs from the approved snapshot.')
        OUT.mkdir(exist_ok=True)
        if (OUT/'scope_manifest.json').exists():
            saved=json.loads((OUT/'scope_manifest.json').read_text())
            if saved['records_sha256']!=course.sha(OUT/'records.json') or saved['analysis_sha256']!=course.sha(CSV):
                raise ValueError('Frozen subset changed; refuse overwriting its provenance.')
            return saved
        db.execute('ATTACH DATABASE ? AS source',(str(ROOT/'work/full.sqlite'),))
        lookup={r['review_id']:r for r in records};seen=set()
        fd,tmp=tempfile.mkstemp(prefix='.scope-',dir=OUT)
        try:
            with os.fdopen(fd,'w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=course.FIELDS,extrasaction='ignore');writer.writeheader()
                query="""SELECT s.*,p.part_json FROM source.source_reviews s JOIN lean_parts p
                  ON p.review_id=s.review_id AND p.source_sha256=s.source_sha256
                  AND p.text_sha256=s.text_sha256 AND p.review_text=s.review_text
                  WHERE p.scope='full' AND p.label_config=? AND json_type(p.part_json,'$.record')='object'
                  ORDER BY s.source_order"""
                for row in db.execute(query,(cfg,)):
                    row=dict(row);part=json.loads(row.pop('part_json'));record=lookup[row['review_id']]
                    if part['record']!=record or record['label_config']!=cfg:raise ValueError('Frozen record differs from its committed original.')
                    valid_record(record,row)
                    if course.row_sha(row)!=record['source_sha256']:raise ValueError('Source row hash differs.')
                    writer.writerow(row);seen.add(record['review_id'])
                f.flush();os.fsync(f.fileno())
            if seen!=set(lookup):raise ValueError('Not every completed record matched the supplied source.')
            os.replace(tmp,CSV)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        shutil.copyfile(ROOT/'reports/full_run/records.json',OUT/'records.json')
        atomic_json(OUT/'configuration.json',config)
        db.execute('BEGIN IMMEDIATE')
        db.execute("INSERT OR IGNORE INTO lean_parts SELECT ?,label_config,review_id,source_sha256,text_sha256,review_text,part_json FROM lean_parts WHERE scope='full' AND label_config=? AND json_type(part_json,'$.record')='object'",(SCOPE,cfg))
        db.commit()
        profile=ingest(CSV,INPUT,OUT/'ingestion_report.json')
        frozen={'scope':SCOPE,'scope_mode':'user_stopped_subset','observed_at_utc':datetime.now(timezone.utc).isoformat(),
          'completed_reviews':len(records),'analysis_sha256':course.sha(CSV),'records_sha256':course.sha(OUT/'records.json'),
          'source_corpus_rows':660622,'source_nonempty_reviews':660609,'source_empty_quarantines':13,
          'source_corpus_sha256':decision.get('source_corpus_sha256',course.sha(Path(json.loads((ROOT/'reports/full/ingestion_report.json').read_text())['source']))),
          'uncompleted_nonempty_reviews':660609-len(records),'label_config':cfg,'selection_method':'All completed original records in the safely stopped full scope; no trimming to 100000 and no fabricated severity.',
          'limitations':LIMIT,'intent_counts':dict(Counter(r['intent'] for r in records)),
          'new_model_calls':0,'requirement_100000':'Option appears in supplied assignment; conflicting full-corpus wording and coverage grading disclosed.'}
        run_id='freeze-'+str(uuid.uuid4())
        run={'scope':SCOPE,'scope_mode':'user_stopped_subset','run_id':run_id,'stop_reason':'completed','pipeline_state':'frozen_completed_scope_downstream_pending',
          'label_config':cfg,'nonempty_reviews':len(records),'source_rows':len(records),'enrichment_completed':len(records),
          'paid_execution':False,'new_model_calls':0,'reused_saved_records':len(records),'pilot_cap_absolute_usd':4.8,
          'note':'Completed means this explicitly frozen subset is complete; original full run remains user-stopped and incomplete.'}
        atomic_json(OUT/'scope_manifest.json',frozen);atomic_json(OUT/'enrichment_run.json',run)
        atomic_json(OUT/'runs'/run_id/'run.json',run)
        atomic_json(OUT/'runs'/run_id/'checkpoint_after.json',{'completed_ids':sorted(lookup)})
        return frozen
    finally:db.close()

def audit():
    """Keep the unchanged instructor's full-source coverage findings visible."""
    manifest=json.loads((OUT/'scope_manifest.json').read_text())
    if course.sha(CSV)!=manifest['analysis_sha256'] or course.sha(OUT/'records.json')!=manifest['records_sha256']:
        raise ValueError('Frozen subset fingerprints changed.')
    records=json.loads((OUT/'records.json').read_text());db=control()
    try:
        if db.execute('SELECT 1 FROM run_locks').fetchone() or db.execute("SELECT 1 FROM calls WHERE outcome='in_flight'").fetchone():raise ValueError('Wait for active work.')
        db.execute('ATTACH DATABASE ? AS source',(str(ROOT/'work/full.sqlite'),))
        for record in records:
            source=db.execute('SELECT * FROM source.source_reviews WHERE review_id=?',(record['review_id'],)).fetchone()
            valid_record(record,source)
            if course.row_sha(source)!=record['source_sha256']:raise ValueError('Source metadata hash mismatch.')
            saved=db.execute('SELECT part_json FROM lean_parts WHERE scope=? AND label_config=? AND review_id=?',(SCOPE,manifest['label_config'],record['review_id'])).fetchone()
            if not saved or json.loads(saved[0])['record']!=record:raise ValueError('Committed classifier record mismatch.')
            for rid in record['model_request_ids']:
                call=db.execute('SELECT call_json FROM calls WHERE request_id=?',(rid,)).fetchone()
                if not call:raise ValueError('Missing real classifier call.')
                call=json.loads(call[0])
                if call['outcome']!='succeeded' or call['label_config']!=record['label_config'] or record['review_id'] not in call['review_ids'] or len(call['review_ids'])>50:
                    raise ValueError('Invalid classifier request provenance.')
        members,ranked,claims=ranking(records)
        for name,wanted in [('membership.csv',members),('ranking.csv',ranked),('claims.csv',claims)]:
            with (OUT/name).open(newline='') as f:got=list(csv.DictReader(f))
            if got!=[{k:str(v) for k,v in row.items()} for row in wanted]:raise ValueError('Ranking arithmetic mismatch: '+name)
        full=Path(json.loads((ROOT/'reports/full/ingestion_report.json').read_text())['source'])
        folder=ROOT/'grading';folder.mkdir(exist_ok=True)
        quarantines=[json.loads(line) for line in (ROOT/'reports/full/quarantine.jsonl').read_text().splitlines()]
        jsonl_save(folder/'records.jsonl',[*records,*quarantines])
        atomic_json(folder/'run.json',{'version':'a5-audit-v1','analysis_count':660622,'analysis_sha256':course.sha(full),
          'classification_input_fields':['review_text'],'allow_multi_issue':False,'scope':'User-stopped production; completed subset retained; full-source missing outputs intentionally disclosed.',
          'completed_subset_count':len(records),'completed_subset_sha256':manifest['analysis_sha256']})
        shutil.copyfile(ROOT/'reports/full/ingestion.json',folder/'ingestion.json')
        for name in ('membership.csv','ranking.csv','claims.csv'):shutil.copyfile(OUT/name,folder/name)
        shutil.copyfile(ROOT/'reports/pilot100_optimized/checkpoint_before.json',folder/'checkpoint_before.json')
        atomic_json(folder/'checkpoint_after.json',{'completed_ids':sorted(r['review_id'] for r in records)})
        ids={i for r in records for i in r['model_request_ids']}
        for directory in (ROOT/'reports/full_run/handoffs',OUT/'handoffs'):
            ids.update(p.name.removesuffix('_input.json') for p in directory.glob('*_input.json'))
        # Preserve the separately authorized live worker experiment as real attempts.
        # Its inputs are development source IDs; business classifications are unchanged.
        ids.update(json.loads(row[0])['request_id'] for row in db.execute(
            "SELECT call_json FROM calls WHERE json_extract(call_json,'$.experiment')='worker_comparison'"))
        calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls ORDER BY rowid') if json.loads(r[0])['request_id'] in ids]
        jsonl_save(folder/'calls.jsonl',calls)
        reference=course.reference(full,full)
        checked=course.audit(folder,reference,None,course.reference_hash(reference));atomic_json(OUT/'instructor_full_source_check.json',checked)
        require_expected_findings(checked,len(records),calls)
        integrity={'status':'pass','scope':'only the frozen completed subset','completed_count':len(records),'checks':['Original ID, exact source row hash and quote validation','Exact committed model result and real bounded-request provenance','Deterministic membership, ranking and claims recalculated from all completed records'],
          'instructor_checker_status':checked['status'],'instructor_checker_issue_counts':checked.get('issue_counts'),
          'full_source_coverage':checked['coverage'],'scope_limitations':LIMIT,'new_model_calls':0,
          'instructor_checker_sha256':course.sha(ROOT/'vendor/check_submission.py'),
          'checker_report_sha256':course.sha(OUT/'instructor_full_source_check.json'),
          'grading_sha256':{p.name:course.sha(p) for p in folder.iterdir() if p.is_file()}}
        atomic_json(OUT/'subset_integrity.json',integrity)
        return integrity
    finally:db.close()

def require_expected_findings(checked,count,calls):
    coverage=checked.get('coverage',{})
    if any(coverage.get(k)!=v for k,v in {'expected':660622,'valid_completed':count,'quarantined':13,
      'missing':660609-count,'duplicate_ids':0,'invalid_or_unresolved':0}.items()):
        raise ValueError('Instructor coverage differs from the explicit stopped subset.')
    missing_usage=[c for c in calls if any(type(c.get(f)) is not int for f in ('input_tokens','output_tokens'))]
    approved='03cb9c58-d8c1-4500-864e-4b9049ddbe6d'
    if any(c['request_id']!=approved for c in missing_usage):raise ValueError('Unexpected unavailable usage requires review.')
    wanted={'missing_records':1,'unfinished_classification':1}
    n=sum(type(c.get(f)) is not int for c in missing_usage for f in ('input_tokens','output_tokens'))
    if n:wanted['invalid_usage']=n
    if checked['status']!='review_required' or checked.get('issue_counts')!=wanted:
        raise ValueError('Unexpected instructor findings block subset publication.')

def saved_review(db,root=ROOT):
    root=Path(root);out=root/'reports/completed_subset';frozen=json.loads((out/'scope_manifest.json').read_text())
    checked=json.loads((out/'subset_integrity.json').read_text())
    if db.execute('SELECT 1 FROM run_locks').fetchone() or db.execute("SELECT 1 FROM calls WHERE outcome='in_flight'").fetchone():raise ValueError('Wait for active work.')
    if checked['status']!='pass' or checked['completed_count']!=frozen['completed_reviews'] or course.sha(out/'records.json')!=frozen['records_sha256']:
        raise ValueError('Frozen subset integrity changed.')
    if course.sha(root/'vendor/check_submission.py')!=checked['instructor_checker_sha256'] or course.sha(out/'instructor_full_source_check.json')!=checked['checker_report_sha256']:
        raise ValueError('Checker or its report changed; rerun subset-check.')
    for name,digest in checked['grading_sha256'].items():
        if course.sha(root/'grading'/name)!=digest:raise ValueError('Grading artifact changed; rerun subset-check.')
    return checked
