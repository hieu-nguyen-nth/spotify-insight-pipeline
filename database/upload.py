"""Offline export by default; explicit resumable client-side COPY to a Free database."""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spotify_pipeline.core import atomic_json,course,valid_record
from spotify_pipeline.artifact_review import saved_full_review

class UploadError(ValueError):
    """A deliberately safe user-facing validation message, never a driver exception."""

COLUMNS=('dataset_id','review_id','source_sha256','text_id','review_rating','review_likes','app_version',
 'review_timestamp','status','reason','topic','intent','severity','sentiment','needs_review','entities',
 'quote_start','quote_length','label_config_id','cache_source_id','model_request_ids','severity_provenance')

def prepare(scope,out):
    db=sqlite3.connect('file:'+str(ROOT/'work/control.sqlite')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    artifact=db.execute("SELECT artifact_json FROM stored_analysis WHERE scope=? AND artifact_kind='dashboard'",(scope,)).fetchone()
    if not artifact:raise UploadError('First save a checked complete analysis scope.')
    dashboard=json.loads(artifact[0]);cfg=dashboard['dataset']['label_config'];full=dashboard['dataset']['is_full_corpus']
    if dashboard['dataset'].get('scope_mode')=='user_stopped_subset':
        from spotify_pipeline.subset import saved_review
        reviewed=saved_review(db,ROOT)
        if dashboard.get('verification',{}).get('issue_counts')!=reviewed['instructor_checker_issue_counts']:
            raise UploadError('Subset dashboard checker disclosure is stale; save analysis again.')
    if full:
        verification=saved_full_review(db,ROOT)
        if dashboard.get('verification')!=verification:raise UploadError('Full dashboard must disclose the current unchanged checker result; save analysis again.')
    db.execute('ATTACH DATABASE ? AS source',(str(ROOT/'work/full.sqlite'),))
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.export-',dir=out)
    count=0;aliases=0;empty=0;digest=hashlib.sha256()
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            query="""SELECT s.*,p.part_json FROM source.source_reviews s JOIN lean_parts p
              ON p.review_id=s.review_id AND p.source_sha256=s.source_sha256 AND p.text_sha256=s.text_sha256
              AND p.review_text=s.review_text WHERE p.scope=? AND p.label_config=?
              AND json_type(p.part_json,'$.record')='object'
              ORDER BY json_extract(p.part_json,'$.record.cache_source_id') IS NOT NULL,s.review_id"""
            for source in db.execute(query,(scope,cfg)):
                source=dict(source);record=json.loads(source.pop('part_json'))['record'];valid_record(record,source)
                if course.row_sha(source)!=source['source_sha256']:raise UploadError('Original metadata/hash mismatch.')
                if record.get('text_sha256')!=hashlib.sha256(source['review_text'].encode()).hexdigest():raise UploadError('Text hash mismatch.')
                if str(uuid.UUID(record['review_id']))!=record['review_id']:raise UploadError('Noncanonical original ID.')
                if record['evidence_quote']!=source['review_text']:raise UploadError('Current export requires the preserved whole-source quote.')
                row={'source':{k:source[k] for k in course.FIELDS},'record':record}
                raw=course.canonical(row)+'\n';f.write(raw);digest.update(raw.encode());count+=1;aliases+=bool(record.get('cache_source_id'))
            if full:
                for source in db.execute("SELECT * FROM source.source_reviews WHERE source_status='quarantined' ORDER BY review_id"):
                    source=dict(source);record={k:source[k] for k in ('review_id','source_sha256','text_sha256','reason')};record['status']='quarantined'
                    raw=course.canonical({'source':{k:source[k] for k in course.FIELDS},'record':record})+'\n';f.write(raw);digest.update(raw.encode());empty+=1
            f.flush();os.fsync(f.fileno())
        if count!=dashboard['overview']['completed'] or empty!=dashboard['overview']['quarantined_in_analysis']:raise UploadError('Export coverage differs from checked dashboard.')
        os.replace(tmp,out/'rows.jsonl')
        artifacts=[dict(r) for r in db.execute('SELECT artifact_kind,sha256,artifact_json FROM stored_analysis WHERE scope=? ORDER BY artifact_kind',(scope,))]
        membership=[dict(r) for r in db.execute('SELECT issue_id,review_id FROM stored_membership WHERE scope=? ORDER BY review_id',(scope,))]
        config=json.loads((ROOT/('reports/full_run' if full else 'reports/'+scope)/'configuration.json').read_text())
        manifest={'scope':scope,'is_full_corpus':full,'source_sha256':dashboard['dataset']['source_sha256'],
          'source_rows':count+empty,'completed_rows':count,'empty_rows':empty,'aliases':aliases,'rows_sha256':digest.hexdigest(),
          'label_config':cfg,'configuration':config,'artifacts':artifacts,'membership':membership}
        atomic_json(out/'manifest.json',manifest)
        return {k:manifest[k] for k in ('scope','source_rows','completed_rows','empty_rows','aliases','rows_sha256')}
    finally:
        db.close()
        if os.path.exists(tmp):os.unlink(tmp)

def load_env():
    for line in (ROOT/'.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1);os.environ.setdefault(key.strip(),value.strip().strip('"\''))
    uri=os.environ.get('SUPABASE_DB_URL','')
    if not uri or 'YOUR-PASSWORD' in uri or '[YOUR-PASSWORD]' in uri:raise UploadError('Add the Session pooler URI to ignored .env as SUPABASE_DB_URL; keep it out of chat.')
    return uri

def upload(out,publish=False,max_database_bytes=450*1024**2):
    import psycopg
    from psycopg.types.json import Jsonb
    from decimal import Decimal
    out=Path(out);m=json.loads((out/'manifest.json').read_text())
    if course.sha(out/'rows.jsonl')!=m['rows_sha256']:raise UploadError('Export fingerprint changed.')
    started=time.perf_counter()
    # Connection errors are suppressed at the CLI boundary to avoid leaking credentials.
    with psycopg.connect(load_env(),sslmode='require',connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_database_size(current_database())');initial_bytes=cur.fetchone()[0]
            if initial_bytes>=max_database_bytes:raise UploadError('Database safety allowance reached; no paid upgrade authorized.')
            cur.execute('INSERT INTO public.pipeline_datasets(name,source_sha256,source_rows) VALUES(%s,%s,%s) ON CONFLICT(name) DO NOTHING',(m['scope'],m['source_sha256'],m['source_rows']))
            cur.execute('SELECT id,source_sha256,source_rows FROM public.pipeline_datasets WHERE name=%s',(m['scope'],));dataset,sha,n=cur.fetchone()
            if (sha,n)!=(m['source_sha256'],m['source_rows']):raise UploadError('Existing dataset provenance differs.')
            cur.execute('INSERT INTO public.label_configs(label_config,configuration) VALUES(%s,%s) ON CONFLICT(label_config) DO NOTHING',(m['label_config'],Jsonb(m['configuration'])))
            cur.execute('SELECT id,configuration FROM public.label_configs WHERE label_config=%s',(m['label_config'],));config,cfg=cur.fetchone()
            if cfg!=m['configuration']:raise UploadError('Frozen configuration differs.')
            cur.execute('CREATE TEMP TABLE import_rows (LIKE public.processed_reviews INCLUDING DEFAULTS) ON COMMIT PRESERVE ROWS')
            cur.execute('ALTER TABLE import_rows ADD review_text text, ADD text_sha256 bytea')
        conn.commit()
        imported=0
        def batch_insert(rows):
            nonlocal imported
            with conn.cursor() as cur:
                cur.execute('TRUNCATE import_rows')
                with cur.copy('COPY import_rows ('+','.join(COLUMNS)+',review_text,text_sha256) FROM STDIN') as copy:
                    for row in rows:
                        s,r=row['source'],row['record'];complete=r['status']=='completed'
                        vals=[dataset,uuid.UUID(r['review_id']),bytes.fromhex(r['source_sha256']),-1,s['review_rating'],s['review_likes'],s['app_version'],s['review_timestamp'],r['status'],r.get('reason'),r.get('topic'),r.get('intent'),r.get('severity'),Decimal(str(r['sentiment'])) if complete else None,r.get('needs_review'),Jsonb(r['entities']) if complete else None,0 if complete else None,len(s['review_text']) if complete else None,config if complete else None,uuid.UUID(r['cache_source_id']) if r.get('cache_source_id') else None,[uuid.UUID(i) for i in r.get('model_request_ids',[])],r.get('severity_provenance'),s['review_text'],bytes.fromhex(r['text_sha256'])]
                        copy.write_row(vals)
                cur.execute('INSERT INTO public.review_texts(text_sha256,review_text) SELECT DISTINCT text_sha256,review_text FROM import_rows ON CONFLICT(text_sha256) DO NOTHING')
                cur.execute('SELECT count(*) FROM import_rows i JOIN public.review_texts t USING(text_sha256) WHERE i.review_text IS DISTINCT FROM t.review_text')
                if cur.fetchone()[0]:raise UploadError('Database text/hash collision.')
                cur.execute('UPDATE import_rows i SET text_id=t.id FROM public.review_texts t WHERE t.text_sha256=i.text_sha256')
                cur.execute('INSERT INTO public.processed_reviews('+','.join(COLUMNS)+') SELECT '+','.join(COLUMNS)+' FROM import_rows ON CONFLICT(dataset_id,review_id) DO NOTHING')
                equal=' AND '.join('r.'+c+' IS NOT DISTINCT FROM i.'+c for c in COLUMNS)
                cur.execute('SELECT count(*) FROM import_rows i JOIN public.processed_reviews r USING(dataset_id,review_id) WHERE NOT ('+equal+')')
                if cur.fetchone()[0]:raise UploadError('Previously imported row differs; refuse overwrite.')
                cur.execute('SELECT pg_database_size(current_database())');size=cur.fetchone()[0]
                if size>max_database_bytes:raise UploadError('Database safety allowance exceeded; this batch is rolled back.')
            conn.commit();imported+=len(rows)
            atomic_json(out/'upload_progress.json',{'dataset_id':dataset,'checked_rows':imported,'database_bytes':size,'state':'uploading','published':False})
        with (out/'rows.jsonl').open() as f:
            rows=[]
            for line in f:
                rows.append(json.loads(line))
                if len(rows)==2000:batch_insert(rows);rows=[]
            if rows:batch_insert(rows)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FILTER(WHERE status='completed'),count(*) FILTER(WHERE status='quarantined') FROM public.processed_reviews WHERE dataset_id=%s",(dataset,));counts=cur.fetchone()
            if counts!=(m['completed_rows'],m['empty_rows']):raise UploadError('Database coverage differs from export.')
            for a in m['artifacts']:
                cur.execute('INSERT INTO public.analysis_outputs VALUES(%s,%s,%s,%s) ON CONFLICT(dataset_id,artifact_kind) DO UPDATE SET artifact_sha256=EXCLUDED.artifact_sha256,value=EXCLUDED.value',(dataset,a['artifact_kind'],a['sha256'],Jsonb(json.loads(a['artifact_json']))))
            cur.execute('CREATE TEMP TABLE import_membership (LIKE public.issue_membership) ON COMMIT DROP')
            with cur.copy('COPY import_membership(dataset_id,issue_id,review_id) FROM STDIN') as copy:
                for r in m['membership']:copy.write_row((dataset,r['issue_id'],uuid.UUID(r['review_id'])))
            cur.execute('INSERT INTO public.issue_membership SELECT * FROM import_membership ON CONFLICT DO NOTHING')
            cur.execute('SELECT count(*) FROM public.issue_membership WHERE dataset_id=%s',(dataset,))
            if cur.fetchone()[0]!=len(m['membership']):raise UploadError('Database membership differs from checked export.')
            if publish:
                cur.execute("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relname IN ('processed_reviews','review_texts','label_configs','issue_membership') AND has_table_privilege('anon',oid,'select')")
                if cur.fetchone()[0]:raise UploadError('Raw-table public access is enabled; apply keep_raw_reviews_private.sql before publishing dashboard artifacts.')
            cur.execute('UPDATE public.pipeline_datasets SET completed_rows=%s,empty_rows=%s,published=%s WHERE id=%s',(*counts,publish,dataset))
            cur.execute('SELECT pg_database_size(current_database())');size=cur.fetchone()[0]
            cur.execute("SELECT sum(pg_total_relation_size(oid)) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r'");tables=int(cur.fetchone()[0])
        conn.commit()
        result={'state':'completed','dataset_id':dataset,'scope':m['scope'],'completed_rows':counts[0],'quarantined_rows':counts[1],
          'source_rows':sum(counts),'membership_rows':len(m['membership']),'stored_artifacts':len(m['artifacts']),
          'initial_database_bytes':initial_bytes,'database_bytes':size,'public_table_bytes':tables,'published':publish,
          'wall_seconds':time.perf_counter()-started,'new_model_calls':0,'verification':'Every imported column compared to client staging; coverage and membership counts matched.'}
        atomic_json(out/'upload_result.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--scope',default='checkpoint10000');p.add_argument('--out',type=Path);p.add_argument('--execute-upload',action='store_true');p.add_argument('--publish',action='store_true');a=p.parse_args()
    out=a.out or ROOT/'work/database_exports'/a.scope
    if a.publish and not a.execute_upload:p.error('--publish requires --execute-upload')
    try:
        result=prepare(a.scope,out)
        if a.execute_upload:result=upload(out,a.publish)
        print(json.dumps(result,indent=2))
    except Exception as error:
        # No driver exception text: it can contain a connection URI or password.
        print(json.dumps({'state':'failed','error_type':type(error).__name__,'reason':str(error) if isinstance(error,UploadError) else 'Database operation failed; credentials omitted.'}));return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
