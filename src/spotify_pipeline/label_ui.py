"""Loopback-only human annotation screen. Never fills or sends model answers."""
import csv
import io
import json
import os
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .core import ROOT, TOPICS, INTENTS, atomic_json

PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Spotify — human labels</title>
<style>body{font:16px system-ui;background:#101a18;color:#edf4ef;margin:0}main{max-width:920px;margin:auto;padding:28px}h1{font-size:25px}article,aside{background:#1b2b26;padding:22px;border-radius:12px;margin:18px 0}#review{white-space:pre-wrap;line-height:1.6}label{display:block;margin:14px 0}select,input,textarea,button{font:inherit;padding:10px;border-radius:7px;border:1px solid #659783}input,select,textarea{background:#fff;color:#16241e;max-width:100%;box-sizing:border-box}textarea{width:100%;height:85px}button{cursor:pointer;background:#b5efcf;color:#11231a;margin-right:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}small{color:#a9c6b6}#notice{color:#c7eaa7}</style>
<main><h1>Golden 50 · your independent labels</h1><p>Read each review and choose your own answers. No model suggestions appear here. Progress saves to your local CSV.</p><aside><strong>Label guide</strong><p>Intent: cancellation → complaint → request → praise → unclear. Choose the most serious specific topic; tie: first mentioned. General praise is “other”. Premium-only restrictions are “billing”.</p><p>Severity: 1 = no problem / pure request; 2 = annoyance; 3 = impaired but usable; 4 = core task blocked; 5 = explicit serious financial, privacy or data harm. Anger and cancellation alone do not increase severity. Sentiment ranges from −1 to +1.</p></aside><p id="progress"></p><article><small id="id"></small><p id="review"></p></article><form id="form"><div class="grid"><label>Topic<select id="topic" required></select></label><label>Intent<select id="intent" required></select></label><label>Severity<select id="severity" required><option value="">Choose…</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label><label>Sentiment<input id="sentiment" type="number" min="-1" max="1" step="0.01" required placeholder="−1 to +1"></label></div><label>Entities (JSON list of feature names; [] if none)<input id="entities" required placeholder='["shuffle"]'></label><label>Evidence quote (copy an exact passage from the review)<textarea id="evidence_quote" required></textarea></label><label>Needs review<select id="needs_review" required><option value="">Choose…</option><option value="false">No — clear interpretation</option><option value="true">Yes — uncertain interpretation</option></select></label><button type="button" id="prev">Previous</button><button>Save & next</button><button type="button" id="next">Next without saving</button></form><p id="notice" role="status"></p></main><script>
let rows=[],index=0,token='';const fields=['topic','intent','severity','sentiment','entities','evidence_quote','needs_review'];
const el=x=>document.getElementById(x);function draw(){let r=rows[index];el('progress').textContent=`Review ${index+1} / ${rows.length} · ${rows.filter(r=>fields.every(f=>r[f]!=='' )).length} saved`;el('id').textContent=r.review_id;el('review').textContent=r.review_text;fields.forEach(f=>el(f).value=r[f]);}
async function init(){let d=await(await fetch('/api/labels')).json();rows=d.rows;token=d.token;for(let [f,opts] of [['topic',d.topics],['intent',d.intents]]){el(f).append(new Option('Choose…',''));opts.forEach(v=>el(f).append(new Option(v,v)));}index=Math.max(0,rows.findIndex(r=>!r.topic));draw();}
el('prev').onclick=()=>{index=Math.max(0,index-1);draw()};el('next').onclick=()=>{index=Math.min(rows.length-1,index+1);draw()};el('form').onsubmit=async e=>{e.preventDefault();let data={review_id:rows[index].review_id};fields.forEach(f=>data[f]=el(f).value);let res=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json','X-Label-Token':token},body:JSON.stringify(data)});let d=await res.json();if(!res.ok){el('notice').textContent=d.error;return}Object.assign(rows[index],data);el('notice').textContent='Saved to the local human-label file.';index=Math.min(rows.length-1,index+1);draw()};init();</script></html>'''

def validate(values, source):
    if values.get('topic') not in TOPICS or values.get('intent') not in INTENTS:
        raise ValueError('Choose a valid topic and intent.')
    if values.get('severity') not in ('1','2','3','4','5'):
        raise ValueError('Choose severity 1–5.')
    sentiment = float(values.get('sentiment',''))
    if not -1 <= sentiment <= 1:
        raise ValueError('Sentiment must be between −1 and +1.')
    entities = json.loads(values.get('entities',''))
    if not isinstance(entities,list) or any(not isinstance(x,str) or not x.strip() for x in entities):
        raise ValueError('Entities must be a JSON list of nonempty names, or [].')
    quote = values.get('evidence_quote','')
    if not quote.strip() or quote not in source['review_text']:
        raise ValueError('The evidence quote must be copied exactly from this review.')
    if values.get('needs_review') not in ('true','false'):
        raise ValueError('Choose whether this review is uncertain.')
    return {k:values[k] for k in ('topic','intent','sentiment','severity','entities','evidence_quote','needs_review')}

def serve(path=ROOT/'labels/golden_50_human.csv', port=8765):
    path=Path(path).resolve(); token=secrets.token_urlsafe(32); lock=threading.Lock()
    def read():
        with path.open(newline='',encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def reply(self,code,data,html=False):
            raw=(data if html else json.dumps(data)).encode()
            self.send_response(code); self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if self.path=='/': return self.reply(200,PAGE,True)
            if self.path=='/api/labels': return self.reply(200,{'rows':read(),'topics':sorted(TOPICS),'intents':sorted(INTENTS),'token':token})
            self.reply(404,{'error':'Not found'})
        def do_POST(self):
            origin=self.headers.get('Origin')
            if self.path!='/api/labels' or self.headers.get('X-Label-Token')!=token or origin not in (None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                return self.reply(403,{'error':'This local screen must be used to save labels.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=20000: raise ValueError('Invalid request size.')
                values=json.loads(self.rfile.read(length))
                with lock:
                    rows=read(); source=next(r for r in rows if r['review_id']==values.get('review_id'))
                    source.update(validate(values,source))
                    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.labels-')
                    try:
                        with os.fdopen(fd,'w',newline='',encoding='utf-8') as f:
                            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);f.flush();os.fsync(f.fileno())
                        os.replace(tmp,path)
                    finally:
                        if os.path.exists(tmp):os.unlink(tmp)
                self.reply(200,{'saved':True})
            except (ValueError,TypeError,StopIteration,KeyError):self.reply(400,{'error':'Check the selected labels, entity list, sentiment and exact evidence quote.'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Human annotation screen: http://127.0.0.1:{port}',flush=True)
    server.serve_forever()
