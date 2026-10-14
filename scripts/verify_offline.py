#!/usr/bin/env python3
"""Actual fresh-copy setup/replay. Dependency install is online; replay blocks sockets."""
import argparse,csv,hashlib,json,os,re,shutil,subprocess,sys,tempfile,time,venv
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(out=None):
    if sys.version_info<(3,10):
        raise RuntimeError('Python 3.10+ required; use the setup virtual environment interpreter.')
    out=Path(out) if out else ROOT/'reports/checklist_fixes'
    out.mkdir(parents=True,exist_ok=True)
    required=('run.json','ingestion.json','records.jsonl','membership.csv','ranking.csv','claims.csv','calls.jsonl','checkpoint_before.json','checkpoint_after.json')
    if any(not (ROOT/'grading'/name).is_file() for name in required):
        raise RuntimeError('Extract the public evidence ZIP with unzip -n into the repository root first; all nine grading files are required.')
    report={'new_model_calls':0,'credentials_copied':False,'persisted_work_database_copied':False,'checks':{}}
    with tempfile.TemporaryDirectory(prefix='spotify-clean-') as tmp:
        clean=Path(tmp)/'project';clean.mkdir()
        for name in ('src','tests','scripts','vendor','prompts','dataset','backend','database','labels'):
            shutil.copytree(ROOT/name,clean/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env*','.vercel'))
        for name in ('pipeline.py','run.sh','pyproject.toml','requirements.lock.txt'):
            shutil.copy2(ROOT/name,clean/name)
        # Original 100 replay needs only these immutable inputs, not project state.
        (clean/'cost').mkdir()
        for name in ('calculator.py','export_full.py','export_subset.py','rates.csv','pilot_calls.jsonl','pilot_runs.json','pilot_records.jsonl','project_usage.json'):
            shutil.copy2(ROOT/'cost'/name,clean/'cost'/name)
        target=clean/'reports/completed_subset';target.mkdir(parents=True)
        for name in ('records.json','membership.csv','ranking.csv','claims.csv','dashboard.json','recommendations.json','ranking_sensitivity.json'):
            shutil.copy2(ROOT/'reports/completed_subset'/name,target/name)
        golden=clean/'reports/golden50';golden.mkdir()
        for name in ('human_labels_as_evaluated.csv','records.json','evaluation.json','follow_up_case_notes.json'):
            shutil.copy2(ROOT/'reports/golden50'/name,golden/name)
        original=clean/'reports/submission_review';original.mkdir()
        shutil.copy2(ROOT/'reports/submission_review/dashboard_before_result_revision.json',original/'dashboard_before_result_revision.json')
        grading=clean/'grading';grading.mkdir()
        for name in required:shutil.copy2(ROOT/'grading'/name,grading/name)
        ingestion=clean/'reports/full';ingestion.mkdir()
        shutil.copy2(ROOT/'reports/full/ingestion_report.json',ingestion/'ingestion_report.json')
        (clean/'work').mkdir()
        env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','PASSWORD','SECRET','SUPABASE','SPOTIFY','OPENAI','ANTHROPIC','GEMINI','TYPESAFE','PYTHONPATH','VIRTUAL_ENV'))}
        venv.EnvBuilder(with_pip=True).create(clean/'.venv')
        python=str(clean/'.venv/bin/python')
        def execute(label,argv,timeout=180,offline=False):
            if offline:
                wrapper="import sys,runpy; sys.addaudithook(lambda event,args: (_ for _ in ()).throw(RuntimeError('network forbidden during replay')) if event=='socket.connect' else None); target=sys.argv.pop(1); module=target=='-m'; target=sys.argv.pop(1) if module else target; runpy.run_module(target,run_name='__main__',alter_sys=True) if module else runpy.run_path(target,run_name='__main__')"
                argv=[python,'-c',wrapper,*argv]
            started=time.perf_counter();p=subprocess.run(argv,cwd=clean,env=env,capture_output=True,text=True,timeout=timeout)
            report['checks'][label]={'exit_code':p.returncode,'wall_seconds':time.perf_counter()-started,'socket_connect_blocked':offline}
            if label in ('install_dependencies','install_source','offline_tests'):
                log=(p.stdout+p.stderr).replace(str(clean),'<clean-project>').replace(tmp,'<temporary-directory>').replace(str(Path.home()),'<home>')
                log=re.sub(r'(?:/private)?/var/folders/[^\s]+', '<temporary-path>', log)
                log=re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@',r'\1<redacted>@',log)
                (out/f'fresh_{label}.txt').write_text(log)
            if p.returncode:raise RuntimeError(f'{label} failed; see credential-free test log')
            return p.stdout
        execute('install_dependencies',[python,'-m','pip','install','-r','requirements.lock.txt'],timeout=240)
        execute('install_source',[python,'-m','pip','install','-e','.','--no-deps'],timeout=240)
        # unittest subprocess also blocks network (fixtures use isolated local transports).
        execute('offline_tests',['-m','unittest','discover','-s','tests'],offline=True)
        test_log=(out/'fresh_offline_tests.txt').read_text()
        report['test_count']=int(re.search(r'Ran (\d+) tests',test_log).group(1))
        replay=json.loads(execute('calculator_default',['cost/calculator.py'],offline=True))
        rows=list(csv.DictReader((clean/'cost/rates.csv').open()))
        for row in rows:
            if not row['provider'].startswith('local_'):row['usd_per_unit']=str(Decimal(row['usd_per_unit'])*2)
        with (clean/'work/doubled_rates.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        doubled=json.loads(execute('calculator_doubled_rates',['cost/calculator.py','--rates','work/doubled_rates.csv'],offline=True))
        assert Decimal(doubled['api_subtotal_usd'])==Decimal(replay['api_subtotal_usd'])*2
        assert doubled['measurements']==replay['measurements'] and doubled['local_compute_usd']==replay['local_compute_usd']
        changed=json.loads(execute('calculator_editable_limits',['cost/calculator.py','--nonempty','100000','--unique','80000','--max-workers','2','--output-token-cap','512','--fallback-fraction','.01'],offline=True))
        assert changed['measurements']==replay['measurements'] and changed['api_subtotal_usd']==replay['api_subtotal_usd']
        assert all(s['api_usd'] is None and s['budget_assessment']=='unknown_fallback_cost' for s in changed['scenarios'])
        execute('ranking_saved_records',['pipeline.py','replay-ranking','--records','reports/completed_subset/records.json','--out','work/ranking_replay'],offline=True)
        equal={name:sha(clean/'work/ranking_replay'/name)==sha(target/name) for name in ('membership.csv','ranking.csv','claims.csv')}
        assert all(equal.values())
        audited=json.loads(execute('saved_quote_provenance',['scripts/audit_saved_evidence.py','--out','work/result_audit'],offline=True))
        assert audited['cited_reviews']==9 and audited['baseline_unchanged'] and not audited['labels_modified']
        execute('golden_export_scope',['scripts/golden_export_coverage.py','--out','work/golden_export_coverage.json'],offline=True)
        coverage=json.loads((clean/'work/golden_export_coverage.json').read_text())
        assert coverage['golden_predictions']==50 and coverage['final_export_overlap']==20 and coverage['completed_overlap']==20
        shutil.copy2(clean/'work/golden_export_coverage.json',out/'golden_export_coverage.json')
        (out/'saved_quote_provenance.json').write_text(json.dumps(audited,indent=2)+'\n')
        (out/'calculator_replay.json').write_text(json.dumps(replay,indent=2)+'\n')
        assert not (clean/'.env').exists() and not (clean/'work/control.sqlite').exists()
        report.update(status='pass',byte_identical_exports=equal,grading_files_present=list(required),doubled_rate_arithmetic='pass',changed_limits_preserve_measurements=True,unpriced_fallback_remains_unknown=True,
          python_version=subprocess.check_output([python,'--version'],env=env,text=True).strip(),offline_socket_policy='Every test, calculator and ranking replay process installed a socket.connect-denying audit hook.',
          dependency_install_network='Package index only; dependency install is not claimed offline.',
          limitation='Fresh copy of exact source and saved evidence; public-checkout download verification is a separate delivery check.')
    (out/'clean_environment_check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,help='Saved verification report directory; defaults to reports/checklist_fixes.')
    run(parser.parse_args().out)
