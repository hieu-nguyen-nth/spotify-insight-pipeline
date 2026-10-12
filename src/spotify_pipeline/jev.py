"""Explicit bounded Jev calls. No calls at import time; no credential logging."""
import json
import os
import random
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .core import ROOT, atomic_json, configuration, connect, course, export_progress, mapped_response, meta, request_body, reuse_cached, save_result, snapshot

RATE_PER_TOKEN = 0.042 / 1_000_000


def load_key(env_path):
    key = os.environ.get("TYPESAFE_API_KEY","").strip()
    if not key and Path(env_path).exists():
        for line in Path(env_path).read_text().splitlines():
            line = line.strip()
            if line.startswith("TYPESAFE_API_KEY="):
                key = line.partition("=")[2].strip().strip('"').strip("'")
    if not key:
        raise ValueError("TYPESAFE_API_KEY is empty. Fill the ignored local .env file; never paste the key into chat.")
    return key


def reserve(db, request_id, run_id, source, body, label_config, phase, cap, review_ids=None):
    # Conservative byte-based estimate plus provider-overhead allowance. Not actual billed usage.
    estimate_tokens = len(json.dumps(body,ensure_ascii=False).encode("utf-8")) + 4096
    reservation = estimate_tokens * RATE_PER_TOKEN
    db.execute("BEGIN IMMEDIATE")
    ledger = db.execute("SELECT * FROM budget").fetchone()
    if ledger["spent"] + ledger["reserved"] + reservation > cap:
        db.rollback()
        return None
    ids = review_ids if review_ids is not None else [source["review_id"]]
    if not 1 <= len(ids) <= 50 or len(set(ids)) != len(ids):
        db.rollback()
        raise ValueError("Requests require 1 to 50 distinct review IDs.")
    call = {"request_id":request_id,"run_id":run_id,"role":"enrich","review_ids":ids,
            "model":body["model"],"phase":phase,"outcome":"in_flight","label_config":label_config,
            "provider":"typesafe","effort":"not_applicable","batch_size":len(ids),"workers":1,
            "reservation_usd":reservation,"input_tokens":None,"output_tokens":None,
            "usage_status":"unavailable","started_at_unix":time.time()}
    db.execute("UPDATE budget SET reserved=reserved+? WHERE singleton=1",(reservation,))
    db.execute("INSERT INTO calls VALUES(?,?,?,?,?)",(request_id,run_id,"enrich","in_flight",course.canonical(call)))
    db.commit()
    return call


def settle(db, call, response=None, failure=None, elapsed=0, status_code=None, record=None):
    usage = response.get("usage",{}) if isinstance(response,dict) else {}
    if not isinstance(usage,dict):
        usage = {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    known = type(input_tokens) is int and input_tokens>=0 and type(output_tokens) is int and output_tokens>=0
    actual = input_tokens*RATE_PER_TOKEN if known else None
    call.update(outcome="failed" if failure else "succeeded", elapsed_seconds=elapsed,
                finished_at_unix=time.time(),input_tokens=input_tokens if known else None,
                output_tokens=output_tokens if known else None,usage_status="provider_reported" if known else "unavailable",
                calculated_api_usd=actual, billing_status="calculated_from_usage" if known else "unknown",
                failure_reason=failure,http_status=status_code)
    db.execute("BEGIN IMMEDIATE")
    if known:
        db.execute("UPDATE budget SET reserved=MAX(0,reserved-?),spent=spent+? WHERE singleton=1",(call["reservation_usd"],actual))
    else:
        # Preserve the reservation: unknown failures/usage must not turn into free calls.
        db.execute("UPDATE budget SET unknown_charges=unknown_charges+1 WHERE singleton=1")
    db.execute("UPDATE calls SET outcome=?,call_json=? WHERE request_id=?",(call["outcome"],course.canonical(call),call["request_id"]))
    if record is not None:
        save_result(db,record)
    db.commit()
    return known


def http_call(body, key):
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone",
          data=json.dumps(body,ensure_ascii=False).encode(),
          headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            return course.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Retry only when the provider actually reports both usage fields.
        # A status code by itself never establishes that an attempt was free.
        if exc.code not in (429,500,502,503,504):raise
        try:reported=course.loads(exc.read().decode('utf-8'))
        except (ValueError,UnicodeError):raise exc
        usage=reported.get('usage',{}) if isinstance(reported,dict) else {}
        if not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('input_tokens','output_tokens')):raise exc
        return {'usage':usage,'transport_failure':{'http_status':exc.code,'transient':True},'provider_error_response':reported}


def enrich(db_path, outdir, env_path, limit=1, cap=0.25, config_path=None, transport=None):
    if limit<1 or cap<=0 or cap>8.5:
        raise ValueError("Choose a positive limit and an API budget no greater than $8.50.")
    config,label_config = configuration(config_path)
    key = load_key(env_path)
    db = connect(db_path)
    if not meta(db,"ingestion_complete"):
        raise ValueError("Run ingestion first.")
    if db.execute("SELECT COUNT(*) FROM calls WHERE outcome='in_flight'").fetchone()[0]:
        raise ValueError("Unresolved in-flight call: reconcile its outcome before dispatching new work.")
    if db.execute("SELECT unknown_charges FROM budget").fetchone()[0]:
        raise ValueError("Unknown charges/usage remain. Reconcile them before further paid dispatch.")
    outdir = Path(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    before = snapshot(db,label_config)
    phase = "resume" if before["completed_ids"] else "initial"
    atomic_json(outdir/"checkpoint_before.json",before)
    atomic_json(outdir/"runs"/run_id/"checkpoint_before.json",before)
    attempts = completed = cache_hits = examined = 0
    stop = "limit_reached"
    try:
        sources = db.execute("SELECT * FROM source_reviews WHERE source_status='pending' ORDER BY source_order")
        for source in sources:
            if examined>=limit:
                break
            examined += 1
            cached = reuse_cached(db,source,label_config)
            if cached:
                cache_hits += 1
                db.commit()
                continue
            failed = db.execute("SELECT record_json FROM results WHERE review_id=? AND label_config=?",(source["review_id"],label_config)).fetchone()
            if failed:
                # Quarantines are explicit, not an infinite retry queue.
                continue
            body = request_body(source["review_text"],config)
            record = None
            failure = None
            for attempt in range(2):
                request_id = str(uuid.uuid4())
                call = reserve(db,request_id,run_id,source,body,label_config,phase,cap)
                if call is None:
                    stop = "budget_stop"
                    break
                attempts += 1
                atomic_json(outdir/"handoffs"/(request_id+"_input.json"),{"request_id":request_id,"review_id":source["review_id"],"role":"enrich","label_config":label_config,"body":body})
                response = None
                tick = time.perf_counter()
                try:
                    response = (transport or http_call)(body,key)
                    record = mapped_response(response,source,config,label_config)
                    failure = None
                except urllib.error.HTTPError as exc:
                    # Never save response bodies or request headers: they can expose credentials.
                    failure = "http_"+str(exc.code)
                    known = settle(db,call,failure=failure,elapsed=time.perf_counter()-tick,status_code=exc.code)
                    stop = "unknown_charge_stop"
                    break
                except (urllib.error.URLError,TimeoutError,OSError):
                    failure = "network_outcome_unknown"
                    settle(db,call,failure=failure,elapsed=time.perf_counter()-tick)
                    stop = "unknown_charge_stop"
                    break
                except (ValueError,KeyError,TypeError):
                    failure = "invalid_response"
                except KeyboardInterrupt:
                    settle(db,call,failure="interrupted_outcome_unknown",elapsed=time.perf_counter()-tick)
                    stop = "interrupted"
                    raise
                if response is not None:
                    atomic_json(outdir/"handoffs"/(request_id+"_output.json"),response)
                known = settle(db,call,response=response,failure=failure,elapsed=time.perf_counter()-tick,record=record)
                if record:
                    completed += 1
                    if not known:
                        stop = "unknown_charge_stop"
                    break
                if not known:
                    stop = "unknown_charge_stop"
                    break
                if attempt==0:
                    time.sleep(0.1+random.random()*0.1)
            if not record and failure:
                save_result(db,{"review_id":source["review_id"],"source_sha256":source["source_sha256"],"status":"quarantined","reason":failure,"label_config":label_config})
                db.commit()
            export_progress(db_path,outdir,label_config)
            if stop in ("budget_stop","unknown_charge_stop"):
                break
    except KeyboardInterrupt:
        stop = "interrupted"
    finally:
        after = snapshot(db,label_config)
        atomic_json(outdir/"checkpoint_after.json",after)
        atomic_json(outdir/"runs"/run_id/"checkpoint_after.json",after)
        summary = {"run_id":run_id,"phase":phase,"scope":"enrichment_only_not_complete_pilot",
                   "new_completed":completed,"cache_hits":cache_hits,"attempts":attempts,
                   "input_window_nonempty_rows":limit,"examined_rows":examined,
                   "stop_reason":stop,"wall_seconds":time.perf_counter()-started,"api_budget_usd":cap,
                   "label_config":label_config,"workers":1,"batch_size":1,
                   "downstream_stages":"not_implemented_yet"}
        atomic_json(outdir/"run_summary.json",summary)
        atomic_json(outdir/"runs"/(run_id+".json"),summary)
        export_progress(db_path,outdir,label_config)
        db.close()
    return summary
