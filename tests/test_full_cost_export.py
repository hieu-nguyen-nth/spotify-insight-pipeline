"""Synthetic offline fixtures only; never presented as real full-run measurements."""
import json
import tempfile
import unittest
from pathlib import Path
from cost import export_full
from spotify_pipeline import lean,budget_policy,reconciliation

class FullCostExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'reports/full_run';self.source.mkdir(parents=True)
        self.production={'state':'completed','wall_seconds':12.3,'enrichment':{'fixture':True},'analysis':{'fixture':True}}
        (self.source/'production_run.json').write_text(json.dumps(self.production))
        self.check={'status':'review_required','coverage':{'expected':660622,'valid_completed':660609,'quarantined':13,'missing':0,'duplicate_ids':0,'invalid_or_unresolved':0},
          'issue_counts':{'invalid_usage':2},'examples':[{'code':'invalid_usage','detail':'failed-id'}]*2}
        self.write_check()
        self.path=self.root/'work/control.sqlite';db=lean.control(self.path)
        success={'request_id':'good-id','run_id':'fixture','provider':'typesafe','model':'jev-1.13.0','role':'enrich','outcome':'succeeded',
          'calculated_api_usd':.002,'input_tokens':100,'output_tokens':0}
        failure={**success,'request_id':'failed-id','outcome':'failed','calculated_api_usd':None,'input_tokens':None,'output_tokens':None,'reservation_usd':.001,'billing_status':'unknown'}
        for c in (success,failure):db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',(c['request_id'],'fixture','enrich',c['outcome'],json.dumps(c)))
        db.execute('UPDATE budget SET spent=.002,reserved=.001,unknown_charges=1');db.commit();db.close()
        self.auth=self.root/'authorization.json';self.auth.write_text(json.dumps({'request_id':'failed-id','source':'explicit_user_instruction',
          'explicit_user_authorization':True,'user_instruction':'Synthetic fixture approval.','observed_at_utc':'2026-10-12T00:00:00Z','project_cap_usd':4.8,'held_usd':.05}))
        budget_policy.authorize_hold(self.auth,True,self.path)
        (self.source/'handoffs').mkdir();(self.source/'handoffs/failed-id_input.json').write_text('{}')
    def write_check(self):(self.source/'self_check.json').write_text(json.dumps(self.check))
    def tearDown(self):self.tmp.cleanup()
    def test_default_refuses_unknown_and_provisional_retains_nulls_and_checker_flags(self):
        with self.assertRaises(ValueError):export_full.export(root=self.root)
        result=export_full.export(True,self.root)
        self.assertEqual(result['known_project_api_usd'],'0.002');self.assertIsNone(result['total_project_api_usd'])
        self.assertIsNone(result['full_new_api_usd']);self.assertEqual(result['authorized_liability_hold_usd'],'0.05')
        self.assertEqual(result['checker_status'],'review_required');self.assertEqual(result['unknown_paid_request_ids'],['failed-id'])
        self.assertFalse((self.root/'cost/full').exists());self.assertTrue((self.root/'cost/full_provisional/usage.csv').exists())
        calls=[json.loads(x) for x in (self.root/'cost/full_provisional/project_calls.jsonl').read_text().splitlines()]
        self.assertIsNone(calls[1]['input_tokens']);self.assertIsNone(calls[1]['calculated_api_usd'])
    def test_provisional_cannot_hide_other_checker_failures_or_incomplete_coverage(self):
        for changed in ({'status':'review_required','issue_counts':{'invalid_usage':2,'claim_mismatch':1}},
                        {'coverage':{**self.check['coverage'],'missing':1}}):
            original=dict(self.check);self.check.update(changed);self.write_check()
            with self.assertRaises(ValueError):export_full.export(True,self.root)
            self.check=original
    def test_new_unknown_or_active_run_blocks_even_provisional(self):
        db=lean.control(self.path);db.execute('UPDATE budget SET unknown_charges=2');db.commit();db.close()
        with self.assertRaises(ValueError):export_full.export(True,self.root)
        db=lean.control(self.path);db.execute('UPDATE budget SET unknown_charges=1');db.execute('INSERT INTO run_locks VALUES(?,?)',('full','active-fixture'));db.commit();db.close()
        with self.assertRaises(ValueError):export_full.export(True,self.root)
    def test_real_usage_reconciliation_enables_actual_export(self):
        receipt=self.root/'receipt.json';receipt.write_text(json.dumps({'request_id':'failed-id','source':'provider_export','observed_at_utc':'2026-10-12T00:00:00Z',
          'evidence_description':'Synthetic fixture reported usage.','billing_outcome':'charged','actual_charge_usd':.00042,'input_tokens':10000,'output_tokens':0}))
        reconciliation.reconcile(receipt,True,self.path)
        self.check.update(status='pass',issue_counts={},examples=[]);self.write_check()
        result=export_full.export(root=self.root)
        self.assertEqual(result['total_project_api_usd'],'0.00242');self.assertEqual(result['unknown_paid_request_ids'],[])
        self.assertEqual(result['authorized_liability_hold_usd'],'0');self.assertEqual(result['cost_status'],'reconciled')
    def test_incomplete_production_blocks_before_any_export(self):
        self.production['state']='stopped';(self.source/'production_run.json').write_text(json.dumps(self.production))
        with self.assertRaises(ValueError):export_full.export(True,self.root)
        self.assertFalse((self.root/'cost').exists())
