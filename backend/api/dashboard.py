"""Read-only deployed endpoint. Page visits never trigger inference."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

def dashboard():
    base=os.environ.get('SUPABASE_URL','').rstrip('/')
    public_key=os.environ.get('SUPABASE_PUBLISHABLE_KEY','')
    dataset=os.environ.get('SPOTIFY_DATASET_ID','')
    if not base.startswith('https://') or not public_key or not dataset.isdigit():
        raise ValueError('Database deployment is not configured.')
    query=urllib.parse.urlencode({'dataset_id':'eq.'+dataset,'artifact_kind':'eq.dashboard','select':'value','limit':'1'})
    headers={'apikey':public_key}
    if public_key.startswith('eyJ'):headers['Authorization']='Bearer '+public_key
    req=urllib.request.Request(base+'/rest/v1/analysis_outputs?'+query,headers=headers)
    with urllib.request.urlopen(req,timeout=15) as response:rows=json.load(response)
    if len(rows)!=1:raise ValueError('Published dashboard data is unavailable.')
    return rows[0]['value']

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:data=dashboard();code=200
        except (ValueError,urllib.error.URLError,OSError):data={'error':'Saved database results are not yet available.'};code=503
        raw=json.dumps(data,allow_nan=False).encode()
        self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','public,max-age=60' if code==200 else 'no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
