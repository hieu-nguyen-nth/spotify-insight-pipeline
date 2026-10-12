import json,tempfile,unittest
from pathlib import Path
from spotify_pipeline import lean,budget_policy

def response(body):
    answers={}
    for k,q in body['questions'].items():
        pick=next(iter(q['criteria']));answers[k]={'type':'choice','choice':pick,'confidence':1,'probabilities':{x:float(x==pick) for x in q['criteria']}}
    return {'model':lean.MODEL,'answers':answers,'usage':{'input_tokens':100,'output_tokens':0}}

class DispatchControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=lean.control(self.root/'state.sqlite')
        self.sources=[{'review_id':'fixture','review_text':'Cannot log in.'}]
        self.cfg,self.label=lean.settings(50,'v3');self.body=lean.body_for(self.sources,self.cfg,'verify',True)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def call(self,transport,**kwargs):
        return lean.dispatch_retry(self.db,self.body,self.sources,'fixture-run',self.label,'initial','verify',.01,self.root,transport=transport,**kwargs)
    def test_invalid_output_retries_once_and_accounts_both_attempts(self):
        calls=[];delays=[]
        def transport(body,key):
            calls.append(body);r=response(body)
            if len(calls)==1:r['answers']={}
            return r
        self.call(transport,sleep=delays.append,jitter=lambda:0)
        self.assertEqual(len(calls),2);self.assertEqual(delays,[.25]);self.assertAlmostEqual(self.db.execute('SELECT spent FROM budget').fetchone()[0],200*lean.RATE_PER_TOKEN)
        self.assertEqual([r[0] for r in self.db.execute('SELECT outcome FROM calls ORDER BY rowid')],['failed','succeeded'])
    def test_known_transient_backoff_and_jitter_then_success(self):
        calls=[];delays=[]
        def transport(body,key):
            calls.append(body)
            if len(calls)==1:return {'usage':{'input_tokens':0,'output_tokens':0},'transport_failure':{'http_status':503,'transient':True},'provider_error_response':{'fixture':True}}
            return response(body)
        self.call(transport,sleep=delays.append,jitter=lambda:1)
        self.assertEqual(len(calls),2);self.assertEqual(delays,[.5]);self.assertEqual(self.db.execute('SELECT unknown_charges FROM budget').fetchone()[0],0)
    def test_retry_exhaustion_and_unknown_usage_never_retried(self):
        count=[]
        def unknown(body,key):count.append(1);return {'answers':{}}
        with self.assertRaises(lean.DispatchFailure):self.call(unknown,sleep=lambda d:None)
        self.assertEqual(len(count),1);self.assertEqual(self.db.execute('SELECT unknown_charges FROM budget').fetchone()[0],1)
    def test_second_invalid_output_stops_without_third_attempt(self):
        count=[]
        def invalid(body,key):count.append(1);r=response(body);r['answers']={};return r
        with self.assertRaises(lean.DispatchFailure):self.call(invalid,sleep=lambda d:None)
        self.assertEqual(len(count),2)
    def test_owned_workers_share_reservations_other_runs_still_block(self):
        self.db.execute('INSERT INTO run_locks VALUES(?,?)',('fixture','owned'))
        c={'reservation_usd':.001};self.db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('x','owned','verify','in_flight',json.dumps(c)))
        self.db.execute('UPDATE budget SET reserved=.001');self.db.commit()
        self.assertIsNone(budget_policy.dispatch_block_reason(self.db,'verify','owned',2))
        self.assertIsNotNone(budget_policy.dispatch_block_reason(self.db,'verify','other',2))
        self.assertIsNotNone(budget_policy.dispatch_block_reason(self.db,'verify'))
        self.db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('y','owned','verify','in_flight',json.dumps(c)));self.db.execute('UPDATE budget SET reserved=.002')
        self.assertIsNotNone(budget_policy.dispatch_block_reason(self.db,'verify','owned',2))
    def test_parallel_reservation_cannot_admit_a_second_overcap_request(self):
        self.db.execute('INSERT INTO run_locks VALUES(?,?)',('fixture','owned'))
        estimate=len(lean.course.canonical(self.body).encode())+4096
        reserved=estimate*lean.RATE_PER_TOKEN
        self.db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('x','owned','verify','in_flight',json.dumps({'reservation_usd':reserved})))
        self.db.execute('UPDATE budget SET reserved=?',(reserved,));self.db.commit()
        calls=[]
        with self.assertRaisesRegex(ValueError,'spend reservation'):
            lean.dispatch(self.db,self.body,self.sources,'owned',self.label,'initial','verify',reserved*1.5,self.root,
              transport=lambda b,k:calls.append(b),worker_limit=2,concurrent_run_id='owned')
        self.assertEqual(calls,[]);self.assertEqual(self.db.execute('SELECT count(*) FROM calls').fetchone()[0],1)
