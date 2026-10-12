"""Measured staged checkpoints. Preparation is offline; inference is explicit."""
import json
import shutil
import time
import uuid
from decimal import Decimal
from pathlib import Path
from .core import ROOT,atomic_json,ingest,course
from .lean import control,prepare,inherit_completed,enrich
from .analysis import analyze,jsonl_save

def run(size,execute_paid=False,additional_cap=None):
    if size not in (500,10000):raise ValueError('Measure 500 before 10,000.')
    prior=ROOT/'reports'/('pilot100_optimized' if size==500 else 'checkpoint500')
    if size==500:
        previous=next((json.loads(p.read_text()) for p in sorted((prior/'pipeline_runs').glob('*.json')) if json.loads(p.read_text()).get('temperature')=='cold'),{})
    else:
        previous=json.loads((prior/'checkpoint_run.json').read_text())
    if previous.get('state')!='completed':raise ValueError('Complete the preceding measured stage first.')
    filename='checkpoint_500.csv' if size==500 else 'analysis_10000.csv'
    source=ROOT/'dataset/samples'/filename
    manifest=json.loads((ROOT/'dataset/manifest.json').read_text())
    if course.sha(source)!=manifest['files'][filename]['sha256']:raise ValueError('Checkpoint input differs from the fixed manifest.')
    cap_allowance=additional_cap if additional_cap is not None else (.02 if size==500 else .2)
    if not 0<cap_allowance<=4.8:raise ValueError('Choose a positive allowance within the project cap.')
    out=ROOT/'reports'/f'checkpoint{size}';input_db=ROOT/'work'/f'checkpoint{size}_source.sqlite'
    clock=time.perf_counter();started=time.time();run_id=str(uuid.uuid4())
    ingestion=ingest(source,input_db,out/'ingestion_report.json');prep_seconds=time.perf_counter()-clock
    plan,sources,config,cfg,profile=prepare(input_db,out,f'checkpoint{size}',50,'v3')
    if len(sources)!=size:raise ValueError('Unexpected checkpoint row count.')
    if cfg!=json.loads((prior/'enrichment_run.json').read_text())['label_config']:
        raise ValueError('The checkpoint must keep the accepted classifier frozen.')
    ledger=control();before={r[0] for r in ledger.execute('SELECT request_id FROM calls')}
    absolute_cap=min(4.8,ledger.execute('SELECT spent+reserved FROM budget').fetchone()[0]+cap_allowance)
    if (out/'checkpoint_plan.json').exists():
        previous_plan=json.loads((out/'checkpoint_plan.json').read_text())
        if previous_plan['label_config']!=cfg:raise ValueError('Use a separate scope for a changed configuration.')
        absolute_cap=min(absolute_cap,previous_plan['absolute_project_cap_usd'])
    prior_scope=json.loads((prior/'enrichment_run.json').read_text())['scope']
    reused=inherit_completed(ledger,sources,prior_scope,f'checkpoint{size}',cfg)
    ledger.close()
    if (out/'cache_transfer.json').exists():
        previous_transfer=json.loads((out/'cache_transfer.json').read_text())
        if previous_transfer['label_config']!=cfg:raise ValueError('Cache transfer configuration changed.')
        by_id={r['review_id']:r for r in previous_transfer['reused_original_rows']}
        by_id.update({r['review_id']:r for r in reused});reused=list(by_id.values())
    atomic_json(out/'cache_transfer.json',{'source_scope':prior_scope,'label_config':cfg,'reused_original_rows':reused,
                'note':'Identical original IDs/row hashes/text/configuration only. Existing target results are retained separately.'})
    plan.update(execute_paid=execute_paid,paid_execution=execute_paid,additional_cap_usd=cap_allowance,absolute_project_cap_usd=absolute_cap,
                reused_rows_this_preparation=len(reused),verification_sample_size=10,
                incremental_pilot_cap_usd=cap_allowance,sentiment_quality='golden50_diagnostics_recorded_student_accepted_variation',
                classifier_quality_decision='Student reviewed golden disagreements and accepted the frozen configuration; original scores/labels retained.')
    atomic_json(out/'checkpoint_plan.json',plan)
    if not execute_paid:return {**plan,'state':'prepared','new_model_calls':0}
    st=time.perf_counter()
    enriched=enrich(input_db,out,f'checkpoint{size}',50,True,absolute_cap=absolute_cap,version='v3',additional_cap=cap_allowance)
    enrich_seconds=time.perf_counter()-st
    if enriched['stop_reason']!='completed' or enriched['enrichment_completed']!=size:
        raise ValueError('Checkpoint stopped; saved enrichment progress can resume.')
    analysis=analyze(input_db,out,True)
    ledger=control();calls=[json.loads(r[0]) for r in ledger.execute('SELECT call_json FROM calls ORDER BY rowid') if json.loads(r[0])['request_id'] not in before]
    budget=dict(ledger.execute('SELECT * FROM budget').fetchone());ledger.close()
    result={'state':'completed','run_id':run_id,'scope':f'checkpoint{size}','source_sha256':profile['file_sha256'],
            'input_rows':size,'completed':size,'unique_texts':ingestion['distinct_nonempty_texts'],
            'started_at_unix':started,'wall_seconds':time.perf_counter()-clock,
            'stage_seconds':{'prepare':prep_seconds,'enrich':enrich_seconds,**analysis['stage_seconds']},
            'model_requests':len(calls),'new_enrichment_calls':sum(c['role']=='enrich' for c in calls),
            'new_unique_enrichment_work':len({rid for c in calls if c['role']=='enrich' for rid in c['review_ids']}),
            'enrichment_cache_hits':enriched['cache_hits'],'api_usd':sum(c['calculated_api_usd'] for c in calls),
            'local_compute_usd':None,'workers':1,'batch_size':50,'fallback_limit':0,'additional_cap_usd':cap_allowance,
            'project_spend_after_usd':budget['spent'],'verification_disagreements':json.loads((out/'verification.json').read_text())['disagreement_count'],
            'note':'Measured incremental work with validated earlier-row reuse; not a fully cold run or human accuracy estimate.'}
    atomic_json(out/'checkpoint_runs'/f'{run_id}.json',result);atomic_json(out/'checkpoint_run.json',result)
    jsonl_save(out/'checkpoint_runs'/f'{run_id}_calls.jsonl',calls)
    return result

def audit(size,full_input=None):
    """Offline scoped checker, with the actual initial pilot interruption trace."""
    if size not in (500,10000):raise ValueError('Choose a measured checkpoint.')
    out=ROOT/'reports'/f'checkpoint{size}'
    measured=json.loads((out/'checkpoint_run.json').read_text())
    if measured['state']!='completed':raise ValueError('Complete the checkpoint before auditing.')
    sample=ROOT/'dataset/samples'/('checkpoint_500.csv' if size==500 else 'analysis_10000.csv')
    reference_path=ROOT/'work'/f'checkpoint{size}_reference.json'
    if reference_path.exists():
        reference=course.read_json(reference_path)
        if reference['analysis_sha256']!=course.sha(sample):raise ValueError('Saved reference has a different input checksum.')
    else:
        full=Path(full_input) if full_input else Path(json.loads((ROOT/'reports/full/ingestion_report.json').read_text())['source'])
        reference=course.reference(full,sample);atomic_json(reference_path,reference)
    if reference['ingestion']!=json.loads((ROOT/'reports/full/ingestion.json').read_text()):
        raise ValueError('Reference does not match the verified full-source profile.')
    folder=out/'grading';folder.mkdir(exist_ok=True)
    records=json.loads((out/'records.json').read_text());jsonl_save(folder/'records.jsonl',records)
    atomic_json(folder/'run.json',{'version':'a5-audit-v1','analysis_count':size,'analysis_sha256':course.sha(sample),
          'classification_input_fields':['review_text'],'allow_multi_issue':False,'scope':f'{size}-review development checkpoint only',
          'resume_demo_origin':'Actual pilot100 SIGINT/resume, followed by validated checkpoint expansions; no new interruption is claimed.'})
    shutil.copyfile(ROOT/'reports/full/ingestion.json',folder/'ingestion.json')
    for name in ('membership.csv','ranking.csv','claims.csv'):shutil.copyfile(out/name,folder/name)
    shutil.copyfile(ROOT/'reports/pilot100_optimized/checkpoint_before.json',folder/'checkpoint_before.json')
    enriched=json.loads((out/'enrichment_run.json').read_text())
    shutil.copyfile(out/'runs'/enriched['run_id']/'checkpoint_after.json',folder/'checkpoint_after.json')
    request_ids={rid for record in records for rid in record.get('model_request_ids',[])}
    request_ids.update(p.name.removesuffix('_input.json') for p in (out/'handoffs').glob('*_input.json'))
    db=control()
    try:calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls ORDER BY rowid') if json.loads(r[0])['request_id'] in request_ids]
    finally:db.close()
    jsonl_save(folder/'calls.jsonl',calls)
    report=course.audit(folder,reference,None,course.reference_hash(reference));atomic_json(out/'self_check.json',report)
    return {'scope':f'{size}-review checkpoint only','status':report['status'],'coverage':report['coverage'],
            'issue_counts':report.get('issue_counts'),'new_model_calls':0}

def export(size):
    """Copy real checkpoint measurement files and refresh the offline spend snapshot."""
    if size not in (500,10000):raise ValueError('Choose a measured checkpoint.')
    out=ROOT/'reports'/f'checkpoint{size}';run=json.loads((out/'checkpoint_run.json').read_text())
    if run['state']!='completed':raise ValueError('Do not export incomplete execution as a completed checkpoint.')
    destination=ROOT/'cost/checkpoints'/str(size);destination.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(out/'checkpoint_run.json',destination/'run.json')
    shutil.copyfile(out/'checkpoint_runs'/f"{run['run_id']}_calls.jsonl",destination/'calls.jsonl')
    shutil.copyfile(out/'records.json',destination/'records.json')
    db=control()
    try:
        paid=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls') if json.loads(r[0]).get('provider')=='typesafe']
        ledger=dict(db.execute('SELECT * FROM budget').fetchone())
    finally:db.close()
    known=sum((Decimal(str(c['calculated_api_usd'])) for c in paid if c.get('calculated_api_usd') is not None),Decimal(0))
    atomic_json(ROOT/'cost/project_usage.json',{'snapshot_date':'2026-10-11','known_api_consumption_usd':str(known.quantize(Decimal('.000000000001'))),
        'actual_paid_attempts':len(paid),'unresolved_paid_usage':sum(c.get('calculated_api_usd') is None for c in paid),
        'reserved_usd':ledger['reserved'],'project_api_cap_usd':4.8,
        'source':'Real saved shared ledger: calculated provider usage, not a receipt or account balance.'})
    return {'scope':run['scope'],'saved_actual_calls':run['model_requests'],'known_project_api_usd':str(known.quantize(Decimal('.000000000001'))),'new_model_calls':0}
