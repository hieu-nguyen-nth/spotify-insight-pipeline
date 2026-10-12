"""Isolated live blind-verification benchmark; business classifications remain stopped."""
import argparse
import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from .core import ROOT,atomic_json,course
from .lean import CONTROL,control,settings,body_for,dispatch
from .jev import load_key
from .budget_policy import dispatch_block_reason

OUT=ROOT/'reports/worker_comparison'

def compare(execute_paid=False,out=OUT,control_path=CONTROL,transport=None):
    out=Path(out)
    source=ROOT/'dataset/samples/cost_100.csv'
    expected=json.loads((ROOT/'dataset/manifest.json').read_text())['files']['cost_100.csv']['sha256']
    if course.sha(source)!=expected:raise ValueError('Benchmark input must match the unchanged course pilot checksum.')
    rows=list(course.csv_rows(source))
    config,cfg=settings(50,'v3')
    plan={'state':'prepared','input_sha256':course.sha(source),'input_reviews':len(rows),
      'conditions':[1,2],'batch_size':10,'task':'blind topic/intent/severity verification',
      'cache_conditions':'fresh benchmark result cache in both conditions; no existing result reuse',
      'shared_limits':{'requests_per_second':4,'estimated_tokens_per_second':50000,'api_ceiling_usd':4.8},
      'additional_cap_usd':.01,'stronger_fallbacks':0,'retries':0,'classification_updates':0}
    if len(rows)!=100:raise ValueError('Benchmark requires the unchanged 100-review development input.')
    if not execute_paid:return dict(plan,new_model_calls=0)
    if (out/'report.json').exists():raise ValueError('Benchmark evidence already exists; do not repeat paid work automatically.')
    db=control(control_path)
    try:
        if db.execute('SELECT 1 FROM run_locks').fetchone() or dispatch_block_reason(db):raise ValueError('Wait for existing work and reconcile unauthorized uncertainty.')
        before=dict(db.execute('SELECT * FROM budget').fetchone())
        cap=min(4.8,before['spent']+before['reserved']+.01)
        if before['spent']+before['reserved']>=cap:raise ValueError('No remaining approved benchmark allowance.')
        key=load_key(ROOT/'.env') if transport is None else None
        report={**plan,'state':'running','budget_before':before,'absolute_admission_cap_usd':cap,'conditions':[]}
        atomic_json(out/'plan.json',plan)
        errors=[]
        for workers in (1,2):
            run_id=str(uuid.uuid4());scope='worker-comparison-'+run_id
            db.execute('INSERT INTO run_locks VALUES(?,?)',(scope,run_id));db.commit()
            folder=out/str(workers);predictions={}
            # Exclude an explicit cooldown from both measured condition durations.
            time.sleep(1.1)
            tick=time.perf_counter()
            def task(batch):
                connection=control(control_path)
                try:
                    body=body_for(batch,config,'verify',blind=True)
                    answers,call=dispatch(connection,body,batch,run_id,cfg,'initial','verify',cap,folder,
                      transport=transport,key=key,worker_limit=workers,concurrent_run_id=run_id,
                      experiment='worker_comparison')
                    values={s['review_id']:{f:int(answers[f'r{i}_{f}']['choice']) if f=='severity' else answers[f'r{i}_{f}']['choice'] for f in ('topic','intent','severity')} for i,s in enumerate(batch)}
                    atomic_json(folder/'results'/f'{call["request_id"]}.json',{'request_id':call['request_id'],'predictions':values})
                    return values
                finally:connection.close()
            try:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures=[executor.submit(task,rows[i:i+10]) for i in range(0,100,10)]
                    for future in as_completed(futures):
                        try:
                            values=future.result()
                            if set(predictions)&set(values):raise ValueError('Duplicate benchmark result IDs.')
                            predictions.update(values)
                        except Exception as exc:errors.append(type(exc).__name__)
            finally:
                # Executor has waited for owned requests to settle; never remove someone else's lock.
                active=db.execute("SELECT 1 FROM calls WHERE run_id=? AND outcome='in_flight'",(run_id,)).fetchone()
                if not active:db.execute('DELETE FROM run_locks WHERE scope=? AND run_id=?',(scope,run_id));db.commit()
            wall=time.perf_counter()-tick
            calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls WHERE run_id=? ORDER BY rowid',(run_id,))]
            from .analysis import jsonl_save
            jsonl_save(folder/'calls.jsonl',calls)
            atomic_json(folder/'predictions.json',predictions)
            events=sorted([(c['started_at_unix'],1) for c in calls]+[(c['finished_at_unix'],-1) for c in calls if 'finished_at_unix' in c],key=lambda v:(v[0],v[1]))
            active_count=peak=0
            for _,delta in events:active_count+=delta;peak=max(peak,active_count)
            known=sum(c['calculated_api_usd'] for c in calls if c.get('calculated_api_usd') is not None)
            condition={'run_id':run_id,'workers':workers,'completed':len(predictions),'wall_seconds':wall,
              'reviews_per_second':len(predictions)/wall,'attempts':len(calls),'cache_hits':0,
              'known_api_usd':known,'total_api_usd':None if any(c.get('calculated_api_usd') is None for c in calls) else known,
              'input_tokens':sum(c.get('input_tokens') or 0 for c in calls),'output_tokens':sum(c.get('output_tokens') or 0 for c in calls),
              'peak_inflight_requests':peak,'failed_attempts':sum(c['outcome']!='succeeded' for c in calls)}
            report['conditions'].append(condition);atomic_json(out/'report.json',report)
            if errors or dispatch_block_reason(db):break
        after=dict(db.execute('SELECT * FROM budget').fetchone())
        report.update(state='stopped' if errors or len(report['conditions'])!=2 else 'completed',budget_after=after,
          additional_known_api_usd=after['spent']-before['spent'],errors=errors,
          unknown_charge_hold_usd=before['reserved'],classification_updates=0,
          inference_destination='https://api.typesafe.ai/v1/systemone',model=config['model'],label_config=cfg,
          measurement_scope='Small live benchmark, not a full-pipeline speedup or provider Batch discount.')
        if report['state']=='completed':
            a=json.loads((out/'1/predictions.json').read_text());b=json.loads((out/'2/predictions.json').read_text())
            report.update(speedup=report['conditions'][0]['wall_seconds']/report['conditions'][1]['wall_seconds'],
              same_input_ids=set(a)==set(b)=={r['review_id'] for r in rows},
              differing_reviews=sum(a[rid]!=b[rid] for rid in a),
              within_additional_cap=report['additional_known_api_usd']<=.01+1e-9)
        atomic_json(out/'report.json',report)
        return report
    finally:db.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-paid',action='store_true');args=p.parse_args()
    print(json.dumps(compare(args.execute_paid),indent=2))

if __name__=='__main__':main()
