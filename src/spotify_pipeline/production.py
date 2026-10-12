"""Full-source preparation and deliberate, capped execution after measured checkpoints."""
import json
import math
import shutil
import time
import uuid
from pathlib import Path
from .core import ROOT,atomic_json,connect,course,meta
from .lean import control,settings,inherit_completed,enrich
from .analysis import analyze,jsonl_save
from .budget_policy import dispatch_block_reason

SCOPE='full';INPUT_DB=ROOT/'work/full.sqlite';OUT=ROOT/'reports/full_run'
MIN_FREE_BYTES=6*1024**3  # Room for SQLite/WAL, raw handoffs, exports and atomic temporary copies.

def status():
    _,cfg=settings(50,'v3');db=control()
    try:
        db.execute('BEGIN')  # One coherent WAL snapshot while the worker continues saving results.
        count=db.execute("""SELECT count(*),sum(json_type(part_json,'$.record')='object'),
          sum(json_type(part_json,'$.topic')='object' AND json_extract(part_json,'$.record.cache_source_id') IS NULL),
          sum(json_type(part_json,'$.record')='object' AND json_extract(part_json,'$.record.cache_source_id') IS NULL),
          sum(json_type(part_json,'$.record')='object' AND json_extract(part_json,'$.record.cache_source_id') IS NOT NULL)
          FROM lean_parts WHERE scope=? AND label_config=?""",(SCOPE,cfg)).fetchone()
        budget=dict(db.execute('SELECT * FROM budget').fetchone())
        block_reason=dispatch_block_reason(db)
        classification_block_reason=dispatch_block_reason(db,'enrich')
        held=db.execute('SELECT COALESCE(SUM(held_usd),0) FROM unknown_charge_holds WHERE active=1').fetchone()[0]
        in_flight=db.execute("SELECT count(*) FROM calls WHERE outcome='in_flight'").fetchone()[0]
        attempts=db.execute("SELECT count(*),sum(json_extract(call_json,'$.provider')='typesafe') FROM calls").fetchone()
        lock=db.execute('SELECT run_id FROM run_locks WHERE scope=?',(SCOPE,)).fetchone()
    finally:db.close()
    return {'scope':SCOPE,'source_rows':660622,'nonempty_reviews':660609,'empty_quarantines':13,
            'saved_partial_rows':count[0],'completed_rows':count[1] or 0,'topic_intent_rows':count[2] or 0,
            'distinct_nonempty_texts':484189,'completed_originals':count[3] or 0,'completed_cache_aliases':count[4] or 0,
            'topic_intent_pending_distinct':484189-(count[2] or 0),
            'nonempty_pending':660609-(count[1] or 0),'known_project_api_usd':budget['spent'],
            'reserved_usd':budget['reserved'],'unknown_paid_usage':budget['unknown_charges'],
            'authorized_unknown_hold_usd':held,'paid_dispatch_block_reason':block_reason,'cost_status':'provisional' if budget['unknown_charges'] else 'usage_reconciled',
            'classification_block_reason':classification_block_reason,
            'in_flight_requests':in_flight,
            'recorded_attempts':attempts[0],'typesafe_attempts':attempts[1] or 0,
            'active_run_id':lock[0] if lock else None,'new_model_calls':0,
            'note':'Includes actually imported completed originals; new full-source dispatch is recorded separately.'}

def require_primary_robustness():
    path=ROOT/'reports/robustness/primary_jev/results.json'
    if not path.exists():raise ValueError('Execute and review the isolated primary Jev injection checks before full dispatch.')
    result=json.loads(path.read_text());_,cfg=settings(50,'v3')
    if result.get('state')!='completed' or not result.get('all_passed') or result.get('label_config')!=cfg:
        raise ValueError('Primary Jev injection checks have not passed for the frozen configuration.')

def prepare():
    prior=ROOT/'reports/checkpoint10000'
    measured=json.loads((prior/'checkpoint_run.json').read_text())
    checked=json.loads((prior/'self_check.json').read_text())
    if measured['state']!='completed' or checked['status']!='pass' or checked['coverage']['valid_completed']!=10000:
        raise ValueError('Complete and check the measured 10000 checkpoint before full preparation.')
    config,cfg=settings(50,'v3')
    if cfg!=json.loads((prior/'enrichment_run.json').read_text())['label_config']:
        raise ValueError('Keep the accepted fixed-label configuration frozen.')
    source=connect(INPUT_DB);profile=meta(source,'profile');path=Path(meta(source,'source_path'))
    report=meta(source,'ingestion_report');source.close()
    manifest=json.loads((ROOT/'dataset/manifest.json').read_text())
    if not report['expected_manifest_match'] or profile['counts']!=manifest['profile'] or profile['file_sha256']!=manifest['files'][path.name]['sha256']:
        raise ValueError('Full input does not match the supplied manifest.')
    if course.sha(path)!=profile['file_sha256']:raise ValueError('Full source changed since ingestion.')
    db=control()
    try:
        if db.execute('SELECT 1 FROM run_locks WHERE scope=?',(SCOPE,)).fetchone():raise ValueError('Full scope is active; inspect saved status.')
        db.execute('ATTACH DATABASE ? AS fullsource',(str(INPUT_DB),))
        candidates=[dict(r) for r in db.execute('''SELECT s.* FROM fullsource.source_reviews s JOIN lean_parts p
              ON s.review_id=p.review_id AND s.source_sha256=p.source_sha256
              AND s.text_sha256=p.text_sha256 AND s.review_text=p.review_text
              WHERE p.scope=? AND p.label_config=? AND json_type(p.part_json,'$.record')='object'
              AND json_extract(p.part_json,'$.record.cache_source_id') IS NULL
              AND s.source_status='pending' ORDER BY s.source_order''',('checkpoint10000',cfg))]
        copied=inherit_completed(db,candidates,'checkpoint10000',SCOPE,cfg)
        budget=dict(db.execute('SELECT * FROM budget').fetchone())
        completed=db.execute("SELECT count(*) FROM lean_parts WHERE scope=? AND label_config=? AND json_type(part_json,'$.record')='object'",(SCOPE,cfg)).fetchone()[0]
        completed_unique=db.execute("SELECT count(DISTINCT text_sha256) FROM lean_parts WHERE scope=? AND label_config=? AND json_type(part_json,'$.record')='object' AND json_extract(part_json,'$.record.cache_source_id') IS NULL",(SCOPE,cfg)).fetchone()[0]
    finally:db.close()
    inventory_path=OUT/'cache_transfer.json'
    previous=json.loads(inventory_path.read_text())['originals'] if inventory_path.exists() else []
    inventory={r['review_id']:r for r in previous};inventory.update({r['review_id']:r for r in copied})
    atomic_json(inventory_path,{'source_scope':'checkpoint10000','target_scope':SCOPE,'label_config':cfg,'originals':list(inventory.values()),
                              'note':'Identical original ID, row hash, text hash, exact text and configuration; original request provenance preserved.'})
    free=shutil.disk_usage(ROOT).free
    initial_work=report['distinct_nonempty_texts']-len(inventory)
    remaining_work=report['distinct_nonempty_texts']-completed_unique
    required_free=2*1024**3+math.ceil(4*1024**3*remaining_work/max(1,initial_work))
    plan={'state':'prepared','scope':SCOPE,'source':str(path),'source_sha256':profile['file_sha256'],
          'source_rows':report['stored_rows'],'nonempty_reviews':report['nonempty_rows'],
          'empty_quarantines':profile['counts']['empty_review_text'],'distinct_nonempty_texts':report['distinct_nonempty_texts'],
          'completed_originals_available':completed_unique,'completed_rows_in_full_scope':completed,
          'pending_rows_in_full_scope':report['nonempty_rows']-completed,
          'pending_distinct_texts':report['distinct_nonempty_texts']-completed_unique,
          'workers':1,'batch_size':50,'stronger_fallback_limit':0,'automatic_retry_limit':0,
          'label_config':cfg,'blind_verification_max':1000,'destination':'https://api.typesafe.ai/v1/systemone',
          'absolute_project_api_cap_usd':4.8,'known_project_api_usage_usd':budget['spent'],
          'remaining_project_api_cap_usd':max(0,4.8-budget['spent']-budget['reserved']),
          'reserved_usd':budget['reserved'],'unresolved_paid_usage':budget['unknown_charges'],
          'paid_execution':False,'new_model_calls':0,'free_disk_bytes':free,'minimum_free_disk_bytes':required_free,
          'storage_ready':free>=required_free,
          'execute_command':'./run.sh full-run --execute-paid --project-cap-usd 4.80',
          'note':'Preparation transfers validated cache only. No full-source paid dispatch is claimed. API costs are estimates, not receipts or balances.'}
    atomic_json(OUT/'execution_plan.json',plan)
    atomic_json(OUT/'configuration.json',config);atomic_json(OUT/'ingestion_report.json',report)
    return plan

def run(execute_paid=False,project_cap=4.8):
    if not 0<project_cap<=4.8:raise ValueError('Project total API cap must be within $4.80.')
    plan=prepare()
    if not execute_paid:return plan
    if not plan['storage_ready']:
        required=plan.get('minimum_free_disk_bytes',MIN_FREE_BYTES)/1024**3
        raise ValueError(f'Full run needs at least {required:g} GiB free disk for saved results and atomic exports; no paid calls started.')
    db=control()
    try:block_reason=dispatch_block_reason(db,'enrich')
    finally:db.close()
    if block_reason:raise ValueError(block_reason)
    cap_path=OUT/'dispatch_cap.json'
    if cap_path.exists():project_cap=min(project_cap,json.loads(cap_path.read_text())['absolute_project_api_cap_usd'])
    remaining=project_cap-plan['known_project_api_usage_usd']
    if remaining<=0:raise ValueError('Project API cap is already exhausted.')
    require_primary_robustness()
    atomic_json(cap_path,{'absolute_project_api_cap_usd':project_cap,'note':'Immutable upper bound across resumed paid phases; never increased by resume.'})
    started=time.time();tick=time.perf_counter();run_id=str(uuid.uuid4())
    enriched=enrich(INPUT_DB,OUT,SCOPE,50,True,absolute_cap=project_cap,version='v3',additional_cap=remaining,save_prepared=False)
    phase={'run_id':run_id,'started_at_unix':started,'enrichment':enriched,'absolute_project_api_cap_usd':project_cap}
    if enriched['stop_reason']!='completed' or enriched['enrichment_completed']!=plan['nonempty_reviews']:
        phase.update(state='stopped',wall_seconds=time.perf_counter()-tick)
        atomic_json(OUT/'production_phases'/f'{run_id}.json',phase)
        return phase
    phase.update(state='enrichment_complete_downstream_pending',wall_seconds=time.perf_counter()-tick)
    atomic_json(OUT/'production_phases'/f'{run_id}.json',phase)
    try:analysis=analyze(INPUT_DB,OUT,True,verification_size=1000,full_corpus=True)
    except (ValueError,KeyboardInterrupt):
        phase.update(state='downstream_stopped',wall_seconds=time.perf_counter()-tick)
        atomic_json(OUT/'production_phases'/f'{run_id}.json',phase)
        raise
    phase.update(state='completed',analysis=analysis,wall_seconds=time.perf_counter()-tick)
    atomic_json(OUT/'production_phases'/f'{run_id}.json',phase);atomic_json(OUT/'production_run.json',phase)
    return phase

def audit():
    """Offline full-source grading export. Never represented as passing before execution."""
    run=json.loads((OUT/'production_run.json').read_text())
    if run['state']!='completed':raise ValueError('Complete the full-source run before exporting grading.')
    plan=json.loads((OUT/'execution_plan.json').read_text());full=Path(plan['source'])
    if course.sha(full)!=plan['source_sha256']:raise ValueError('Source changed before full grading.')
    folder=ROOT/'grading';folder.mkdir(exist_ok=True)
    records=json.loads((OUT/'records.json').read_text())
    quarantines=[json.loads(line) for line in (ROOT/'reports/full/quarantine.jsonl').read_text().splitlines()]
    if len(records)!=660609 or len(quarantines)!=13:raise ValueError('Full output/quarantine counts differ.')
    jsonl_save(folder/'records.jsonl',[*records,*quarantines])
    atomic_json(folder/'run.json',{'version':'a5-audit-v1','analysis_count':660622,'analysis_sha256':plan['source_sha256'],
           'classification_input_fields':['review_text'],'allow_multi_issue':False,'scope':'complete supplied corpus',
           'resume_demo_origin':'Actual pilot100 SIGINT/resume, then verified cache transfer and production; no additional interruption is claimed.'})
    shutil.copyfile(ROOT/'reports/full/ingestion.json',folder/'ingestion.json')
    for name in ('membership.csv','ranking.csv','claims.csv'):shutil.copyfile(OUT/name,folder/name)
    shutil.copyfile(ROOT/'reports/pilot100_optimized/checkpoint_before.json',folder/'checkpoint_before.json')
    enriched=json.loads((OUT/'enrichment_run.json').read_text())
    shutil.copyfile(OUT/'runs'/enriched['run_id']/'checkpoint_after.json',folder/'checkpoint_after.json')
    request_ids={rid for record in records for rid in record.get('model_request_ids',[])}
    request_ids.update(p.name.removesuffix('_input.json') for p in (OUT/'handoffs').glob('*_input.json'))
    db=control()
    try:calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls ORDER BY rowid') if json.loads(r[0])['request_id'] in request_ids]
    finally:db.close()
    jsonl_save(folder/'calls.jsonl',calls)
    reference=course.reference(full,full)
    report=course.audit(folder,reference,None,course.reference_hash(reference));atomic_json(OUT/'self_check.json',report)
    return {'scope':'complete supplied corpus','status':report['status'],'coverage':report['coverage'],'issue_counts':report.get('issue_counts'),'new_model_calls':0}
