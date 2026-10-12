import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from spotify_pipeline import lean,primary_robustness as primary

class PrimaryRobustnessTests(unittest.TestCase):
    def test_preparation_excludes_expected_answers_and_has_no_network_or_ledger(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(primary,'ROOT',Path(tmp)),patch.object(primary,'dispatch') as dispatch,patch.object(primary,'control') as control:
            plan=primary.run(False)
            dispatch.assert_not_called();control.assert_not_called()
            self.assertEqual(plan['new_model_calls'],0)
            self.assertTrue(all(set(s)=={'review_id','review_text'} for s in plan['cases']))
            config,_=lean.settings(50,'v3')
            for stage in ('topic_intent','severity'):
                body=lean.body_for(plan['cases'],config,stage)
                self.assertEqual(set(body['state']),{'reviews','rubric'})
                self.assertEqual(len(body['state']['reviews']),2)
