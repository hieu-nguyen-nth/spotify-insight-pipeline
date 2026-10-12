#!/usr/bin/env python3
"""Prepare local credential-scanned evidence/source archives; never publishes."""
import argparse,hashlib,json,subprocess,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE_DIRS=('src','tests','vendor','prompts','docs','scripts','specs','labels','dataset','backend','database')
ROOT_FILES=('.env.example','.gitignore','.gitattributes','README.md','ARCHITECTURE.md','pyproject.toml','requirements.lock.txt','pipeline.py','run.sh')
SMALL_REPORT_DIRS=('full','golden50','robustness','worker_comparison','pilot100_optimized','scope_change','deployment','submission_review')

def allowed(path):
    rel=path.relative_to(ROOT)
    return path.is_file() and not path.is_symlink() and not any(s in ('__pycache__','.venv','.vercel','.git') for s in rel.parts) and not (path.name.startswith('.env') and path.name!='.env.example') and path.suffix not in ('.pyc','.sqlite','.db','.zip')

def source_files():
    files={ROOT/n for n in ROOT_FILES}
    for name in SOURCE_DIRS:
        files.update(p for p in (ROOT/name).rglob('*') if allowed(p))
    files.update(p for p in (ROOT/'cost').rglob('*') if allowed(p) and p.stat().st_size<1024**2)
    files.update(p for p in (ROOT/'grading').glob('*') if allowed(p) and p.name!='records.jsonl')
    for name in SMALL_REPORT_DIRS:
        files.update(p for p in (ROOT/'reports'/name).rglob('*') if allowed(p))
    for name in ('checkpoint500','checkpoint10000','completed_subset'):
        files.update(p for p in (ROOT/'reports'/name).glob('*') if allowed(p) and p.stat().st_size<1024**2)
    files.update(p for p in (ROOT/'reports/full_run').glob('*') if allowed(p) and p.name!='records.json')
    files.update(p for p in (ROOT/'reports/full_run/reconciliation').rglob('*') if allowed(p))
    files.add(ROOT/'reports/readiness.json')
    files.update(ROOT/'submission'/n for n in ('README.md','requirement-audit.md'))
    if (ROOT/'submission/final_run_manifest.json').exists():files.add(ROOT/'submission/final_run_manifest.json')
    return sorted(files)

def scan(files):
    secrets=[]
    for env in (ROOT/'.env',ROOT/'backend/.env.local'):
        if not env.exists():continue
        for line in env.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                name,value=line.split('=',1);value=value.strip().strip('"\'')
                if value and len(value)>12 and any(s in name.upper() for s in ('KEY','TOKEN','PASSWORD','DB_URL')):secrets.append(value.encode())
    for path in files:
        raw=path.read_bytes()
        if any(secret in raw for secret in secrets):raise ValueError('Configured credential found in candidate file: '+str(path.relative_to(ROOT)))
    blank=[l for l in (ROOT/'.env.example').read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    if any(l.split('=',1)[1].strip() for l in blank):raise ValueError('.env.example must have empty values.')
    return {'configured_credential_scan':'passed','blank_env_example':'passed','files_scanned':len(files)}

def archive(path,files):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in files:z.write(file,str(file.relative_to(ROOT)))
    with zipfile.ZipFile(path) as z:
        if z.testzip():raise ValueError('ZIP failed integrity check')
    return {'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'files':len(files),'zip_integrity':'passed'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--list-source',action='store_true');a=p.parse_args()
    source=source_files();scan_source=scan(source)
    if a.list_source:
        (ROOT/'work/source_files.json').write_text(json.dumps([str(p.relative_to(ROOT)) for p in source],indent=2)+'\n')
        print(json.dumps(scan_source));return
    # Complete saved per-attempt handoffs are evidence, not Git blobs. No work state/keys/weights.
    evidence=sorted({p for name in ('reports','cost','grading') for p in (ROOT/name).rglob('*') if allowed(p)})
    scan_evidence=scan(evidence)
    output=ROOT/'submission';output.mkdir(exist_ok=True)
    result={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'publicly_published':False,'new_model_calls':0,
      'source':archive(output/'source-code.zip',source),'evidence':archive(output/'submission-evidence.zip',evidence),
      'source_scan':scan_source,'evidence_scan':scan_evidence,'scope':'244582 completed originals; full-source missing outputs disclosed',
      'contains_source_review_quotes':True,'contains_saved_model_request_response_handoffs':True,
      'contains_original_raw_csv':False,'contains_work_databases_credentials_or_model_weights':False,
      'publication_requires_user_scope':'Public evidence includes review quotes beyond the previously published selected dashboard examples.'}
    try:result['delivery_source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:result['delivery_source_commit']=None
    (output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
