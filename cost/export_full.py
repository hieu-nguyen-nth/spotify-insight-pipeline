"""Export an actually completed, checked full run. Offline; never calls providers."""
import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from spotify_pipeline.core import atomic_json
from spotify_pipeline.budget_policy import dispatch_block_reason

def export(provisional=False,root=ROOT):
    root=Path(root);source=root/'reports/full_run';out=root/'cost'/('full_provisional' if provisional else 'full')
    production=json.loads((source/'production_run.json').read_text());checked=json.loads((source/'self_check.json').read_text())
    coverage=checked.get('coverage',{})
    if production['state']!='completed' or any(coverage.get(k)!=v for k,v in {
        'expected':660622,'valid_completed':660609,'quarantined':13,'missing':0,'duplicate_ids':0,'invalid_or_unresolved':0}.items()):
        raise ValueError('Complete and check the full run before exporting full measurements.')
    db=sqlite3.connect('file:'+str(root/'work/control.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN')
        calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls ORDER BY rowid')]
        spent,reserved,unknown=db.execute('SELECT spent,reserved,unknown_charges FROM budget').fetchone()
        holds=[dict(r) for r in db.execute('SELECT * FROM unknown_charge_holds WHERE active=1')]
        if db.execute('SELECT 1 FROM run_locks LIMIT 1').fetchone() or any(c['outcome']=='in_flight' for c in calls):
            raise ValueError('Do not export while a run or request is active.')
        if reserved or unknown:
            if not provisional:raise ValueError('Reconcile incomplete usage before actual full cost export; --provisional preserves approved unknown holds.')
            if dispatch_block_reason(db):raise ValueError('Provisional export requires every unknown charge to have its explicit user-approved hold.')
    finally:db.close()
    unknown_calls=[c for c in calls if c.get('calculated_api_usd') is None]
    hold_ids={h['request_id'] for h in holds}
    if unknown_calls and (not provisional or {c['request_id'] for c in unknown_calls}!=hold_ids):
        raise ValueError('Unknown charges cannot be omitted or silently converted to zero.')
    if checked['status']!='pass':
        expected_missing=sum(type(c.get(f)) is not int for c in unknown_calls for f in ('input_tokens','output_tokens'))
        examples=checked.get('examples',[])
        if (not provisional or checked['status']!='review_required' or not expected_missing
            or checked.get('issue_counts')!={'invalid_usage':expected_missing}
            or len(examples)!=expected_missing or any(e.get('code')!='invalid_usage' or e.get('detail') not in hold_ids for e in examples)):
            raise ValueError('Full checker must pass all checks except explicitly disclosed missing usage on approved held requests.')
    calculated=sum((Decimal(str(c['calculated_api_usd'])) for c in calls if c.get('calculated_api_usd') is not None),Decimal(0))
    if abs(calculated-Decimal(str(spent)))>Decimal('0.000000001'):raise ValueError('Project ledger does not match saved call usage.')
    if calculated+Decimal(str(reserved))>Decimal('4.800000001'):raise ValueError('Known project usage plus holds exceeded the approved cap.')
    ids={p.name.removesuffix('_input.json') for p in (source/'handoffs').glob('*_input.json')}
    current=[c for c in calls if c['request_id'] in ids]
    current_known=sum((Decimal(str(c['calculated_api_usd'])) for c in current if c.get('calculated_api_usd') is not None),Decimal(0))
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('project_calls.jsonl',calls),('new_calls.jsonl',current)]:
        raw=''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows)
        tmp=out/('.'+name+'.tmp');tmp.write_text(raw);tmp.replace(out/name)
    fields=['request_id','run_id','provider','model','role','outcome','input_tokens','output_tokens','elapsed_seconds','calculated_api_usd','usage_status','billing_status']
    tmp=out/'.usage.csv.tmp'
    with tmp.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(calls)
    tmp.replace(out/'usage.csv')
    summary={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'state':'completed_full_run_provisional_cost' if provisional else 'completed_checked_full_run',
      'checker_status':checked['status'],'checker_issue_counts':checked.get('issue_counts',{}),'cost_status':'provisional' if unknown_calls else 'reconciled',
      'source_rows':660622,'completed_reviews':660609,'quarantined_rows':13,'recorded_project_attempts':len(calls),
      'typesafe_project_attempts':sum(c.get('provider')=='typesafe' for c in calls),'local_project_attempts':sum(str(c.get('provider','')).startswith('local_') for c in calls),
      'known_project_api_usd':str(calculated),'total_project_api_usd':None if unknown_calls else str(calculated),
      'full_new_known_api_usd':str(current_known),'full_new_api_usd':None if any(c.get('calculated_api_usd') is None for c in current) else str(current_known),
      'unknown_paid_request_ids':[c['request_id'] for c in unknown_calls],'authorized_liability_hold_usd':str(sum((Decimal(str(h['held_usd'])) for h in holds),Decimal(0))),
      'held_request_actual_charges':[{'request_id':c['request_id'],'actual_charge_usd':None,'input_tokens':c.get('input_tokens'),'output_tokens':c.get('output_tokens')} for c in unknown_calls],
      'full_current_phase_wall_seconds':production['wall_seconds'],'enrichment':production['enrichment'],'analysis':production['analysis'],
      'local_compute_usd':None,'provider_balance_usd':None,'hosting_invoice_usd':None,'new_model_calls':0,
      'production_phase_measurements':[json.loads(p.read_text()) for p in sorted((source/'production_phases').glob('*.json'))],
      'note':'Known cost is calculated only from saved reported usage or real provider reconciliation. Unknown actual charges remain null; liability holds are not billed usage. API consumption differs from the $5 credit purchase. Resume phase timings are separately recorded.'}
    atomic_json(out/'summary.json',summary)
    atomic_json(root/'cost/project_usage.json',{'known_project_api_consumption_usd':str(calculated),'recorded_attempts':len(calls),
      'typesafe_attempts':summary['typesafe_project_attempts'],'reserved_usd':reserved,'unknown_paid_usage':unknown,'cost_status':summary['cost_status'],'observed_at_utc':summary['observed_at_utc']})
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Offline full-run export; --provisional retains explicit unknown charges and checker flags.')
    parser.add_argument('--provisional',action='store_true');args=parser.parse_args()
    try:print(json.dumps(export(args.provisional),indent=2))
    except (FileNotFoundError,ValueError) as e:print(json.dumps({'state':'not_exported','reason':str(e)}));raise SystemExit(1)
