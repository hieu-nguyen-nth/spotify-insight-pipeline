#!/usr/bin/env python3
"""Saved-measurement replay only. No model clients, credentials or network I/O."""
import argparse
import csv
import json
import math
from decimal import Decimal
from pathlib import Path

HERE=Path(__file__).resolve().parent

def calculate(runs,calls,rate_rows,unique=484189,nonempty=660609,budget=4.8,verification_max=1000,retry_fraction=.05,prior_spend=0,checkpoint_allowance=0,completed_unique=0,max_workers=1,output_token_cap=1024,fallback_fraction=0,fallback_usd_per_review=None):
    if not 0 < unique <= nonempty or verification_max < 1 or min(Decimal(str(v)) for v in (budget,retry_fraction,prior_spend,checkpoint_allowance))<0:
        raise ValueError('Volumes, budgets and allowances must be valid nonnegative values.')
    if type(completed_unique) is not int or not 0<=completed_unique<=unique:
        raise ValueError('Completed distinct-text credit must be an integer within the projected unique count.')
    if type(max_workers) is not int or not 1<=max_workers<=2 or type(output_token_cap) is not int or not 32<=output_token_cap<=4096:
        raise ValueError('Choose one or two planned workers and a 32–4096 local output cap.')
    if not math.isfinite(fallback_fraction) or not 0<=fallback_fraction<=1 or (fallback_usd_per_review is not None and (not math.isfinite(fallback_usd_per_review) or fallback_usd_per_review<0)):
        raise ValueError('Fallback planning fraction/rate must be finite and nonnegative.')
    prices={(r['provider'],r['model'],r['unit']):Decimal(r['usd_per_unit']) for r in rate_rows}
    stages={};unknown=[]
    for call in calls:
        if call.get('provider','').startswith('local_'):
            amount=Decimal(0)  # Local inference has no API bill; compute cost remains unknown.
        elif call.get('input_tokens') is None or call.get('output_tokens') is None:
            unknown.append(call['request_id']);continue
        else:
            inp=call['input_tokens'];cached=call.get('cached_input_tokens',0)
            if not 0<=cached<=inp:raise ValueError('Invalid cached token usage.')
            units={'input_token':inp-cached,'output_token':call['output_tokens']}
            if cached:units['cached_input_token']=cached
            amount=sum((Decimal(v)*prices[(call['provider'],call['model'],unit)] for unit,v in units.items()),Decimal(0))
        stages[call['role']]=stages.get(call['role'],Decimal(0))+amount
    cold=next((r for r in runs if r.get('temperature')=='cold'),None)
    if cold is None:cold=next((r for r in runs if r.get('state')=='completed' and r.get('new_unique_enrichment_work',0)>0),None)
    warm=next((r for r in runs if r.get('temperature')=='warm'),None)
    if cold is None:raise ValueError('A real completed cold run is required.')
    # Calls may span interrupted/resumed enrichment and downstream runs; include the actual cold attempts.
    cold_calls=calls if warm is None else calls[:cold['model_requests']]
    enrichment=sum((Decimal(c.get('input_tokens') or 0)*prices[(c['provider'],c['model'],'input_token')]+Decimal(c.get('output_tokens') or 0)*prices[(c['provider'],c['model'],'output_token')] for c in cold_calls if c['role']=='enrich' and c.get('input_tokens') is not None),Decimal(0))
    verify_calls=[c for c in cold_calls if c['role']=='verify']
    verify_n=sum(len(c['review_ids']) for c in verify_calls)
    verify_cost=sum((Decimal(c['input_tokens'])*prices[(c['provider'],c['model'],'input_token')]+Decimal(c['output_tokens'])*prices[(c['provider'],c['model'],'output_token')] for c in verify_calls if c.get('input_tokens') is not None),Decimal(0))
    measured_enrichment_work=cold.get('new_unique_enrichment_work',cold['unique_texts'])
    variable_per_unique=enrichment/Decimal(measured_enrichment_work)
    verification_per_review=verify_cost/Decimal(verify_n) if verify_n else None
    scenarios=[]
    for name,work,retries in [('exact_text_reuse',unique-completed_unique,0),('no_reuse',nonempty,0),('conservative',unique-completed_unique,retry_fraction)]:
        verifies=min(verification_max,nonempty)
        base=variable_per_unique*Decimal(work)
        extra=verification_per_review*Decimal(verifies) if verification_per_review is not None else None
        fallback_work=math.ceil(nonempty*fallback_fraction)
        fallback_cost=Decimal(str(fallback_usd_per_review))*fallback_work if fallback_usd_per_review is not None else (Decimal(0) if not fallback_work else None)
        total=(base+(extra or Decimal(0)))*(1+Decimal(str(retries)))+(fallback_cost or Decimal(0))
        project_total=total+Decimal(str(prior_spend))+Decimal(str(checkpoint_allowance))
        enrich_seconds=cold['stage_seconds']['enrich']*work/measured_enrichment_work*(1+retries)
        verify_seconds=cold['stage_seconds'].get('verify',0)*verifies/verify_n if verify_n else None
        fixed_seconds=cold['stage_seconds'].get('group',0)+cold['stage_seconds'].get('memo',0)
        # Full preparation is an actual earlier full ingestion; grouping/ranking scaling is still an estimate.
        full_profile=HERE.parent/'reports/full/ingestion_report.json'
        preparation=json.loads(full_profile.read_text())['ingestion_seconds'] if full_profile.exists() else None
        rank_seconds=cold['stage_seconds'].get('rank',0)*nonempty/cold['input_rows']
        elapsed=enrich_seconds+(verify_seconds or 0)+fixed_seconds+rank_seconds+(preparation or 0)
        scenarios.append({'name':name,'unique_enrichment_work':work,'verification_work':verifies,'retry_fraction':retries,'fallback_fraction':fallback_fraction,
                          'fallback_work':fallback_work,'fallback_api_usd':str(fallback_cost) if fallback_cost is not None else None,
                          'fallback_rate_basis':'User-supplied hypothetical per-review assumption; no fallback execution measured.',
                          'api_usd':str(total) if extra is not None and not unknown and fallback_cost is not None else None,'known_api_subtotal_usd':str(total),
                          'seconds_estimate':elapsed if not fallback_work else None,'known_seconds_estimate':elapsed,'fixed_language_seconds':fixed_seconds,'local_compute_usd':None,
                          'planned_workers':max_workers,'concurrency_time_basis':'One-worker stage measurements retained; no automatic division by workers.',
                          'project_api_usd_with_allowances':str(project_total) if extra is not None and not unknown and fallback_cost is not None else None,
                          'budget_assessment':'unknown_fallback_cost' if fallback_cost is None else ('exceeds' if project_total>Decimal(str(budget)) else 'within_known_api_scenario'),
                          'exceeds_api_budget':project_total>Decimal(str(budget)),
                          'basis':'Stage throughput per newly enriched distinct text; plus prior consumption and checkpoint allowance. Extrapolation, not full execution.'})
    subtotal=sum(stages.values(),Decimal(0))
    return {'offline':True,'new_model_calls':0,'measurements':runs,'attempted_calls':len(calls),
            'api_subtotal_usd':str(subtotal),'api_total_usd':str(subtotal) if not unknown else None,
            'stage_api_usd':{k:str(v) for k,v in stages.items()},'unknown_usage_request_ids':unknown,
            'api_usd_per_1000_pilot_rows':str(subtotal/Decimal(cold['input_rows'])*1000),
            'api_usd_per_completed_pilot_record':str(subtotal/Decimal(cold['completed'])),
            'projected_nonempty':nonempty,'projected_unique_texts':unique,'empty_quarantines':13,
            'measured_enrichment_work':measured_enrichment_work,'measurement_input_rows':cold['input_rows'],
            'validated_completed_unique_credit':completed_unique,
            'api_budget_usd':budget,'user_reported_credit_purchase_usd':5,'other_provider_purchases_usd':0,
            'prior_project_api_consumption_usd':str(prior_spend),'checkpoint_planning_allowance_usd':str(checkpoint_allowance),
            'remaining_api_budget_before_checkpoints_usd':str(Decimal(str(budget))-Decimal(str(prior_spend))),
            'local_compute_usd':None,'hosting_cost_usd':None,'worker_limit':max_workers,'output_token_cap_local':output_token_cap,
            'measured_worker_limit':1,'measured_local_output_cap':1024,
            'stronger_fallback_limit':fallback_fraction,'execution_fallback_limit':0,'scenarios':scenarios,'warm_run_recorded':warm is not None,
            'planning_limits_note':'Editable limits apply to planning; saved measurements remain unchanged. Positive fallback execution is unsupported. Output/time effects of new limits are unmeasured.',
            'scaling_decision':('10000 measurement is complete; validate full-source transfer, storage and total budget before explicit full dispatch.' if cold['input_rows']>=10000 else 'Measure 500, then 10,000 and validate quality before explicitly starting the full run.')}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rates',type=Path,default=HERE/'rates.csv');p.add_argument('--unique',type=int,default=484189);p.add_argument('--nonempty',type=int,default=660609);p.add_argument('--budget',type=float,default=4.8);p.add_argument('--verification-max',type=int,default=1000);p.add_argument('--retry-fraction',type=float,default=.05);p.add_argument('--out',type=Path)
    p.add_argument('--prior-spend',type=float,default=None,help='Override saved actual project API consumption; not a new purchase.')
    p.add_argument('--checkpoint-allowance',type=float,default=.125,help='Unmeasured planning allowance for 500 and 10,000; replace after measurements.')
    p.add_argument('--checkpoint-size',type=int,choices=[500,10000],help='Project from a saved incremental checkpoint; default is the original cold/warm 100.')
    p.add_argument('--completed-unique',type=int,default=0,help='Credit only verified completed distinct originals that can transfer to the target; default assumes no cross-scope transfer.')
    p.add_argument('--max-workers',type=int,default=1)
    p.add_argument('--output-token-cap',type=int,default=1024)
    p.add_argument('--fallback-fraction',type=float,default=0)
    p.add_argument('--fallback-usd-per-review',type=float,help='Explicit hypothetical rate; omitted nonzero fallback costs remain unknown.')
    args=p.parse_args()
    with args.rates.open(newline='') as f:price=list(csv.DictReader(f))
    if args.checkpoint_size:
        folder=HERE/'checkpoints'/str(args.checkpoint_size)
        runs=[json.loads((folder/'run.json').read_text())];calls=[json.loads(x) for x in (folder/'calls.jsonl').read_text().splitlines()]
    else:
        runs=json.loads((HERE/'pilot_runs.json').read_text());calls=[json.loads(x) for x in (HERE/'pilot_calls.jsonl').read_text().splitlines()]
    prior=args.prior_spend
    if prior is None:
        snapshot=HERE/'project_usage.json'
        if not snapshot.exists():raise ValueError('Saved project consumption is required, or specify --prior-spend explicitly.')
        prior=json.loads(snapshot.read_text())['known_api_consumption_usd']
    result=calculate(runs,calls,price,args.unique,args.nonempty,args.budget,args.verification_max,args.retry_fraction,prior,args.checkpoint_allowance,args.completed_unique,args.max_workers,args.output_token_cap,args.fallback_fraction,args.fallback_usd_per_review)
    raw=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.write_text(raw)
    print(raw,end='')

if __name__=='__main__':main()
