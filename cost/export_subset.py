"""Offline actual stopped-project accounting. Unknown charges remain null."""
import argparse
import csv
import json
import shutil
import sqlite3
import sys
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from spotify_pipeline.core import atomic_json,course
from spotify_pipeline.analysis import jsonl_save,csv_save
from spotify_pipeline.budget_policy import dispatch_block_reason

def export():
    source=ROOT/'reports/completed_subset';out=ROOT/'cost/completed_subset'
    frozen=json.loads((source/'scope_manifest.json').read_text());checked=json.loads((source/'subset_integrity.json').read_text())
    if checked['status']!='pass' or checked['completed_count']!=frozen['completed_reviews'] or course.sha(source/'records.json')!=frozen['records_sha256']:
        raise ValueError('Check the exact completed subset before exporting its project accounting.')
    db=sqlite3.connect('file:'+str(ROOT/'work/control.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN');calls=[json.loads(r[0]) for r in db.execute('SELECT call_json FROM calls ORDER BY rowid')]
        b=dict(db.execute('SELECT * FROM budget').fetchone());holds=[dict(r) for r in db.execute('SELECT * FROM unknown_charge_holds WHERE active=1')]
        if db.execute('SELECT 1 FROM run_locks').fetchone() or any(c['outcome']=='in_flight' for c in calls):raise ValueError('Wait for all work to settle.')
        if dispatch_block_reason(db):raise ValueError('Any unknown charge needs its explicit authorized hold.')
    finally:db.close()
    unknown=[c for c in calls if c.get('calculated_api_usd') is None]
    if {c['request_id'] for c in unknown}!={h['request_id'] for h in holds}:raise ValueError('Unknown actual charges differ from approved holds.')
    known=sum((Decimal(str(c['calculated_api_usd'])) for c in calls if c.get('calculated_api_usd') is not None),Decimal(0))
    if abs(known-Decimal(str(b['spent'])))>Decimal('.000000001') or known+Decimal(str(b['reserved']))>Decimal('4.800000001'):
        raise ValueError('Known saved usage differs from the ledger or exceeds the cap.')
    displayed_known=known.quantize(Decimal('.000000000001'))
    out.mkdir(exist_ok=True);jsonl_save(out/'project_calls.jsonl',calls)
    fields=['request_id','run_id','provider','model','role','outcome','input_tokens','output_tokens','elapsed_seconds','calculated_api_usd','usage_status','billing_status']
    csv_save(out/'usage.csv',calls,fields);shutil.copyfile(ROOT/'cost/rates.csv',out/'rates.csv')
    summary={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'state':'completed_subset_stopped_project_accounting',
      'scope':'244582 completed original reviews; all project attempts including unused partial work remain in accounting',
      'completed_reviews':frozen['completed_reviews'],'source_rows_ingested':660622,'source_empty_quarantines':13,
      'uncompleted_nonempty_reviews':frozen['uncompleted_nonempty_reviews'],'known_project_api_usd':str(displayed_known),
      'total_project_api_usd':None if unknown else str(displayed_known),'unknown_paid_request_ids':[c['request_id'] for c in unknown],
      'unknown_charge_hold_usd':b['reserved'],'api_ceiling_usd':4.8,'user_reported_credit_purchase_usd':5,
      'recorded_project_attempts':len(calls),'typesafe_attempts':sum(c.get('provider')=='typesafe' for c in calls),
      'cost_status':'provisional' if unknown else 'reconciled','local_compute_usd':None,'hosting_invoice_usd':None,
      'provider_balance_usd':None,'new_model_calls':0,'subset_integrity_status':checked['status'],
      'instructor_checker_status':checked['instructor_checker_status'],'instructor_checker_issue_counts':checked['instructor_checker_issue_counts'],
      'analysis_measurement':json.loads((source/'analysis_run.json').read_text()),
      'stopped_enrichment_phase':json.loads((ROOT/'reports/full_run/enrichment_run.json').read_text()),
      'earlier_production_phases':[json.loads(p.read_text()) for p in sorted((ROOT/'reports/full_run/production_phases').glob('*.json'))],
      'note':'The $5 purchase funds API usage; do not add both as separate expenses. Hold is a liability allowance, not a measured charge. Phase wall times are separately measured; request durations are not an invented end-to-end duration. Unfinished classifications are preserved, not treated as completed.'}
    atomic_json(out/'summary.json',summary)
    atomic_json(ROOT/'cost/project_usage.json',{'known_api_consumption_usd':str(displayed_known),'known_project_api_consumption_usd':str(displayed_known),
      'recorded_attempts':len(calls),'actual_paid_attempts':summary['typesafe_attempts'],'unresolved_paid_usage':len(unknown),
      'reserved_usd':b['reserved'],'project_api_cap_usd':4.8,'cost_status':summary['cost_status'],'observed_at_utc':summary['observed_at_utc']})
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    try:print(json.dumps(export(),indent=2))
    except (FileNotFoundError,ValueError) as e:print(json.dumps({'state':'not_exported','reason':str(e)}));raise SystemExit(1)
