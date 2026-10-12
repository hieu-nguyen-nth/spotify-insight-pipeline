import json
import tempfile
import unittest
from pathlib import Path
from spotify_pipeline import lean,reconciliation

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'control.sqlite'
        db=lean.control(self.path);self.call={'request_id':'failed-real-id','provider':'typesafe','outcome':'failed','reservation_usd':.001,
          'calculated_api_usd':None,'input_tokens':None,'output_tokens':None,'usage_status':'unavailable','billing_status':'unknown','failure_reason':'network_or_http_outcome_unknown'}
        db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('failed-real-id','run','enrich','failed',json.dumps(self.call)))
        db.execute('UPDATE budget SET spent=1.49,reserved=.001,unknown_charges=1');db.commit();db.close()
        self.evidence={'request_id':'failed-real-id','source':'provider_export','observed_at_utc':'2026-10-12T03:00:00Z','evidence_description':'Test fixture provider usage entry.',
          'billing_outcome':'charged','actual_charge_usd':'0.00042','input_tokens':10000,'output_tokens':None}
        self.receipt=self.root/'evidence.json';self.save()
    def save(self):self.receipt.write_text(json.dumps(self.evidence))
    def tearDown(self):self.tmp.cleanup()
    def test_preview_keeps_unknown_charge_and_reservation(self):
        result=reconciliation.reconcile(self.receipt,control_path=self.path);self.assertFalse(result['applied'])
        db=lean.control(self.path);self.assertEqual(db.execute('SELECT unknown_charges FROM budget').fetchone()[0],1);db.close()
    def test_apply_preserves_failure_and_missing_output_tokens_exactly_once(self):
        reconciliation.reconcile(self.receipt,True,self.path);again=reconciliation.reconcile(self.receipt,True,self.path)
        self.assertEqual(again['state'],'already_reconciled');db=lean.control(self.path)
        b=dict(db.execute('SELECT * FROM budget').fetchone());r=json.loads(db.execute('SELECT call_json FROM calls').fetchone()[0]);db.close()
        self.assertAlmostEqual(b['spent'],1.49042);self.assertEqual(b['reserved'],0);self.assertEqual(b['unknown_charges'],0)
        self.assertEqual(r['outcome'],'failed');self.assertIsNone(r['output_tokens']);self.assertIsNone(r['original_unknown_usage']['input_tokens'])
    def test_estimates_and_planted_rate_mismatch_cannot_release_reservation(self):
        for changes in ({'source':'estimated_reservation'},{'actual_charge_usd':'0.001'}):
            self.evidence.update(changes);self.save()
            with self.assertRaises(ValueError):reconciliation.reconcile(self.receipt,True,self.path)
            self.evidence['source']='provider_export'
    def test_active_run_cannot_be_settled(self):
        db=lean.control(self.path);db.execute('INSERT INTO run_locks VALUES(?,?)',('full','active'));db.commit();db.close()
        with self.assertRaises(ValueError):reconciliation.reconcile(self.receipt,True,self.path)
