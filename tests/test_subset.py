import copy
import unittest
from spotify_pipeline.subset import require_expected_findings

class SubsetFindingTests(unittest.TestCase):
    def fixture(self):
        count=244582
        result={'status':'review_required','coverage':{'expected':660622,'valid_completed':count,
          'quarantined':13,'missing':660609-count,'duplicate_ids':0,'invalid_or_unresolved':0},
          'issue_counts':{'missing_records':1,'unfinished_classification':1,'invalid_usage':2}}
        calls=[{'request_id':'03cb9c58-d8c1-4500-864e-4b9049ddbe6d','input_tokens':None,'output_tokens':None}]
        return result,count,calls
    def test_expected_scope_and_unavailable_usage_are_preserved(self):
        checked,count,calls=self.fixture();before=copy.deepcopy(checked)
        require_expected_findings(checked,count,calls);self.assertEqual(checked,before)
    def test_other_errors_and_forged_pass_are_blocked(self):
        checked,count,calls=self.fixture();checked['issue_counts']['invalid_cache_reuse']=1
        with self.assertRaises(ValueError):require_expected_findings(checked,count,calls)
        checked,count,calls=self.fixture();checked['status']='pass'
        with self.assertRaises(ValueError):require_expected_findings(checked,count,calls)
    def test_changed_coverage_or_new_unknown_usage_are_blocked(self):
        checked,count,calls=self.fixture();checked['coverage']['missing']-=1
        with self.assertRaises(ValueError):require_expected_findings(checked,count,calls)
        checked,count,calls=self.fixture();calls.append({'request_id':'unapproved','input_tokens':None,'output_tokens':None})
        with self.assertRaises(ValueError):require_expected_findings(checked,count,calls)
