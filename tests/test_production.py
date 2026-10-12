import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from spotify_pipeline import production,lean

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.control_path=Path(self.tmp.name)/'control.sqlite'
        self.control_patch=patch.object(production,'control',side_effect=lambda:lean.control(self.control_path));self.control_patch.start()
    def tearDown(self):self.control_patch.stop();self.tmp.cleanup()
    def test_status_counts_alias_reviews_without_inflating_distinct_first_pass(self):
        _,cfg=lean.settings(50,'v3');db=lean.control(self.control_path)
        for rid,value in [('original',{'topic':{'choice':'playback'},'record':{'cache_source_id':None}}),
                          ('alias',{'topic':{'choice':'playback'},'record':{'cache_source_id':'original'}}),
                          ('partial-original',{'topic':{'choice':'billing'}})]:
            source={'review_id':rid,'source_sha256':'fixture','text_sha256':'fixture-'+rid,'review_text':'Synthetic fixture only.'}
            lean.put(db,'full',cfg,source,value)
        db.commit();db.close();result=production.status()
        self.assertEqual(result['completed_rows'],2);self.assertEqual(result['completed_originals'],1)
        self.assertEqual(result['completed_cache_aliases'],1);self.assertEqual(result['topic_intent_rows'],2)
    def test_low_disk_blocks_paid_execution_before_any_dispatch(self):
        with patch.object(production,'prepare',return_value={'storage_ready':False}),patch.object(production,'enrich') as enrich:
            with self.assertRaisesRegex(ValueError,'6 GiB'):production.run(True)
            enrich.assert_not_called()
    def test_offline_preparation_never_dispatches(self):
        plan={'state':'prepared','storage_ready':False,'new_model_calls':0}
        with patch.object(production,'prepare',return_value=plan),patch.object(production,'enrich') as enrich:
            self.assertEqual(production.run(False),plan);enrich.assert_not_called()
    def test_unknown_usage_and_exhausted_cap_block_dispatch(self):
        for plan in ({'storage_ready':True,'unresolved_paid_usage':1,'reserved_usd':0},
                     {'storage_ready':True,'unresolved_paid_usage':0,'reserved_usd':0,'known_project_api_usage_usd':4.8}):
            db=lean.control(self.control_path);db.execute('UPDATE budget SET unknown_charges=?',(plan['unresolved_paid_usage'],));db.commit();db.close()
            with patch.object(production,'prepare',return_value=plan),patch.object(production,'enrich') as enrich:
                with self.assertRaises(ValueError):production.run(True)
                enrich.assert_not_called()
    def test_cap_cannot_expand_past_declared_ceiling(self):
        with patch.object(production,'prepare') as prepare:
            with self.assertRaises(ValueError):production.run(True,4.81)
            prepare.assert_not_called()
    def test_resume_cannot_raise_an_earlier_full_run_cap(self):
        plan={'storage_ready':True,'unresolved_paid_usage':0,'reserved_usd':0,'known_project_api_usage_usd':.1,'nonempty_reviews':660609}
        with tempfile.TemporaryDirectory() as tmp,patch.object(production,'OUT',Path(tmp)),patch.object(production,'prepare',return_value=plan),patch.object(production,'require_primary_robustness'),patch.object(production,'enrich',return_value={'stop_reason':'stopped'}) as enrich:
            production.run(True,4.5);production.run(True,4.8)
            self.assertEqual(enrich.call_args.kwargs['absolute_cap'],4.5)
    def test_missing_primary_robustness_blocks_full_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(production,'ROOT',Path(tmp)):
            with self.assertRaisesRegex(ValueError,'injection checks'):production.require_primary_robustness()
