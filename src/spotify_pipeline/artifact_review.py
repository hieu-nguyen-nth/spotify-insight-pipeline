"""Preserve the instructor's result while distinguishing a documented usage-only flag."""
import hashlib
import json
from pathlib import Path
from .core import ROOT,course
from .budget_policy import dispatch_block_reason

FULL_COVERAGE={'expected':660622,'received_lines':660622,'unique_expected_ids':660622,
              'valid_completed':660609,'quarantined':13,'missing':0,'duplicate_ids':0,'invalid_or_unresolved':0,'labelable':660609}

def assess(checked,calls,db):
    if any(checked.get('coverage',{}).get(k)!=v for k,v in FULL_COVERAGE.items()):
        raise ValueError('Full artifacts require exact, complete source coverage with no invalid records.')
    if db.execute('SELECT 1 FROM run_locks LIMIT 1').fetchone() or dispatch_block_reason(db):
        raise ValueError('Full artifacts require no active run, in-flight request or unauthorized unknown charge.')
    missing=[]
    for call in calls:
        if any(call.get(k) is not None and (type(call[k]) is not int or call[k]<0) for k in ('input_tokens','output_tokens')):
            raise ValueError('Reported token usage must be real nonnegative integers or explicitly unavailable.')
        fields=[k for k in ('input_tokens','output_tokens') if call.get(k) is None]
        if not fields:continue
        rid=call.get('request_id');hold=db.execute('SELECT * FROM unknown_charge_holds WHERE request_id=?',(rid,)).fetchone()
        row=db.execute('SELECT call_json FROM calls WHERE request_id=?',(rid,)).fetchone()
        if not hold or not row or call.get('outcome')!='failed' or call.get('provider')!='typesafe':
            raise ValueError('Missing usage must correspond to the documented approved failed request.')
        auth=json.loads(hold['authorization_json']);actual=json.loads(row[0])
        if (hashlib.sha256(hold['authorization_json'].encode()).hexdigest()!=hold['authorization_sha256']
            or auth.get('source')!='explicit_user_instruction' or auth.get('explicit_user_authorization') is not True
            or auth.get('request_id')!=rid or auth.get('project_cap_usd')!=4.8 or auth.get('held_usd')!=hold['held_usd']):
            raise ValueError('Failed-request review exception lacks valid explicit authorization.')
        if any(call.get(k)!=actual.get(k) for k in ('outcome','provider','model','label_config','input_tokens','output_tokens','calculated_api_usd')):
            raise ValueError('Saved checker call evidence is stale; rerun full-check after reconciliation.')
        if not hold['active'] and not actual.get('reconciliation'):
            raise ValueError('An inactive hold must retain its genuine provider reconciliation evidence.')
        missing.extend({'code':'invalid_usage','detail':rid,'unavailable_field':k} for k in fields)
    counts=checked.get('issue_counts',{})
    if checked.get('status')=='pass':
        if counts or missing:raise ValueError('A passing checker cannot hide missing usage or reported findings.')
    elif checked.get('status')=='review_required':
        examples=checked.get('examples',[])
        expected=[{'code':m['code'],'detail':m['detail']} for m in missing]
        if not missing or counts!={'invalid_usage':len(missing)} or sorted(examples,key=str)!=sorted(expected,key=str):
            raise ValueError('Only the documented failed request missing-usage findings may accompany verified full artifacts.')
    else:raise ValueError('A real full checker result is required.')
    return {'checker_status':checked['status'],'checker_passed':checked['status']=='pass',
            'mechanical_data_and_ranking_checks':'passed','coverage':checked['coverage'],
            'checker_issue_counts':counts,'checker_examples':checked.get('examples',[]),
            'unavailable_usage':missing,'cost_status':'provisional' if db.execute('SELECT unknown_charges FROM budget').fetchone()[0] else 'reconciled',
            'note':'The instructor checker result is preserved. A usage-only review flag is not a full checker pass.'}

def saved_full_review(db,root=ROOT):
    root=Path(root);out=root/'reports/full_run'
    production=json.loads((out/'production_run.json').read_text());checked=json.loads((out/'self_check.json').read_text())
    if production.get('state')!='completed':raise ValueError('Complete the actual full pipeline before artifact publication.')
    if checked.get('audit_script_sha256')!=course.sha(ROOT/'vendor/check_submission.py'):
        raise ValueError('Use the unchanged supplied instructor checker.')
    fingerprints=checked.get('input_files_sha256',{})
    required={'calls.jsonl','records.jsonl','ranking.csv','membership.csv','claims.csv','run.json','ingestion.json','checkpoint_before.json','checkpoint_after.json'}
    if not required.issubset(fingerprints):raise ValueError('Full checker evidence is incomplete.')
    for name,digest in fingerprints.items():
        if Path(name).name!=name or course.sha(root/'grading'/name)!=digest:
            raise ValueError('Checked grading artifacts changed; rerun the unchanged checker.')
    calls=[json.loads(line) for line in (root/'grading/calls.jsonl').read_text().splitlines() if line.strip()]
    return assess(checked,calls,db)
