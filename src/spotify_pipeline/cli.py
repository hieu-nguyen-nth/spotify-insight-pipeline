import argparse
import json
from pathlib import Path

from .core import ROOT, atomic_json, configuration, connect, ingest, request_body, status, verify_dataset
from .costs import replay


def main(argv=None):
    parser = argparse.ArgumentParser(description="Spotify pipeline foundation: offline by default; paid calls are explicit.")
    sub = parser.add_subparsers(dest="command",required=True)
    check = sub.add_parser("check-dataset",help="Verify actual files against the supplied manifest; no API calls")
    check.add_argument("--directory",required=True)
    check.add_argument("--out",default=str(ROOT/"reports/dataset_checks.json"))
    ing = sub.add_parser("ingest",help="Read every source row and build resumable local state; no API calls")
    ing.add_argument("--input",required=True)
    ing.add_argument("--db",required=True)
    ing.add_argument("--out",required=True)
    ing.add_argument("--manifest")
    st = sub.add_parser("status",help="Show actual accounting and classification progress; no API calls")
    st.add_argument("--db",required=True)
    prep = sub.add_parser("prepare-request",help="Save a real one-review Jev request for inspection; no API calls")
    prep.add_argument("--db",required=True)
    prep.add_argument("--out",default=str(ROOT/"reports/first_request.json"))
    paid = sub.add_parser("paid-enrich",help="Explicit PAID enrichment smoke test; not the complete 100-review pilot")
    paid.add_argument("--execute-paid",action="store_true",required=True)
    paid.add_argument("--db",required=True)
    paid.add_argument("--out",default=str(ROOT/"reports/smoke_enrichment"))
    paid.add_argument("--env-file",default=str(ROOT/".env"))
    paid.add_argument("--limit",type=int,default=1)
    paid.add_argument("--budget-usd",type=float,default=0.25)
    off = sub.add_parser("cost-replay",help="Offline replay of saved usage; no credentials or model calls")
    off.add_argument("--calls",required=True)
    off.add_argument("--rates",default=str(ROOT/"cost/rates.csv"))
    off.add_argument("--out")
    probe = sub.add_parser("cost-probe",help="Prepare paired development cost experiment offline; paid execution requires explicit flag")
    probe.add_argument("--db",required=True)
    probe.add_argument("--out",default=str(ROOT/"reports/cost_optimization"))
    probe.add_argument("--env-file",default=str(ROOT/".env"))
    probe.add_argument("--execute-paid",action="store_true")
    probe_off = sub.add_parser("cost-probe-replay",help="Recompute saved paired cost experiment offline; never calls models")
    probe_off.add_argument("--out",default=str(ROOT/"reports/cost_optimization"))
    probe_off.add_argument("--rates",default=str(ROOT/"cost/rates.csv"))
    probe_off.add_argument("--projected-unique",type=int,default=484189)
    probe_off.add_argument("--projected-nonempty",type=int,default=660609)
    lab = sub.add_parser("label-ui",help="Open a local human annotation screen; no model calls")
    lab.add_argument("--port",type=int,default=8765)
    lean = sub.add_parser("lean-pilot",help="Prepare the optimized pilot offline; paid execution requires --execute-paid")
    lean.add_argument("--db",required=True)
    lean.add_argument("--out",default=str(ROOT/"reports/pilot100"))
    lean.add_argument("--scope",default="pilot100")
    lean.add_argument("--batch-size",type=int,default=20)
    lean.add_argument("--execute-paid",action="store_true")
    lean.add_argument("--prompt-version",choices=["v2","v3"],default="v2")
    lean.add_argument("--additional-cap-usd",type=float,default=.05)
    analyze = sub.add_parser("analyze-pilot",help="Blind verification and local grouping/memo; explicit paid verification flag")
    analyze.add_argument("--db",required=True)
    analyze.add_argument("--out",default=str(ROOT/"reports/pilot100"))
    analyze.add_argument("--execute-paid",action="store_true")
    analyze.add_argument('--output-token-cap',type=int,default=1024)
    pilot = sub.add_parser("pilot-run",help="Explicit paid end-to-end 100-review cold/warm pilot")
    pilot.add_argument("--execute-paid",action="store_true",required=True)
    pilot.add_argument("--interrupt-demo",action="store_true")
    pilot.add_argument("--batch-size",type=int,default=50)
    pilot.add_argument("--scope",default="pilot100_final")
    pilot.add_argument("--out",default=str(ROOT/'reports/pilot100_final'))
    pilot.add_argument("--prompt-version",choices=['v2','v3'],default='v2')
    pilot.add_argument("--additional-cap-usd",type=float,default=.002)
    exp = sub.add_parser("pilot-export",help="Export saved complete pilot measurements offline; no calls")
    exp.add_argument("--out",default=str(ROOT/'reports/pilot100_optimized'))
    ev=sub.add_parser('evaluate',help='Score saved predictions against human labels offline; never sends labels')
    ev.add_argument('--predictions',default=str(ROOT/'reports/golden50/records.json'))
    ev.add_argument('--out',default=str(ROOT/'reports/golden50/evaluation.json'))
    audit=sub.add_parser('pilot-check',help='Export and mechanically audit the 100-review pilot; no API calls')
    audit.add_argument('--out',default=str(ROOT/'reports/pilot100_optimized'))
    audit.add_argument('--reference',default=str(ROOT/'work/pilot100_reference.json'))
    sub.add_parser('local-robustness',help='Run isolated local model injection tests and offline planted-ranking checker test; zero API charges')
    checkpoint=sub.add_parser('checkpoint-run',help='Prepare 500/10,000 offline; explicit paid flag measures enrichment and analysis')
    checkpoint.add_argument('--size',type=int,choices=[500,10000],required=True)
    checkpoint.add_argument('--execute-paid',action='store_true')
    checkpoint.add_argument('--additional-cap-usd',type=float)
    checkpoint_check=sub.add_parser('checkpoint-check',help='Export and audit completed checkpoint offline; no model calls')
    checkpoint_check.add_argument('--size',type=int,choices=[500,10000],required=True)
    checkpoint_check.add_argument('--full-input')
    checkpoint_export=sub.add_parser('checkpoint-export',help='Export real checkpoint usage to the offline calculator; no model calls')
    checkpoint_export.add_argument('--size',type=int,choices=[500,10000],required=True)
    store=sub.add_parser('save-analysis',help='Validate and persist saved analysis/dashboard artifacts offline; no model calls')
    store.add_argument('--out',required=True)
    full=sub.add_parser('full-run',help='Prepare full-source cache offline; full paid inference requires explicit flag and adequate disk space')
    full.add_argument('--execute-paid',action='store_true')
    full.add_argument('--project-cap-usd',type=float,default=4.8)
    sub.add_parser('full-check',help='Export completed full-source grading and run the supplied checker offline')
    sub.add_parser('full-status',help='Read current frozen full-scope progress and shared spend offline')
    sub.add_parser('freeze-subset',help='Freeze the explicitly user-stopped completed subset offline; no model calls')
    sub.add_parser('subset-check',help='Audit completed-subset integrity and retain unchanged full-source checker findings')
    subset_analysis=sub.add_parser('analyze-subset',help='Analyze the frozen subset; explicit paid flag permits only blind verification')
    subset_analysis.add_argument('--execute-paid',action='store_true')
    subset_analysis.add_argument('--verification-size',type=int,default=1000)
    ranks=sub.add_parser('replay-ranking',help='Regenerate membership, ranking and claims from saved records; no keys or model calls')
    ranks.add_argument('--records',default=str(ROOT/'reports/completed_subset/records.json'))
    ranks.add_argument('--out',default=str(ROOT/'work/ranking_replay'))
    settle=sub.add_parser('reconcile-usage',help='Validate real provider evidence offline; apply only with an explicit flag; no model calls')
    settle.add_argument('--evidence',required=True)
    settle.add_argument('--apply',action='store_true')
    hold=sub.add_parser('authorize-unknown-hold',help='Preview a documented user-approved liability hold offline; apply only with explicit flag')
    hold.add_argument('--authorization',required=True)
    hold.add_argument('--apply',action='store_true')
    primary=sub.add_parser('jev-robustness',help='Prepare isolated synthetic injection checks offline; API execution is explicit')
    primary.add_argument('--execute-paid',action='store_true')
    primary.add_argument('--additional-cap-usd',type=float,default=.003)
    args = parser.parse_args(argv)
    try:
        if args.command == "check-dataset":
            result = verify_dataset(args.directory)
            atomic_json(args.out,result)
        elif args.command == "ingest":
            result = ingest(args.input,args.db,args.out,args.manifest)
        elif args.command == "status":
            _,label_config = configuration()
            result = status(args.db,label_config)
        elif args.command == "prepare-request":
            db = connect(args.db)
            source = db.execute("SELECT * FROM source_reviews WHERE source_status='pending' ORDER BY source_order LIMIT 1").fetchone()
            if not source:
                raise ValueError("No nonempty source reviews; ingest first.")
            config,label_config = configuration()
            body = request_body(source["review_text"],config)
            atomic_json(args.out,{"review_id":source["review_id"],"source_sha256":source["source_sha256"],
                       "label_config":label_config,"body":body,"sent":False})
            result = {"saved":args.out,"review_id":source["review_id"],"sent":False,
                      "payload_utf8_bytes":len(json.dumps(body,ensure_ascii=False).encode()),
                      "billed_tokens":None,"note":"Payload size is not measured token usage."}
            db.close()
        elif args.command == "paid-enrich":
            raise ValueError('Historical v1 paid entry point retired. Use lean-pilot or pilot-run with the shared project ledger. Historical replay remains available.')
        elif args.command == "cost-probe":
            from .cost_probe import plan,run
            if args.execute_paid:raise ValueError('Historical paired-probe execution is retired; use lean-pilot with the shared project ledger. Replay remains available.')
            result = plan(args.db,args.out)[0]
        elif args.command == "cost-probe-replay":
            from .cost_probe import replay as probe_replay
            result = probe_replay(args.out,args.rates,args.projected_unique,args.projected_nonempty)
        elif args.command == "label-ui":
            from .label_ui import serve
            serve(port=args.port)
            return 0
        elif args.command == "lean-pilot":
            from .lean import enrich
            result = enrich(args.db,args.out,args.scope,args.batch_size,args.execute_paid,version=args.prompt_version,additional_cap=args.additional_cap_usd)
        elif args.command == "analyze-pilot":
            from .analysis import analyze as analyze_run
            result = analyze_run(args.db,args.out,args.execute_paid,output_token_cap=args.output_token_cap)
        elif args.command == "pilot-run":
            from .pilot import run as pilot_run
            result = pilot_run(outdir=args.out,scope=args.scope,batch_size=args.batch_size,interrupt_demo=args.interrupt_demo,version=args.prompt_version,additional_cap=args.additional_cap_usd)
        elif args.command == "pilot-export":
            from .pilot import export_cost
            result = export_cost(args.out)
        elif args.command=='evaluate':
            from .evaluation import evaluate
            result=evaluate(ROOT/'labels/golden_50_human.csv',args.predictions,args.out)
        elif args.command=='pilot-check':
            from .pilot import audit_pilot
            result=audit_pilot(args.out,args.reference)
        elif args.command=='local-robustness':
            from .robustness import run as robustness_run
            result=robustness_run()
        elif args.command=='checkpoint-run':
            from .checkpoint import run as checkpoint_run
            result=checkpoint_run(args.size,args.execute_paid,args.additional_cap_usd)
        elif args.command=='checkpoint-check':
            from .checkpoint import audit as checkpoint_audit
            result=checkpoint_audit(args.size,args.full_input)
        elif args.command=='checkpoint-export':
            from .checkpoint import export as checkpoint_export_run
            result=checkpoint_export_run(args.size)
        elif args.command=='save-analysis':
            from .storage import save as save_analysis
            result=save_analysis(args.out)
        elif args.command=='full-run':
            from .production import run as full_run
            result=full_run(args.execute_paid,args.project_cap_usd)
        elif args.command=='full-check':
            from .production import audit as full_audit
            result=full_audit()
        elif args.command=='full-status':
            from .production import status as full_status
            result=full_status()
        elif args.command=='freeze-subset':
            from .subset import freeze
            result=freeze()
        elif args.command=='subset-check':
            from .subset import audit
            result=audit()
        elif args.command=='analyze-subset':
            from .subset import INPUT,OUT
            from .analysis import analyze
            if args.execute_paid:result=analyze(INPUT,OUT,True,verification_size=args.verification_size)
            else:result={'scope':'completed_subset','paid_execution':False,'new_model_calls':0,'execute_command':'./run.sh analyze-subset --execute-paid --verification-size 1000'}
        elif args.command=='replay-ranking':
            from .analysis import ranking,csv_save
            records=json.loads(Path(args.records).read_text());members,ranked,claims=ranking(records);out=Path(args.out)
            csv_save(out/'membership.csv',members,['issue_id','review_id'])
            csv_save(out/'ranking.csv',ranked,['rank','issue_id','complaint_count','severity_sum','mean_severity','priority_score'])
            csv_save(out/'claims.csv',claims,['claim_id','issue_id','metric','value'])
            result={'completed_records':len(records),'membership_rows':len(members),'ranked_issues':len(ranked),'new_model_calls':0,'out':str(out)}
        elif args.command=='reconcile-usage':
            from .reconciliation import reconcile
            result=reconcile(args.evidence,args.apply,outdir=ROOT/'reports/full_run/reconciliation')
        elif args.command=='authorize-unknown-hold':
            from .budget_policy import authorize_hold
            result=authorize_hold(args.authorization,args.apply,outdir=ROOT/'reports/full_run/reconciliation')
        elif args.command=='jev-robustness':
            from .primary_robustness import run as primary_run
            result=primary_run(args.execute_paid,args.additional_cap_usd)
        else:
            result = replay(args.calls,args.rates)
            if args.out:
                atomic_json(args.out,result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get("passed",result.get('all_passed',True)) else 1
    except (ValueError,OSError,KeyError) as exc:
        # Known errors contain no request headers, provider error bodies, or key values.
        print("Stopped: "+str(exc))
        return 1
