import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from test_foundation import response
from spotify_pipeline.core import configuration, course
from spotify_pipeline.cost_probe import body_for, validate_response, replay


class CostProbeTests(unittest.TestCase):
    def setUp(self):
        self.config,_ = configuration()
        self.sources = [{"review_id":"source-a","review_text":"Playback fails","source_sha256":"hash-a"},
                        {"review_id":"source-b","review_text":"Excellent music","source_sha256":"hash-b"}]

    def test_shared_rubric_is_saved_once_with_exact_texts(self):
        body = body_for(self.sources,self.config,"shared_rubric")
        self.assertEqual(body["state"]["rubric"],self.config["questions"])
        self.assertEqual(body["state"]["reviews"]["r0"],self.sources[0]["review_text"])
        self.assertEqual(set(body["state"]),{"reviews","rubric"})
        self.assertNotIn("source-a",course.canonical(body))
        self.assertTrue(all(value is None for value in body["questions"]["r0_topic"]["criteria"].values()))
        for i in range(2):
            for field in self.config["questions"]:
                self.assertIn(f"reviews.r{i}",body["questions"][f"r{i}_{field}"]["instructions"])

    def test_batch_answer_mapping_preserves_original_identity(self):
        answers = response(self.config)["answers"]
        reply = {"model":self.config["model"],"answers":{f"r{i}_{field}":copy.deepcopy(value) for i in range(2) for field,value in answers.items()}}
        reply["answers"]["r1_topic"]["choice"] = "catalog"
        reply["answers"]["r1_topic"]["probabilities"] = {key:float(key=="catalog") for key in self.config["questions"]["topic"]["criteria"]}
        records = validate_response(reply,self.sources,self.config,"shared_rubric","probe:test")
        self.assertEqual([r["review_id"] for r in records],["source-a","source-b"])
        self.assertEqual(records[1]["source_sha256"],"hash-b")
        self.assertEqual(records[1]["topic"],"catalog")
        self.assertEqual(records[1]["evidence_quote"],"Excellent music")

    def test_missing_batch_id_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_response(response(self.config),self.sources,self.config,"shared_rubric","probe:test")

    def test_batch_over_50_is_rejected(self):
        with self.assertRaises(ValueError):
            body_for(self.sources*26,self.config,"shared_rubric")

    def test_original_single_is_byte_equivalent_body(self):
        body = body_for(self.sources[:1],self.config,"original_single")
        self.assertEqual(body,{"state":"Playback fails","model":self.config["model"],"questions":self.config["questions"]})


class ProbeReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/"records").mkdir()
        (self.root/"handoffs").mkdir()
        self.rows = [{"review_id":f"r{i}","source_sha256":f"hash{i}","evidence_quote":f"text{i}","topic":"other","intent":"praise","severity":1,"sentiment":1.0,"needs_review":False} for i in range(20)]
        (self.root/"records/original_single_1.json").write_text(json.dumps(self.rows))
        (self.root/"records/shared_rubric_20.json").write_text(json.dumps(self.rows))
        (self.root/"run.json").write_text(json.dumps({"run_id":"fixture","review_ids":[r["review_id"] for r in self.rows],"wall_seconds":10,"design_results":{"original_single_1":{"wall_seconds":9},"shared_rubric_20":{"wall_seconds":1}}}))
        self.calls = [{"request_id":f"call{i}","run_id":"fixture","role":"enrich","provider":"typesafe","model":"jev-1.13.0","batch_size":1,"input_tokens":100,"output_tokens":10,"elapsed_seconds":0.4,"outcome":"succeeded","usage_status":"provider_reported"} for i in range(20)]
        self.calls.append(dict(self.calls[0],request_id="batch",batch_size=20,input_tokens=1000,output_tokens=200,elapsed_seconds=1.0))
        (self.root/"calls.json").write_text(json.dumps(self.calls))
        for call in self.calls:
            (self.root/"handoffs"/(call["request_id"]+"_input.json")).write_text(json.dumps({"design":"shared_rubric_20" if call["request_id"]=="batch" else "original_single_1"}))
        self.rates = self.root/"rates.csv"
        self.rates.write_text("provider,model,unit,usd_per_unit\ntypesafe,jev-1.13.0,input_token,0.000000042\ntypesafe,jev-1.13.0,output_token,0\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_doubling_rates_changes_cost_only(self):
        first = replay(self.root,self.rates)
        self.rates.write_text(self.rates.read_text().replace("0.000000042","0.000000084"))
        second = replay(self.root,self.rates)
        self.assertEqual(Decimal(second["experiment_api_total_usd"]),Decimal(first["experiment_api_total_usd"])*2)
        self.assertEqual(second["actual_experiment_wall_seconds"],first["actual_experiment_wall_seconds"])
        self.assertEqual(second["new_model_calls"],0)

    def test_projection_change_leaves_measurements_unchanged(self):
        first = replay(self.root,self.rates,100,200)
        second = replay(self.root,self.rates,200,400)
        self.assertEqual(second["experiment_api_total_usd"],first["experiment_api_total_usd"])
        for name in first["designs"]:
            self.assertEqual(second["designs"][name]["input_tokens"],first["designs"][name]["input_tokens"])
            self.assertEqual(Decimal(second["designs"][name]["projected_unique_enrichment_api_usd"]),Decimal(first["designs"][name]["projected_unique_enrichment_api_usd"])*2)

    def test_unknown_usage_remains_unknown(self):
        self.calls[-1]["input_tokens"] = None
        (self.root/"calls.json").write_text(json.dumps(self.calls))
        report = replay(self.root,self.rates)
        self.assertIsNone(report["experiment_api_total_usd"])
        self.assertIsNone(report["designs"]["shared_rubric_20"]["projected_unique_enrichment_api_usd"])
        self.assertEqual(report["unknown_request_ids"],["batch"])


if __name__ == "__main__":
    unittest.main()
