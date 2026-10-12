import unittest
from spotify_pipeline.evidence_review import planted_label_replay

class EvidenceReplayTests(unittest.TestCase):
    def test_planted_labels_are_detected_without_changing_saved_prediction(self):
        original={'review_id':'x','request_id':'actual-blind-call','fields':{f:{'initial':v,'independent':v} for f,v in {'topic':'usability','intent':'complaint','severity':2}.items()}}
        result=planted_label_replay(original)
        self.assertTrue(result['passed']);self.assertEqual(len(result['detected_fields']),3)
        self.assertEqual(original['fields']['severity']['initial'],2);self.assertEqual(result['new_model_calls'],0)
