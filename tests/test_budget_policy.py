import json
import tempfile
import unittest
from pathlib import Path
from spotify_pipeline import lean,budget_policy,reconciliation

class UnknownHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'control.sqlite'
        self.call={'request_id':'failed-id','provider':'typesafe','outcome':'failed','reservation_usd':.001,
          'calculated_api_usd':None,'input_tokens':None,'output_tokens':None,'billing_status':'unknown'}
        db=lean.control(self.path)
        db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('failed-id','run','enrich','failed',json.dumps(self.call)))
        db.execute('UPDATE budget SET spent=1.49,reserved=.001,unknown_charges=1');db.commit();db.close()
        self.auth={'request_id':'failed-id','source':'explicit_user_instruction','explicit_user_authorization':True,
          'user_instruction':'Test fixture: resume with an unknown charge held at $0.05.',
          'observed_at_utc':'2026-10-12T03:00:00Z','project_cap_usd':4.8,'held_usd':.05}
        self.file=self.root/'auth.json';self.file.write_text(json.dumps(self.auth))
    def tearDown(self):self.tmp.cleanup()
    def hold(self):return budget_policy.authorize_hold(self.file,True,self.path)
    def test_preview_does_not_change_ledger(self):
        budget_policy.authorize_hold(self.file,False,self.path)
        db=lean.control(self.path);self.assertIsNotNone(budget_policy.dispatch_block_reason(db))
        self.assertEqual(db.execute('SELECT reserved FROM budget').fetchone()[0],.001);db.close()
    def test_hold_keeps_unknown_usage_and_is_idempotent(self):
        self.hold();self.assertEqual(self.hold()['state'],'already_held')
        db=lean.control(self.path);b=dict(db.execute('SELECT * FROM budget').fetchone())
        call=json.loads(db.execute('SELECT call_json FROM calls').fetchone()[0])
        self.assertAlmostEqual(b['spent'],1.49);self.assertAlmostEqual(b['reserved'],.05);self.assertEqual(b['unknown_charges'],1)
        self.assertIsNone(call['calculated_api_usd']);self.assertEqual(call['billing_status'],'unknown')
        self.assertIsNone(budget_policy.dispatch_block_reason(db));db.close()
    def test_new_unknown_or_inflight_stops_dispatch(self):
        self.hold();db=lean.control(self.path)
        db.execute('UPDATE budget SET unknown_charges=2');self.assertIsNotNone(budget_policy.dispatch_block_reason(db))
        db.execute('UPDATE budget SET unknown_charges=1')
        db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('new','run','enrich','in_flight','{}'))
        self.assertIsNotNone(budget_policy.dispatch_block_reason(db));db.close()
    def test_cap_cannot_be_raised_and_overcap_hold_rejected(self):
        self.auth['project_cap_usd']=5;self.file.write_text(json.dumps(self.auth))
        with self.assertRaises(ValueError):self.hold()
        self.auth['project_cap_usd']=4.8;self.file.write_text(json.dumps(self.auth))
        db=lean.control(self.path);db.execute('UPDATE budget SET spent=4.76');db.commit();db.close()
        with self.assertRaises(ValueError):self.hold()
    def test_real_receipt_releases_entire_hold_and_preserves_audit(self):
        self.hold();receipt=self.root/'receipt.json'
        receipt.write_text(json.dumps({'request_id':'failed-id','source':'provider_export','observed_at_utc':'2026-10-12T03:00:00Z',
          'evidence_description':'Test fixture actual usage.','billing_outcome':'charged','actual_charge_usd':.00042,'input_tokens':10000,'output_tokens':None}))
        reconciliation.reconcile(receipt,True,self.path)
        db=lean.control(self.path);b=dict(db.execute('SELECT * FROM budget').fetchone())
        self.assertEqual(b['unknown_charges'],0);self.assertEqual(b['reserved'],0);self.assertAlmostEqual(b['spent'],1.49042)
        self.assertEqual(db.execute('SELECT active FROM unknown_charge_holds').fetchone()[0],0)
        self.assertIsNone(budget_policy.dispatch_block_reason(db));db.close()
    def test_hold_counts_toward_next_dispatch_cap(self):
        self.hold();db=lean.control(self.path)
        with self.assertRaisesRegex(ValueError,'spend reservation'):
            lean.dispatch(db,{'state':'test'},[{'review_id':'new'}],'new-run','cfg','resume','enrich',1.54,self.root,transport=lambda body,key:None,key='fixture')
        self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0],1);db.close()

    def test_user_stop_blocks_classification_without_changing_usage(self):
        self.hold();db=lean.control(self.path)
        db.execute('INSERT INTO stopped_roles VALUES(?,?)',('enrich','Finalize completed records only.'));db.commit()
        before=dict(db.execute('SELECT * FROM budget').fetchone())
        called=[]
        with self.assertRaisesRegex(ValueError,'User stopped'):
            lean.dispatch(db,{},[{'review_id':'new'}],'run','cfg','resume','enrich',4.8,self.root,
                          transport=lambda body,key:called.append(body),key='fixture')
        self.assertEqual(called,[]);self.assertEqual(dict(db.execute('SELECT * FROM budget').fetchone()),before)
        self.assertIsNone(budget_policy.dispatch_block_reason(db,'verify'));db.close()
