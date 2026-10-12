"""Offline fixtures only. These are NOT actual paid-call or semantic-evaluation evidence."""
import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from spotify_pipeline.core import FIELDS, configuration, connect, course, ingest, mapped_response, request_body, status
from spotify_pipeline.costs import replay
from spotify_pipeline.jev import enrich


def response(config, topic="playback", severity="4"):
    selected = {"topic":topic,"intent":"complaint","severity":severity}
    answers = {}
    for name,choice in selected.items():
        answers[name] = {"type":"choice","choice":choice,"confidence":1.0,
                         "probabilities":{k:float(k==choice) for k in config["questions"][name]["criteria"]}}
    answers["sentiment"] = {"type":"score","score":0.0}
    answers["ambiguous"] = {"type":"noul","noul":0.0}
    return {"model":config["model"],"answers":answers,"usage":{"input_tokens":300,"output_tokens":80}}


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.csv = self.folder/"input.csv"
        self.db = self.folder/"state.sqlite"
        self.out = self.folder/"run"
        self.rows = [dict(zip(FIELDS,values)) for values in [
            ("a","Music crashes\nwhen I play. café","1","2","","2023-01-01 12:00:00"),
            ("b","Music crashes\nwhen I play. café","5","0","v1","2023-01-02 12:00:00"),
            ("c","","3","0","","2023-01-03 12:00:00"),
            ("d","Offline playback fails","1","0","v2","2023-01-04 12:00:00")]]
        with self.csv.open("w",newline="") as f:
            writer = csv.DictWriter(f,fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)
        ingest(self.csv,self.db,self.folder/"ingestion_report.json")
        self.config,self.label_config = configuration()
        self.env_patch = patch.dict(os.environ,{"TYPESAFE_API_KEY":"synthetic-test-placeholder"})
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    def execute(self,limit=1,cap=0.25,transport=None):
        return enrich(self.db,self.out,self.folder/"missing.env",limit,cap,transport=transport or (lambda body,key:response(self.config)))

    def test_ingestion_preserves_multiline_unicode_and_exact_hash(self):
        db = connect(self.db)
        a = dict(db.execute("SELECT * FROM source_reviews WHERE review_id='a'").fetchone())
        self.assertEqual(a["review_text"],self.rows[0]["review_text"])
        self.assertEqual(a["source_sha256"],course.row_sha(self.rows[0]))
        self.assertEqual(status(self.db)["unique_nonempty_texts"],2)
        self.assertEqual(status(self.db)["empty_quarantines"],1)
        db.close()

    def test_ingestion_repeat_is_idempotent(self):
        report = ingest(self.csv,self.db,self.folder/"again.json")
        self.assertTrue(report["reused_existing_ingestion"])
        self.assertEqual(status(self.db)["source_rows"],4)

    def test_mixed_source_is_rejected(self):
        extra = self.folder/"different.csv"
        extra.write_text(self.csv.read_text().replace("café","changed"))
        with self.assertRaises(ValueError):
            ingest(extra,self.db,self.folder/"bad.json")

    def test_payload_contains_no_rating_or_human_answers(self):
        body = request_body(self.rows[0]["review_text"],self.config)
        self.assertEqual(body["state"],self.rows[0]["review_text"])
        self.assertEqual(set(body),{"state","model","questions"})

    def test_cold_warm_same_window_zero_new_calls(self):
        first = self.execute()
        self.assertEqual(first["attempts"],1)
        second = self.execute(transport=lambda *_:self.fail("Warm run made a new call"))
        self.assertEqual(second["attempts"],0)
        self.assertEqual(second["cache_hits"],1)

    def test_resume_and_direct_exact_text_reuse(self):
        self.execute(1)
        second = self.execute(3)
        self.assertEqual(second["phase"],"resume")
        self.assertEqual(second["attempts"],1)
        db = connect(self.db)
        b = json.loads(db.execute("SELECT record_json FROM results WHERE review_id='b'").fetchone()[0])
        self.assertEqual(b["cache_source_id"],"a")
        self.assertEqual(b["source_sha256"],course.row_sha(self.rows[1]))
        self.assertEqual(status(self.db)["completed"],3)
        db.close()

    def test_each_run_preserves_its_own_checkpoints(self):
        first = self.execute()
        self.execute(3)
        saved = self.out/"runs"/first["run_id"]
        self.assertEqual(json.loads((saved/"checkpoint_before.json").read_text())["completed_ids"],[])
        self.assertEqual(json.loads((saved/"checkpoint_after.json").read_text())["completed_ids"],["a"])

    def test_budget_stops_before_transport(self):
        summary = self.execute(cap=0.000000001,transport=lambda *_:self.fail("Over-budget call dispatched"))
        self.assertEqual(summary["stop_reason"],"budget_stop")
        self.assertEqual(summary["attempts"],0)

    def test_invalid_output_retries_only_once_then_quarantines(self):
        bad = response(self.config)
        bad["answers"]["severity"]["choice"] = "9"
        summary = self.execute(transport=lambda *_:bad)
        self.assertEqual(summary["attempts"],2)
        self.assertEqual(status(self.db)["nonempty_failures"],1)

    def test_missing_usage_stops_and_is_not_zero_cost(self):
        reply = response(self.config)
        reply.pop("usage")
        summary = self.execute(3,transport=lambda *_:reply)
        self.assertEqual(summary["attempts"],1)
        self.assertEqual(summary["stop_reason"],"unknown_charge_stop")
        report = replay(self.out/"calls.jsonl",ROOT/"cost/rates.csv")
        self.assertIsNone(report["api_total_usd"])
        self.assertEqual(len(report["unknown_usage_request_ids"]),1)

    def test_model_version_change_is_rejected(self):
        reply = response(self.config)
        reply["model"] = "different-version"
        db = connect(self.db)
        source = dict(db.execute("SELECT * FROM source_reviews LIMIT 1").fetchone())
        with self.assertRaises(ValueError):
            mapped_response(reply,source,self.config,self.label_config)
        db.close()

    def test_two_decimal_probability_rounding_preserves_labels(self):
        reply = response(self.config)
        reply["answers"]["intent"]["choice"] = "praise"
        reply["answers"]["intent"]["probabilities"] = {"cancellation":0.0,"complaint":0.27,"request":0.0,"praise":0.55,"unclear":0.17}
        db = connect(self.db)
        source = dict(db.execute("SELECT * FROM source_reviews LIMIT 1").fetchone())
        record = mapped_response(reply,source,self.config,self.label_config)
        self.assertEqual(record["intent"],"praise")
        self.assertAlmostEqual(sum(reply["answers"]["intent"]["probabilities"].values()),0.99)
        db.close()

    def test_probability_mass_outside_rounding_interval_rejected(self):
        reply = response(self.config)
        reply["answers"]["intent"]["probabilities"] = {"cancellation":0.0,"complaint":0.1,"request":0.0,"praise":0.55,"unclear":0.17}
        db = connect(self.db)
        source = dict(db.execute("SELECT * FROM source_reviews LIMIT 1").fetchone())
        with self.assertRaises(ValueError):
            mapped_response(reply,source,self.config,self.label_config)
        db.close()

    def test_malformed_response_stops_with_unknown_charge(self):
        summary = self.execute(3,transport=lambda *_:[])
        self.assertEqual(summary["attempts"],1)
        self.assertEqual(summary["stop_reason"],"unknown_charge_stop")
        db = connect(self.db)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM calls WHERE outcome='in_flight'").fetchone()[0],0)
        db.close()

    def test_malformed_usage_is_unknown_not_free(self):
        reply = response(self.config)
        reply["usage"] = []
        summary = self.execute(3,transport=lambda *_:reply)
        self.assertEqual(summary["stop_reason"],"unknown_charge_stop")
        self.assertEqual(status(self.db)["budget"]["unknown_charges"],1)

    def test_replay_doubled_rates_doubles_spend_without_calls(self):
        self.execute()
        first = replay(self.out/"calls.jsonl",ROOT/"cost/rates.csv")
        doubled = self.folder/"double.csv"
        from decimal import Decimal
        with (ROOT/"cost/rates.csv").open(newline="") as f:
            reader = csv.DictReader(f)
            names = reader.fieldnames
            rows = list(reader)
        for row in rows:
            row["usd_per_unit"] = str(Decimal(row["usd_per_unit"])*2)
        with doubled.open("w",newline="") as f:
            writer = csv.DictWriter(f,fieldnames=names)
            writer.writeheader()
            writer.writerows(rows)
        second = replay(self.out/"calls.jsonl",doubled)
        self.assertEqual(Decimal(second["api_total_usd"]),Decimal(first["api_total_usd"])*2)
        self.assertEqual(second["new_model_calls"],0)

    def test_imports_and_replay_require_no_api_key(self):
        self.execute()
        with patch.dict(os.environ,{"TYPESAFE_API_KEY":""}):
            self.assertEqual(replay(self.out/"calls.jsonl",ROOT/"cost/rates.csv")["new_model_calls"],0)


if __name__ == "__main__":
    unittest.main()
