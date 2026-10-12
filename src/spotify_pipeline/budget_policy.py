"""Explicit user-approved liability holds. Holds never become actual provider charges."""
import hashlib
import json
import math
from pathlib import Path
from .core import course, atomic_json

def dispatch_block_reason(db,role=None,concurrent_run_id=None,max_workers=1):
    if max_workers not in (1,2) or (max_workers!=1 and concurrent_run_id is None):
        raise ValueError('Concurrent admission requires an owned run and a limit of one or two workers.')
    if role is not None and db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='stopped_roles'").fetchone():
        stopped=db.execute('SELECT reason FROM stopped_roles WHERE role=?',(role,)).fetchone()
        if stopped:return 'User stopped this model role: '+stopped[0]
    active=list(db.execute("SELECT run_id,call_json FROM calls WHERE outcome='in_flight'"))
    if active:
        owned=(concurrent_run_id is not None and
          db.execute('SELECT 1 FROM run_locks WHERE run_id=?',(concurrent_run_id,)).fetchone() and
          all(row['run_id']==concurrent_run_id for row in active))
        if not owned:return 'A request is in flight; wait for its outcome before another dispatch.'
        if len(active)>=max_workers:return 'The owned run has reached its worker admission limit.'
    budget=dict(db.execute('SELECT * FROM budget').fetchone())
    holds=list(db.execute('SELECT * FROM unknown_charge_holds WHERE active=1'))
    if budget['unknown_charges']!=len(holds):
        return 'A new or unauthorized unknown charge needs review before paid dispatch.'
    held=0.0
    for hold in holds:
        row=db.execute('SELECT call_json FROM calls WHERE request_id=?',(hold['request_id'],)).fetchone()
        if not row:return 'Authorized liability hold has no corresponding failed request.'
        call=json.loads(row[0]);auth=json.loads(hold['authorization_json'])
        digest=hashlib.sha256(hold['authorization_json'].encode()).hexdigest()
        if (call.get('outcome')!='failed' or call.get('provider')!='typesafe' or call.get('calculated_api_usd') is not None
            or auth.get('request_id')!=hold['request_id'] or auth.get('project_cap_usd')!=4.8
            or not auth.get('explicit_user_authorization') or auth.get('held_usd')!=hold['held_usd']
            or digest!=hold['authorization_sha256'] or hold['held_usd']<call['reservation_usd']):
            return 'Liability hold validation failed; provider usage remains unknown.'
        held+=hold['held_usd']
    active_reserved=sum(json.loads(row['call_json'])['reservation_usd'] for row in active)
    if abs(budget['reserved']-held-active_reserved)>1e-9:
        return 'Outstanding reservations are not fully covered by explicit liability holds.'
    return None

def authorize_hold(authorization_path,apply=False,control_path=None,outdir=None):
    from .lean import control,CONTROL
    auth=json.loads(Path(authorization_path).read_text())
    held=auth.get('held_usd')
    if (auth.get('source')!='explicit_user_instruction' or auth.get('explicit_user_authorization') is not True
        or not auth.get('user_instruction') or not auth.get('observed_at_utc') or auth.get('project_cap_usd')!=4.8
        or type(held) not in (int,float) or not math.isfinite(held) or not .05<=held<=4.8):
        raise ValueError('Require explicit, dated user authorization for a hold within the unchanged $4.80 cap.')
    canonical=course.canonical(auth);digest=hashlib.sha256(canonical.encode()).hexdigest()
    db=control(control_path or CONTROL)
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM run_locks LIMIT 1').fetchone() or db.execute("SELECT 1 FROM calls WHERE outcome='in_flight' LIMIT 1").fetchone():
            raise ValueError('Do not change liability holds during an active or in-flight run.')
        existing=db.execute('SELECT * FROM unknown_charge_holds WHERE request_id=?',(auth.get('request_id'),)).fetchone()
        if existing:
            if existing['authorization_sha256']!=digest or not existing['active']:raise ValueError('This hold already has different authorization or was reconciled.')
            return {'state':'already_held','held_usd':held,'new_model_calls':0}
        row=db.execute('SELECT call_json FROM calls WHERE request_id=?',(auth.get('request_id'),)).fetchone()
        call=json.loads(row[0]) if row else {}
        if call.get('provider')!='typesafe' or call.get('outcome')!='failed' or call.get('calculated_api_usd') is not None:
            raise ValueError('A hold can cover only an actual failed TypeSafe request with unknown charge.')
        budget=dict(db.execute('SELECT * FROM budget').fetchone());old=call['reservation_usd']
        if held<old or budget['unknown_charges']<1 or budget['reserved']+1e-12<old:raise ValueError('Existing unknown reservation does not support this hold.')
        if budget['spent']+budget['reserved']-old+held>4.8:raise ValueError('Hold would exceed the unchanged cap.')
        report={'state':'hold_applied' if apply else 'hold_validated','request_id':auth['request_id'],'held_usd':held,
                'original_reservation_usd':old,'actual_charge_usd':None,'tokens':None,'cost_status':'provisional',
                'authorization_sha256':digest,'new_model_calls':0,'note':'Only this failed request is covered. Any new unknown charge stops dispatch.'}
        if apply:
            db.execute('INSERT INTO unknown_charge_holds VALUES(?,?,?,?,1)',(auth['request_id'],held,digest,canonical))
            db.execute('UPDATE budget SET reserved=reserved-?+? WHERE singleton=1',(old,held))
            db.commit()
            if outdir:atomic_json(Path(outdir)/'authorized_unknown_hold.json',report)
        return report
    except BaseException:db.rollback();raise
    finally:db.close()
