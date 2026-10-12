"""Synthetic checker/ledger fixtures; no classification, database upload or provider calls."""
import json
import tempfile
import unittest
from pathlib import Path
from spotify_pipeline import lean,budget_policy,artifact_review,reconciliation
from spotify_pipeline.core import course,atomic_json

class ArtifactReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'work/control.sqlite'
        self.call={'request_id':'failed-id','provider':'typesafe','outcome':'failed','reservation_usd':.001,
          'calculated_api_usd':None,'input_tokens':None,'output_tokens':None,'model':'jev-1.13.0','label_config':'fixture','billing_status':'unknown'}
        self.db=lean.control(self.path);self.db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('failed-id','fixture','enrich','failed',course.canonical(self.call)))
        self.db.execute('UPDATE budget SET spent=1,reserved=.001,unknown_charges=1');self.db.commit()
        p=self.root/'auth.json';atomic_json(p,{'request_id':'failed-id','source':'explicit_user_instruction','explicit_user_authorization':True,
          'user_instruction':'Synthetic approval fixture.','observed_at_utc':'2026-10-12T00:00:00Z','project_cap_usd':4.8,'held_usd':.05})
        budget_policy.authorize_hold(p,True,self.path)
        self.check={'coverage':dict(artifact_review.FULL_COVERAGE),'status':'review_required','issue_counts':{'invalid_usage':2},
          'examples':[{'code':'invalid_usage','detail':'failed-id'}]*2}
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def test_usage_only_flag_is_retained_and_not_mislabeled_pass(self):
        r=artifact_review.assess(self.check,[self.call],self.db)
        self.assertEqual(r['checker_status'],'review_required');self.assertFalse(r['checker_passed'])
        self.assertEqual(r['cost_status'],'provisional');self.assertEqual(len(r['unavailable_usage']),2)
    def test_other_checker_error_or_missing_source_blocks_publication(self):
        for change in ({'issue_counts':{'invalid_usage':2,'claim_mismatch':1}},
                       {'coverage':{**self.check['coverage'],'missing':1}},
                       {'status':'pass','issue_counts':{},'examples':[]}):
            check={**self.check,**change}
            with self.assertRaises(ValueError):artifact_review.assess(check,[self.call],self.db)
    def test_new_unknown_failure_and_active_worker_block(self):
        self.db.execute('UPDATE budget SET unknown_charges=2');self.db.commit()
        with self.assertRaises(ValueError):artifact_review.assess(self.check,[self.call],self.db)
        self.db.execute('UPDATE budget SET unknown_charges=1');self.db.execute('INSERT INTO run_locks VALUES(?,?)',('full','fixture'));self.db.commit()
        with self.assertRaises(ValueError):artifact_review.assess(self.check,[self.call],self.db)
    def test_fake_usage_or_foreign_exception_is_rejected(self):
        for changes in ({'input_tokens':-1},{'input_tokens':'estimated'},{'request_id':'unapproved-failed-id'}):
            with self.assertRaises(ValueError):artifact_review.assess(self.check,[{**self.call,**changes}],self.db)
    def test_reconciliation_requires_fresh_checker_call_evidence(self):
        p=self.root/'receipt.json';atomic_json(p,{'request_id':'failed-id','source':'provider_export','observed_at_utc':'2026-10-12T00:00:00Z',
          'evidence_description':'Synthetic exact charge fixture, token counts unavailable.','billing_outcome':'charged','actual_charge_usd':.00042,'input_tokens':None,'output_tokens':None})
        reconciliation.reconcile(p,True,self.path)
        with self.assertRaises(ValueError):artifact_review.assess(self.check,[self.call],self.db)
        current=json.loads(self.db.execute('SELECT call_json FROM calls').fetchone()[0]);r=artifact_review.assess(self.check,[current],self.db)
        self.assertEqual(r['checker_status'],'review_required');self.assertEqual(r['cost_status'],'reconciled')
    def test_saved_review_rejects_changed_grading_artifacts(self):
        out=self.root/'reports/full_run';out.mkdir(parents=True);grading=self.root/'grading';grading.mkdir()
        atomic_json(out/'production_run.json',{'state':'completed','fixture':True})
        for name in ('records.jsonl','ranking.csv','membership.csv','claims.csv','run.json','ingestion.json','checkpoint_before.json','checkpoint_after.json'):
            (grading/name).write_text('synthetic fixture only\n')
        (grading/'calls.jsonl').write_text(course.canonical(self.call)+'\n')
        check={**self.check,'audit_script_sha256':course.sha(artifact_review.ROOT/'vendor/check_submission.py'),
          'input_files_sha256':{p.name:course.sha(p) for p in grading.iterdir()}}
        atomic_json(out/'self_check.json',check)
        self.assertFalse(artifact_review.saved_full_review(self.db,self.root)['checker_passed'])
        (grading/'ranking.csv').write_text('planted changed ranking')
        with self.assertRaises(ValueError):artifact_review.saved_full_review(self.db,self.root)
