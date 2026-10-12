"""One explicitly paid six-stage pilot entry point; separate offline calculator."""
import json
import time
from pathlib import Path
from .core import ROOT, atomic_json, ingest, course
from .lean import CONTROL, control, enrich, settings
from .analysis import analyze, jsonl_save, csv_save

def run(input_csv=ROOT/'dataset/samples/cost_100.csv',outdir=ROOT/'reports/pilot100_final',scope='pilot100_final',batch_size=50,interrupt_demo=False,version='v2',additional_cap=.002):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'dataset/manifest.json').read_text())
    if course.sha(input_csv)!=manifest['files']['cost_100.csv']['sha256']:raise ValueError('Use the supplied, unchanged cost_100.csv for this pilot.')
    clock=time.perf_counter();run_id=str(int(time.time()*1000000));events=[]
    def note(message):
        text=message+'\r\n';events.append([time.perf_counter()-clock,'o',text]);print(message,flush=True)
    input_db=ROOT/'work'/f'{scope}_source.sqlite'
    note('Starting the measured 100-review pipeline; paid usage capped at $0.05 across this pilot and its earlier route test.')
    st=time.perf_counter();ingestion=ingest(input_csv,input_db,outdir/'ingestion_report.json');prep_seconds=time.perf_counter()-st
    ledger=control();initial_calls={r[0] for r in ledger.execute('SELECT request_id FROM calls')}
    # Prior approved 100-route development plus this complete pilot share one $0.05 allowance.
    historical=sum(json.loads(r[0]).get('calculated_api_usd',0) or 0 for r in ledger.execute('SELECT call_json FROM calls') if json.loads(r[0]).get('historical_import'))
    cap=min(4.8,historical+.05,ledger.execute('SELECT spent+reserved FROM budget').fetchone()[0]+additional_cap);_,cfg=settings(batch_size,version)
    existing=ledger.execute('SELECT COUNT(*) FROM lean_parts WHERE scope=? AND label_config=?',(scope,cfg)).fetchone()[0];ledger.close()
    temperature='warm' if existing else 'cold'
    if interrupt_demo and existing:raise ValueError('Interruption demonstration requires a fresh pilot scope.')
    try:
        st=time.perf_counter()
        if interrupt_demo:
            note('First batch will save validated progress, then receive an actual SIGINT.')
            first=enrich(input_db,outdir,scope,batch_size,True,interrupt_after_batches=1,absolute_cap=cap,version=version)
            if first['stop_reason']!='interrupted':raise ValueError('Interruption demonstration did not interrupt successfully.')
            checkpoint=json.loads((outdir/'runs'/first['run_id']/'checkpoint_at_interrupt.json').read_text())
            atomic_json(outdir/'checkpoint_before.json',checkpoint)
            note(f'SIGINT handled: {len(checkpoint["completed_ids"])} completed IDs were saved. Resuming the same configuration.')
        enriched=enrich(input_db,outdir,scope,batch_size,True,absolute_cap=cap,version=version)
        enrichment_seconds=time.perf_counter()-st
        if enriched['stop_reason']!='completed' or enriched['enrichment_completed']!=100:raise ValueError('Pilot enrichment did not complete all 100 reviews.')
        if interrupt_demo:
            after=json.loads((outdir/'runs'/enriched['run_id']/'checkpoint_after.json').read_text());atomic_json(outdir/'checkpoint_after.json',after)
            note(f'Resume completed: {len(after["completed_ids"])} IDs; completed records were reused without enrichment calls.')
        analysis=analyze(input_db,outdir,True)
        ledger=control();calls=[json.loads(r[0]) for r in ledger.execute('SELECT call_json FROM calls ORDER BY rowid') if json.loads(r[0])['request_id'] not in initial_calls];ledger.close()
        result={'run_id':run_id,'temperature':temperature,'scope':scope,'source_sha256':ingestion['profile']['file_sha256'],
                'input_rows':100,'completed':enriched['enrichment_completed'],'failed':0,'unique_texts':ingestion['distinct_nonempty_texts'],
                'wall_seconds':time.perf_counter()-clock,'stage_seconds':{'prepare':prep_seconds,'enrich':enrichment_seconds,**analysis['stage_seconds']},
                'model_requests':len(calls),'new_enrichment_calls':sum(c['role']=='enrich' for c in calls),'cache_hits':enriched['cache_hits'],
                'api_usd':sum(c['calculated_api_usd'] for c in calls),'local_compute_usd':None,'batch_size':batch_size,'workers':1,
                'fallback_limit':0,'interruption_demonstrated':interrupt_demo,'downstream_cache_hits':analysis['cache_hits'],'state':'completed'}
        atomic_json(outdir/'pipeline_runs'/f'{run_id}.json',result);atomic_json(outdir/'pipeline_run.json',result)
        jsonl_save(outdir/'pipeline_runs'/f'{run_id}_calls.jsonl',calls)
        note(f'{temperature.capitalize()} pipeline complete. Actual calls: {len(calls)}; API usage cost: ${result["api_usd"]:.9f}.')
        return result
    finally:
        if interrupt_demo:
            header={'version':2,'width':110,'height':24,'timestamp':int(time.time()),'title':'Actual automated SIGINT and resume — Spotify 100-review pilot'}
            (outdir/'resume.cast').write_text(json.dumps(header)+'\n'+'\n'.join(json.dumps(e) for e in events)+'\n')

def export_cost(outdir=ROOT/'reports/pilot100_final'):
    """Export existing measurements only: no key loading, network, or inference."""
    outdir=Path(outdir);runs=sorted([json.loads(p.read_text()) for p in (outdir/'pipeline_runs').glob('*.json')],key=lambda r:r['run_id'])
    if not runs:raise ValueError('No completed measured pipeline runs to export.')
    calls=[]
    for p in sorted((outdir/'pipeline_runs').glob('*_calls.jsonl')):calls.extend(json.loads(line) for line in p.read_text().splitlines())
    records=json.loads((outdir/'records.json').read_text());cost=ROOT/'cost'
    jsonl_save(cost/'pilot_records.jsonl',records);jsonl_save(cost/'pilot_calls.jsonl',calls);atomic_json(cost/'pilot_runs.json',runs)
    rows=[{**c,'currency':'USD','input_billing_unit':'input_token','output_billing_unit':'output_token'} for c in calls]
    csv_save(cost/'usage.csv',rows,['request_id','run_id','role','provider','model','outcome','input_tokens','output_tokens','input_billing_unit','output_billing_unit','currency','calculated_api_usd','elapsed_seconds'])
    return {'exported_completed_runs':len(runs),'saved_calls':len(calls),'pilot_records':len(records),'offline':True,'new_model_calls':0}

def audit_pilot(outdir,reference_path):
    """Instructor checker on this 100-review scope; never claim full-corpus coverage."""
    import shutil
    outdir=Path(outdir).resolve();folder=outdir/'grading';folder.mkdir(exist_ok=True)
    records=json.loads((outdir/'records.json').read_text());jsonl_save(folder/'records.jsonl',records)
    manifest=json.loads((ROOT/'dataset/manifest.json').read_text())
    atomic_json(folder/'run.json',{'version':'a5-audit-v1','analysis_count':100,'analysis_sha256':manifest['files']['cost_100.csv']['sha256'],'classification_input_fields':['review_text'],'allow_multi_issue':False,'scope':'100-review development pilot only'})
    shutil.copyfile(ROOT/'reports/full/ingestion.json',folder/'ingestion.json')
    for name in ('membership.csv','ranking.csv','claims.csv','checkpoint_before.json','checkpoint_after.json'):shutil.copyfile(outdir/name,folder/name)
    request_ids={p.name.removesuffix('_input.json') for p in (outdir/'handoffs').glob('*_input.json')}
    db=control();calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls ORDER BY rowid') if json.loads(r[0])['request_id'] in request_ids];db.close()
    jsonl_save(folder/'calls.jsonl',calls)
    reference=json.loads(Path(reference_path).read_text());report=course.audit(folder,reference,None,course.reference_hash(reference))
    atomic_json(outdir/'self_check.json',report)
    return {'scope':'100-review development pilot only','status':report['status'],'coverage':report['coverage'],'issue_counts':report.get('issue_counts'),'new_model_calls':0}
