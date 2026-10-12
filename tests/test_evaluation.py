import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spotify_pipeline.core import FIELDS,course
from spotify_pipeline.evaluation import evaluate


class EvaluationTests(unittest.TestCase):
    def fixture(self,folder):
        humans=[];predictions=[]
        for i in range(50):
            row=dict(zip(FIELDS,[str(i),'Great app','5','0','','2023-01-01']))
            row.update(topic='other',intent='praise',severity='1',sentiment='1',entities='[]',evidence_quote='Great',needs_review='false')
            humans.append(row)
            predictions.append({'review_id':str(i),'source_sha256':course.row_sha(row),'status':'completed','topic':'other','intent':'praise','severity':1,'sentiment':1,'evidence_quote':'Great','needs_review':False})
        human_path=folder/'human.csv';prediction_path=folder/'predictions.json'
        with human_path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(humans[0]));writer.writeheader();writer.writerows(humans)
        prediction_path.write_text(json.dumps(predictions))
        return human_path,prediction_path,predictions

    def test_missing_predictions_stay_in_denominator_and_human_input_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);human,predicted,rows=self.fixture(folder);original=human.read_bytes()
            predicted.write_text(json.dumps(rows[:-1]));result=evaluate(human,predicted,folder/'result.json')
            self.assertEqual(result['classification_metrics']['topic']['accuracy'],.98)
            self.assertEqual(result['severity_exact_agreement'],.98)
            self.assertEqual(result['exact_source_quote_count'],49)
            self.assertEqual(human.read_bytes(),original)

    def test_duplicate_predictions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);human,predicted,rows=self.fixture(folder)
            predicted.write_text(json.dumps(rows+[rows[0]]))
            with self.assertRaises(ValueError):evaluate(human,predicted,folder/'result.json')
