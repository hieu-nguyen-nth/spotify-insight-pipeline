import unittest
import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spotify_pipeline.analysis import ranking,verify
from spotify_pipeline import lean
from spotify_pipeline.label_ui import validate

class AnalysisTests(unittest.TestCase):
    def test_ranking_excludes_praise_counts_aliases_and_breaks_ties(self):
        records=[{'review_id':'a','status':'completed','topic':'playback','intent':'complaint','severity':3},
                 {'review_id':'b','status':'completed','topic':'playback','intent':'cancellation','severity':1,'cache_source_id':'a'},
                 {'review_id':'c','status':'completed','topic':'access','intent':'complaint','severity':4},
                 {'review_id':'d','status':'completed','topic':'access','intent':'praise','severity':1}]
        members,rows,claims=ranking(records)
        self.assertEqual([r['issue_id'] for r in rows],['issue_access','issue_playback'])
        self.assertEqual(rows[1]['complaint_count'],2);self.assertEqual(rows[1]['mean_severity'],'2.000000')
        self.assertEqual(len(members),3);self.assertEqual(len(claims),8)
    def test_half_up_mean(self):
        rs=[{'review_id':str(i),'status':'completed','topic':'other','intent':'complaint','severity':v} for i,v in enumerate([1,1,2])]
        self.assertEqual(ranking(rs)[1][0]['mean_severity'],'1.333333')
    def test_human_label_quote_validation(self):
        values={'topic':'other','intent':'praise','severity':'1','sentiment':'0.7','entities':'[]','evidence_quote':'Great','needs_review':'false'}
        self.assertEqual(validate(values,{'review_text':'Great app'})['intent'],'praise')
        values['evidence_quote']='invented'
        with self.assertRaises(ValueError):validate(values,{'review_text':'Great app'})
    def test_human_sentiment_rejects_nan(self):
        v={'topic':'other','intent':'praise','severity':'1','sentiment':'nan','entities':'[]','evidence_quote':'Great','needs_review':'false'}
        with self.assertRaises(ValueError):validate(v,{'review_text':'Great'})
    def test_large_blind_sample_is_bounded_and_resume_reuses_batch_results(self):
        sources=[{'review_id':str(i),'review_text':'Playback is blocked.','source_sha256':'row'+str(i),'text_sha256':'text'} for i in range(53)]
        records=[{'review_id':s['review_id'],'topic':'playback','intent':'complaint','severity':4,'secret_initial_label':'never-send'} for s in sources]
        sent=[]
        def transport(body,key):
            self.assertNotIn('never-send',json.dumps(body));self.assertLessEqual(len(body['state']['reviews']),50)
            sent.append(body)
            answers={}
            for k,q in body['questions'].items():
                selected={'topic':'playback','intent':'complaint','severity':'4'}[k.split('_')[-1]]
                answers[k]={'type':'choice','choice':selected,'confidence':1,'probabilities':{v:float(v==selected) for v in q['criteria']}}
            return {'model':lean.MODEL,'answers':answers,'usage':{'input_tokens':100,'output_tokens':10}}
        with tempfile.TemporaryDirectory() as tmp:
            db=lean.control(Path(tmp)/'control.sqlite');config,cfg=lean.settings(50,'v3')
            a=verify(records,sources,config,cfg,db,tmp,'first',.01,'test',transport,sample_size=53)
            self.assertEqual(len(sent),2);self.assertEqual(len(a['sample_ids']),53);self.assertEqual(a['disagreement_count'],0)
            b=verify(records,list(reversed(sources)),config,cfg,db,tmp,'resume',.01,'test',transport,sample_size=53)
            self.assertEqual(len(sent),2);self.assertTrue(b['cache_hit']);self.assertEqual(a['sample_ids'],b['sample_ids'])
            self.assertEqual(len(set(b['sample_ids'])),53);db.close()
