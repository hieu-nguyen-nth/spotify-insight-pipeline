"""Local-only dashboard preview from actually persisted SQLite analysis."""
import argparse
import json
import os
import importlib.util
import sqlite3
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--scope',default='checkpoint10000');p.add_argument('--port',type=int,default=8787);p.add_argument('--cloud-database',action='store_true');args=p.parse_args()
    if args.cloud_database:
        os.environ.update(json.loads((HERE.parent/'work/backend_env.json').read_text()))
        spec=importlib.util.spec_from_file_location('cloud_dashboard',HERE/'api/dashboard.py');cloud=importlib.util.module_from_spec(spec);spec.loader.exec_module(cloud)
    database=HERE.parent/'work/control.sqlite'
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.split('?')[0]=='/api/dashboard':
                if args.cloud_database:
                    try:raw=json.dumps(cloud.dashboard()).encode();code=200
                    except Exception:raw=json.dumps({'error':'Cloud saved results are unavailable.'}).encode();code=503
                    self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
                db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
                try:row=db.execute("SELECT artifact_json FROM stored_analysis WHERE scope=? AND artifact_kind='dashboard'",(args.scope,)).fetchone()
                finally:db.close()
                raw=(row[0] if row else json.dumps({'error':'Saved analysis is not available.'})).encode()
                self.send_response(200 if row else 503);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
            else:super().do_GET()
        def log_message(self,format,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(HERE/'public')))
    print(f'Local saved-data preview: http://127.0.0.1:{args.port} · '+('Supabase database' if args.cloud_database else 'scope '+args.scope),flush=True)
    server.serve_forever()

if __name__=='__main__':main()
