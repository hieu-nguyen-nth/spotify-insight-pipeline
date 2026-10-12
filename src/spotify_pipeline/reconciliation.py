"""Evidence-based settlement of failed calls. Offline preview unless explicitly applied."""
import hashlib
import json
from decimal import Decimal,InvalidOperation
from pathlib import Path
from .core import atomic_json,course,ROOT
from .lean import control,CONTROL,RATE_PER_TOKEN

def reconcile(evidence_path,apply=False,control_path=CONTROL,outdir=None):
    path=Path(evidence_path);raw=path.read_bytes();e=json.loads(raw)
    if e.get('source') not in ('provider_export','provider_support_confirmation','user_checked_provider_dashboard'):
        raise ValueError('Identify real provider evidence; do not use a reservation or model estimate.')
    if not isinstance(e.get('evidence_description'),str) or not e['evidence_description'].strip() or not e.get('observed_at_utc'):
        raise ValueError('Describe the provider evidence and observation time.')
    if e.get('billing_outcome') not in ('charged','confirmed_no_charge'):
        raise ValueError('Provider evidence must establish charged or confirmed_no_charge.')
    try:amount=Decimal(str(e.get('actual_charge_usd')))
    except InvalidOperation:raise ValueError('Provide a real provider charge, not an empty or estimated value.')
    if not amount.is_finite() or amount<0:raise ValueError('Actual charge must be a finite nonnegative USD amount.')
    if e['billing_outcome']=='confirmed_no_charge' and amount!=0:raise ValueError('No-charge evidence must establish zero charge.')
    for field in ('input_tokens','output_tokens'):
        if e.get(field) is not None and (type(e[field]) is not int or e[field]<0):raise ValueError('Token values must be real nonnegative integers or null when unavailable.')
    if e.get('input_tokens') is not None and abs(amount-Decimal(str(RATE_PER_TOKEN))*e['input_tokens'])>Decimal('0.000000001'):
        raise ValueError('Token usage and supplied charge disagree with the frozen dated rate.')
    digest=hashlib.sha256(raw).hexdigest();db=control(control_path)
    try:
        row=db.execute('SELECT call_json FROM calls WHERE request_id=?',(e.get('request_id'),)).fetchone()
        if not row:raise ValueError('Evidence request ID is not in the actual ledger.')
        call=json.loads(row[0])
        if call.get('reconciliation'):
            if call['reconciliation']['evidence_sha256']!=digest:raise ValueError('This request was already settled with different evidence.')
            return {'state':'already_reconciled','request_id':call['request_id'],'actual_charge_usd':call['calculated_api_usd'],'new_model_calls':0}
        if call.get('provider')!='typesafe' or call.get('outcome')!='failed' or call.get('calculated_api_usd') is not None:
            raise ValueError('Only an actual failed TypeSafe call with unknown billing can be settled here.')
        preview={'state':'evidence_validated' if not apply else 'reconciled','request_id':call['request_id'],
                 'actual_charge_usd':str(amount),'evidence_sha256':digest,'source':e['source'],'applied':apply,
                 'input_tokens':e.get('input_tokens'),'output_tokens':e.get('output_tokens'),'new_model_calls':0,
                 'note':'No classifier result recovered or inferred. Original failed outcome and handoff are retained.'}
        if not apply:return preview
        db.execute('BEGIN IMMEDIATE')
        current=db.execute('SELECT call_json FROM calls WHERE request_id=?',(e['request_id'],)).fetchone()
        if current is None or current[0]!=row[0]:raise ValueError('Call changed during settlement; inspect its current evidence before retrying.')
        if db.execute('SELECT 1 FROM run_locks LIMIT 1').fetchone():raise ValueError('Do not settle usage during an active classification run.')
        budget=dict(db.execute('SELECT * FROM budget').fetchone())
        if budget['unknown_charges']<1 or budget['reserved']+1e-12<call['reservation_usd']:
            raise ValueError('Ledger reservation/unknown counts do not support this settlement.')
        # Keep the failed request, original missing usage and provider evidence independently visible.
        call['original_unknown_usage']={k:call.get(k) for k in ('input_tokens','output_tokens','calculated_api_usd','usage_status','billing_status','failure_reason')}
        call.update(input_tokens=e.get('input_tokens'),output_tokens=e.get('output_tokens'),calculated_api_usd=float(amount),
                    billing_status='reconciled_from_provider_evidence',usage_status='provider_evidence_tokens' if e.get('input_tokens') is not None else 'tokens_unavailable_charge_reconciled',
                    reconciliation={'evidence_sha256':digest,'evidence':e})
        db.execute('UPDATE calls SET call_json=? WHERE request_id=?',(course.canonical(call),call['request_id']))
        hold=db.execute('SELECT held_usd FROM unknown_charge_holds WHERE request_id=? AND active=1',(call['request_id'],)).fetchone()
        release=hold[0] if hold else call['reservation_usd']
        db.execute('UPDATE unknown_charge_holds SET active=0 WHERE request_id=?',(call['request_id'],))
        db.execute('UPDATE budget SET reserved=MAX(0,reserved-?),spent=spent+?,unknown_charges=unknown_charges-1 WHERE singleton=1',(release,float(amount)))
        db.commit()
        # Even a unexpectedly large actual charge must be recorded truthfully; the cap blocks future dispatch.
        preview['project_api_cap_exhausted']=budget['spent']+float(amount)>=4.8
        if outdir:atomic_json(Path(outdir)/(call['request_id']+'_reconciliation.json'),preview)
        return preview
    except BaseException:
        db.rollback();raise
    finally:db.close()
