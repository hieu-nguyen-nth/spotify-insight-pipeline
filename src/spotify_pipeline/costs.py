"""Offline usage arithmetic, intentionally separate from execution."""
import csv
import json
from decimal import Decimal
from pathlib import Path


def rates(path):
    with Path(path).open(newline="") as f:
        rows = list(csv.DictReader(f))
    return {(r["provider"],r["model"],r["unit"]):Decimal(r["usd_per_unit"]) for r in rows}


def replay(calls_path, rates_path):
    price = rates(rates_path)
    total = Decimal(0)
    unknown = []
    stages = {}
    attempts = 0
    with Path(calls_path).open() as f:
        for line in f:
            call = json.loads(line)
            attempts += 1
            stage = call["role"]
            if call.get("input_tokens") is None or call.get("output_tokens") is None:
                unknown.append(call["request_id"])
                continue
            units = {"input_token":call["input_tokens"],"output_token":call["output_tokens"]}
            cost = sum((Decimal(amount)*price[(call["provider"],call["model"],unit)] for unit,amount in units.items()),Decimal(0))
            total += cost
            stages[stage] = stages.get(stage,Decimal(0))+cost
    return {"offline":True,"new_model_calls":0,"attempts":attempts,"known_api_subtotal_usd":str(total),
            "api_total_usd":str(total) if not unknown else None,"unknown_usage_request_ids":unknown,
            "by_stage_usd":{k:str(v) for k,v in stages.items()},
            "scope":"usage_arithmetic_only; complete 100-review calculator remains pending"}

