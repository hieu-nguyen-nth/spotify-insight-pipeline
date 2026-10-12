import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from spotify_pipeline import lean

def response(body):
    answers={}
    for key,q in body['questions'].items():
        options=list(q['criteria']);pick=options[0]
        answers[key]={'type':'choice','choice':pick,'confidence':1.,'probabilities':{v:float(v==pick) for v in options}}
    return {'model':lean.MODEL,'answers':answers,'usage':{'input_tokens':123,'output_tokens':9}}

class LeanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.db=lean.control(self.root/'control.sqlite')
        self.config,self.cfg=lean.settings()
        self.sources=[{'review_id':'original-id','review_text':'Cannot log in','source_sha256':'row-hash','text_sha256':'text-hash'}]
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def test_payload_excludes_metadata_and_answers(self):
        src=dict(self.sources[0],review_rating='5',topic='planted-answer',review_likes='900')
        body=lean.body_for([src],self.config,'topic_intent')
        self.assertEqual(body['state']['reviews'],{'r0':'Cannot log in'})
        self.assertNotIn('planted-answer',json.dumps(body));self.assertNotIn('review_rating',json.dumps(body))
        self.assertEqual(len(body['questions']),2)
    def test_bounded_review_count(self):
        with self.assertRaises(ValueError):lean.body_for(self.sources*51,self.config,'topic_intent')
    def test_long_reviews_split_without_dropping_or_duplicating_ids(self):
        sources=[dict(self.sources[0],review_id=str(i),review_text='Long text '*300) for i in range(50)]
        config,_=lean.settings(50);result=list(lean.batches(sources,config,'topic_intent'))
        self.assertGreater(len(result),1)
        self.assertEqual([s['review_id'] for batch,body in result for s in batch],[str(i) for i in range(50)])
    def test_atomic_usage_and_partial_answers(self):
        body=lean.body_for(self.sources,self.config,'topic_intent')
        def save(answer,rid):lean.put(self.db,'test',self.cfg,self.sources[0],{'topic':answer['r0_topic'],'request_ids':[rid]})
        _,call=lean.dispatch(self.db,body,self.sources,'run',self.cfg,'initial','enrich',.01,self.root,save,lambda b,k:response(b),'test')
        self.assertIsNotNone(lean.part(self.db,'test',self.cfg,'original-id'))
        self.assertAlmostEqual(self.db.execute('SELECT spent FROM budget').fetchone()[0],123*lean.RATE_PER_TOKEN)
        self.assertEqual(call['review_ids'],['original-id'])
    def test_unknown_usage_blocks_next_call(self):
        body=lean.body_for(self.sources,self.config,'topic_intent')
        def unknown(b,k):r=response(b);r.pop('usage');return r
        with self.assertRaises(ValueError):lean.dispatch(self.db,body,self.sources,'run',self.cfg,'initial','enrich',.01,self.root,transport=unknown)
        self.assertGreater(self.db.execute('SELECT reserved FROM budget').fetchone()[0],0)
        with self.assertRaises(ValueError):lean.dispatch(self.db,body,self.sources,'run',self.cfg,'resume','enrich',.01,self.root,transport=lambda b,k:self.fail('must not call'))
    def test_transport_diagnostics_do_not_leak_error_message_or_clear_unknown_usage(self):
        body=lean.body_for(self.sources,self.config,'topic_intent')
        def broken(b,k):raise urllib.error.URLError(TimeoutError('do-not-log-credential-value'))
        with self.assertRaises(ValueError):lean.dispatch(self.db,body,self.sources,'run',self.cfg,'initial','enrich',.01,self.root,transport=broken)
        raw=self.db.execute('SELECT call_json FROM calls').fetchone()[0];call=json.loads(raw)
        self.assertNotIn('do-not-log-credential-value',raw)
        self.assertEqual(call['transport_error']['exception_type'],'URLError')
        self.assertEqual(call['transport_error']['reason_type'],'TimeoutError')
        self.assertIsNone(call['calculated_api_usd']);self.assertEqual(self.db.execute('SELECT unknown_charges FROM budget').fetchone()[0],1)
    def test_probability_rounding_and_impossible_distribution(self):
        body=lean.body_for(self.sources,self.config,'topic_intent');r=response(body)
        values=r['answers']['r0_topic']['probabilities'];options=list(values)
        values.update({v:0 for v in values});values[options[0]]=.55;values[options[1]]=.27;values[options[2]]=.17
        lean.choices(r,body)
        values[options[0]]=.50
        with self.assertRaises(ValueError):lean.choices(r,body)
    def test_configuration_changes_invalidate_cache(self):
        self.assertNotEqual(lean.settings(20)[1],lean.settings(50)[1])
    def test_reservation_prevents_dispatch(self):
        body=lean.body_for(self.sources,self.config,'topic_intent')
        with self.assertRaises(ValueError):lean.dispatch(self.db,body,self.sources,'run',self.cfg,'initial','enrich',0.000001,self.root,transport=lambda b,k:self.fail('must not call'))
    def cached_record(self):
        s=self.sources[0]
        return {'review_id':s['review_id'],'source_sha256':s['source_sha256'],'label_config':self.cfg,'status':'completed',
                'topic':'access','intent':'complaint','severity':4,'sentiment':-.5,'entities':[],'evidence_quote':s['review_text'],
                'needs_review':False,'model_request_ids':['real-original-request']}
    def test_cross_scope_reuse_preserves_ids_and_request_provenance(self):
        record=self.cached_record();lean.put(self.db,'first',self.cfg,self.sources[0],{'record':record,'request_ids':['real-original-request']});self.db.commit()
        copied=lean.inherit_completed(self.db,self.sources,'first','second',self.cfg)
        self.assertEqual(len(copied),1)
        self.assertEqual(lean.part(self.db,'second',self.cfg,'original-id')['record'],record)
        self.assertEqual(lean.inherit_completed(self.db,self.sources,'first','second',self.cfg),[])
    def test_cross_scope_reuse_rejects_changed_source_config_and_aliases(self):
        record=self.cached_record();lean.put(self.db,'first',self.cfg,self.sources[0],{'record':record});self.db.commit()
        changed=[dict(self.sources[0],source_sha256='changed')]
        self.assertEqual(lean.inherit_completed(self.db,changed,'first','second',self.cfg),[])
        self.assertEqual(lean.inherit_completed(self.db,self.sources,'first','second','changed-config'),[])
        record['cache_source_id']='other-id';lean.put(self.db,'first',self.cfg,self.sources[0],{'record':record});self.db.commit()
        self.assertEqual(lean.inherit_completed(self.db,self.sources,'first','second',self.cfg),[])
    def test_larger_input_prefers_the_existing_original_even_when_row_order_changes(self):
        original=self.sources[0];record=self.cached_record()
        lean.put(self.db,'target',self.cfg,original,{'record':record});self.db.commit()
        earlier=dict(original,review_id='earlier-row',source_sha256='earlier-row-hash')
        unique,aliases=lean.select_originals(self.db,[earlier,original],'target',self.cfg)
        self.assertEqual([s['review_id'] for s in unique],['original-id'])
        self.assertEqual([(s['review_id'],o['review_id']) for s,o in aliases],[('earlier-row','original-id')])
        self.assertEqual(lean.part(self.db,'target',self.cfg,'original-id')['record'],record)

if __name__=='__main__':unittest.main()
