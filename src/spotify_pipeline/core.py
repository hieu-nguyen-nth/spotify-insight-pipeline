import csv
import hashlib
import importlib.util
import json
import math
import os
import sqlite3
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("course_checker", ROOT / "vendor/check_submission.py")
course = importlib.util.module_from_spec(spec)
spec.loader.exec_module(course)
FIELDS = course.FIELDS
TOPICS = course.TOPICS
INTENTS = course.INTENTS


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS source_reviews (
        review_id TEXT PRIMARY KEY, review_text TEXT NOT NULL, review_rating TEXT NOT NULL,
        review_likes TEXT NOT NULL, app_version TEXT NOT NULL, review_timestamp TEXT NOT NULL,
        source_sha256 TEXT NOT NULL, text_sha256 TEXT NOT NULL, canonical_id TEXT,
        source_order INTEGER NOT NULL, source_status TEXT NOT NULL, reason TEXT);
      CREATE TABLE IF NOT EXISTS unique_texts (
        text_sha256 TEXT PRIMARY KEY, canonical_id TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS results (
        review_id TEXT NOT NULL, label_config TEXT NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(review_id,label_config));
      CREATE TABLE IF NOT EXISTS calls (
        request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT NOT NULL,
        outcome TEXT NOT NULL, call_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS budget (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), spent REAL NOT NULL,
        reserved REAL NOT NULL, unknown_charges INTEGER NOT NULL);
      INSERT OR IGNORE INTO budget VALUES(1,0,0,0);
    """)
    db.commit()
    return db


def meta(db, key, value=None):
    if value is not None:
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", (key, json.dumps(value)))
    row = db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def verify_dataset(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    results = []
    for name, expected in manifest["files"].items():
        p = directory / name
        got = {"bytes": p.stat().st_size, "sha256": course.sha(p)}
        results.append({"file": name, "expected": expected, "actual": got, "matches": got == expected})
    samples = {}
    for name in ("cost_100.csv", "checkpoint_500.csv", "analysis_10000.csv", "golden_50_to_label.csv"):
        samples[name] = list(course.csv_rows(directory / name))
    def source_rows(rows):
        return [[r[f] for f in FIELDS] for r in rows]
    nesting = (source_rows(samples["cost_100.csv"]) == source_rows(samples["checkpoint_500.csv"][:100])
               and source_rows(samples["checkpoint_500.csv"]) == source_rows(samples["analysis_10000.csv"][:500]))
    development_ids = {r["review_id"] for r in samples["analysis_10000.csv"]}
    golden_ids = {r["review_id"] for r in samples["golden_50_to_label.csv"]}
    report = {"files": results, "nested_development_samples": nesting,
              "golden_development_overlap": len(golden_ids & development_ids),
              "sample_counts": {k: len(v) for k,v in samples.items()}}
    report["passed"] = all(x["matches"] for x in results) and nesting and not (golden_ids & development_ids)
    return report


def ingest(csv_path, db_path, report_path, manifest_path=None):
    started = time.perf_counter()
    csv_path = Path(csv_path).resolve()
    fingerprint = course.sha(csv_path)
    db = connect(db_path)
    old = meta(db, "source_sha256")
    if old is not None and old != fingerprint:
        raise ValueError("This database belongs to a different CSV. Choose a separate database.")
    # Use the provided deterministic helper without recreating its format.
    profile = course.profile(csv_path)
    if meta(db, "ingestion_complete"):
        report = meta(db, "ingestion_report")
        atomic_json(report_path, report)
        db.close()
        return dict(report, reused_existing_ingestion=True)
    meta(db, "source_sha256", fingerprint)
    meta(db, "source_path", str(csv_path))
    db.commit()
    seen_ids = set()
    processed = 0
    for i, row in enumerate(course.csv_rows(csv_path)):
        rid = row["review_id"]
        if rid in seen_ids:
            raise ValueError("Repeated source review_id: " + rid)
        seen_ids.add(rid)
        text = row["review_text"]
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        empty = not text.strip()
        first = None
        if not empty:
            hit = db.execute("SELECT canonical_id FROM unique_texts WHERE text_sha256=?", (text_hash,)).fetchone()
            if hit:
                first = hit[0]
                original = db.execute("SELECT review_text FROM source_reviews WHERE review_id=?", (first,)).fetchone()
                if original[0] != text:
                    raise ValueError("Text-hash collision; exact comparison failed.")
            else:
                first = rid
                db.execute("INSERT INTO unique_texts VALUES(?,?)", (text_hash, rid))
        db.execute("INSERT OR IGNORE INTO source_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (*[row[f] for f in FIELDS], course.row_sha(row), text_hash, first, i,
                    "quarantined" if empty else "pending", "empty_review_text" if empty else None))
        processed += 1
        if processed % 5000 == 0:
            db.commit()
    db.execute("CREATE INDEX IF NOT EXISTS source_canonical_idx ON source_reviews(canonical_id)")
    db.execute("CREATE INDEX IF NOT EXISTS source_order_idx ON source_reviews(source_order)")
    unique = db.execute("SELECT COUNT(*) FROM unique_texts").fetchone()[0]
    stored = db.execute("SELECT COUNT(*) FROM source_reviews").fetchone()[0]
    expected_match = None
    if manifest_path:
        expected = json.loads(Path(manifest_path).read_text())
        expected_match = (profile["file_sha256"] == expected["files"][csv_path.name]["sha256"]
                          and profile["counts"] == expected["profile"]
                          and profile["reviews_by_month"] == expected["reviews_by_month"]
                          and profile["reviews_by_rating"] == expected["reviews_by_rating"]
                          and profile["first_review"] == expected["window"]["first_review"]
                          and profile["last_review"] == expected["window"]["last_review"])
    report = {"source": str(csv_path), "profile": profile, "stored_rows": stored,
              "nonempty_rows": stored-profile["counts"]["empty_review_text"],
              "distinct_nonempty_texts": unique,
              "reusable_duplicate_rows": stored-profile["counts"]["empty_review_text"]-unique,
              "expected_manifest_match": expected_match, "ingestion_seconds": time.perf_counter()-started,
              "classification_completed": 0, "classification_pending": stored-profile["counts"]["empty_review_text"],
              "stage": "ingestion_only", "api_calls": 0}
    assert stored == profile["counts"]["records"]
    meta(db, "profile", profile)
    meta(db, "ingestion_report", report)
    meta(db, "ingestion_complete", True)
    db.commit()
    atomic_json(report_path, report)
    atomic_json(Path(report_path).with_name("ingestion.json"), profile)
    if expected_match is False:
        raise ValueError("Ingestion does not match the supplied full-file manifest; inspect report.")
    db.close()
    return report


def configuration(path=None):
    config = json.loads(Path(path or ROOT / "prompts/jev_enrich_v1.json").read_text())
    config_hash = hashlib.sha256(course.canonical(config).encode()).hexdigest()[:20]
    return config, f"{config['model']}:{config['prompt_version']}:{config_hash}"


def request_body(text, config):
    # Source metadata and human answer labels never enter this payload.
    return {"state": text, "model": config["model"], "questions": config["questions"]}


def valid_record(record, source):
    if record.get("review_id") != source["review_id"] or record.get("source_sha256") != source["source_sha256"]:
        raise ValueError("Source identity mismatch")
    if record.get("topic") not in TOPICS or record.get("intent") not in INTENTS:
        raise ValueError("Invalid topic/intent")
    if type(record.get("severity")) is not int or not 1 <= record["severity"] <= 5:
        raise ValueError("Invalid severity")
    sentiment = record.get("sentiment")
    if type(sentiment) not in (int,float) or not math.isfinite(sentiment) or not -1 <= sentiment <= 1:
        raise ValueError("Invalid sentiment")
    if type(record.get("needs_review")) is not bool:
        raise ValueError("Invalid review flag")
    quote = record.get("evidence_quote")
    if not isinstance(quote,str) or not quote.strip() or quote not in source["review_text"]:
        raise ValueError("Unsupported evidence quote")
    if not isinstance(record.get("entities"),list) or any(not isinstance(v,str) or not v.strip() for v in record["entities"]):
        raise ValueError("Invalid entities")
    if not record.get("label_config") or record.get("status") != "completed":
        raise ValueError("Invalid status/configuration")


def mapped_response(response, source, config, label_config):
    if not isinstance(response, dict):
        raise ValueError("Provider response must be an object")
    if response.get("model") != config["model"]:
        raise ValueError("Provider model differs from pinned configuration")
    answers = response["answers"]
    if not isinstance(answers, dict) or any(not isinstance(answer, dict) for answer in answers.values()):
        raise ValueError("Provider answers must be objects")
    if set(answers) != set(config["questions"]):
        raise ValueError("Missing or unexpected question IDs")
    selected = {}
    confidences = []
    for field in ("topic", "intent", "severity"):
        answer = answers[field]
        if answer.get("type") != "choice" or answer.get("choice") not in config["questions"][field]["criteria"]:
            raise ValueError("Invalid Choice answer: " + field)
        selected[field] = answer["choice"]
        value = answer.get("confidence")
        if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid confidence")
        probabilities = answer.get("probabilities",{})
        if not isinstance(probabilities, dict):
            raise ValueError("Invalid probability object")
        if set(probabilities) != set(config["questions"][field]["criteria"]):
            raise ValueError("Invalid probability options")
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values()):
            raise ValueError("Invalid probability values")
        total = sum(probabilities.values())
        if abs(total-1)>0.001:
            # Observed provider distributions use two-decimal rounding. Retain
            # raw values; accept only when their rounding intervals can sum to 1.
            two_decimal = all(abs(v*100-round(v*100))<1e-9 for v in probabilities.values())
            lower = sum(max(0,v-0.005) for v in probabilities.values())
            upper = sum(min(1,v+0.005) for v in probabilities.values())
            if not two_decimal or not lower-1e-12 <= 1 <= upper+1e-12:
                raise ValueError("Probabilities cannot sum to one within reported rounding")
        confidences.append(value)
    score = answers["sentiment"].get("score")
    noul = answers["ambiguous"].get("noul")
    for value, upper in ((score,4),(noul,1)):
        if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= upper:
            raise ValueError("Invalid Score/Noul range")
    if answers["sentiment"].get("type") != "score" or answers["ambiguous"].get("type") != "noul":
        raise ValueError("Invalid answer types")
    import re
    pattern = r"(?<!\w)(?:offline|downloads?|playlists?|podcasts?|lyrics|premium|ads|shuffle|queue|login|search|recommendations?|bluetooth)(?!\w)"
    entities = list(dict.fromkeys(m.group(0) for m in re.finditer(pattern,source["review_text"],re.I)))
    record = {"review_id": source["review_id"], "source_sha256": source["source_sha256"], "status": "completed",
              "topic": selected["topic"], "intent": selected["intent"], "severity": int(selected["severity"]),
              "sentiment": score/2-1, "entities": entities, "evidence_quote": source["review_text"],
              "needs_review": min(confidences)<config["minimum_confidence"] or noul>=config["ambiguity_probability_threshold"],
              "label_config": label_config}
    valid_record(record, source)
    return record


def save_result(db, record):
    db.execute("INSERT OR REPLACE INTO results VALUES(?,?,?)", (record["review_id"],record["label_config"],course.canonical(record)))


def reuse_cached(db, source, label_config):
    exact = db.execute("SELECT record_json FROM results WHERE review_id=? AND label_config=?", (source["review_id"],label_config)).fetchone()
    if exact:
        record = json.loads(exact[0])
        if record.get("status") == "completed":
            valid_record(record,source)
            return record
        return None
    hits = db.execute("""SELECT r.record_json,s.review_text FROM results r
        JOIN source_reviews s ON r.review_id=s.review_id
        WHERE s.text_sha256=? AND r.label_config=? ORDER BY s.source_order""", (source["text_sha256"],label_config))
    for hit in hits:
        original = json.loads(hit[0])
        if original["status"] != "completed" or original.get("cache_source_id") or hit[1] != source["review_text"]:
            continue
        record = dict(original, review_id=source["review_id"],source_sha256=source["source_sha256"],cache_source_id=original["review_id"])
        valid_record(record,source)
        save_result(db,record)
        return record
    return None


def status(db_path, label_config=None):
    db = connect(db_path)
    total = db.execute("SELECT COUNT(*) FROM source_reviews").fetchone()[0]
    empty = db.execute("SELECT COUNT(*) FROM source_reviews WHERE source_status='quarantined'").fetchone()[0]
    records = [json.loads(r[0]) for r in db.execute("SELECT record_json FROM results" + (" WHERE label_config=?" if label_config else ""), (label_config,) if label_config else ())]
    completed_ids = {r["review_id"] for r in records if r["status"] == "completed"}
    failed_ids = {r["review_id"] for r in records if r["status"] == "quarantined"} - completed_ids
    result = {"source_rows":total,"empty_quarantines":empty,"completed":len(completed_ids),
              "nonempty_failures":len(failed_ids),"pending":total-empty-len(completed_ids)-len(failed_ids),
              "unique_nonempty_texts":db.execute("SELECT COUNT(*) FROM unique_texts").fetchone()[0],
              "budget":dict(db.execute("SELECT * FROM budget").fetchone()),
              "attempted_calls":db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]}
    db.close()
    return result


def snapshot(db, label_config):
    return {"completed_ids":sorted(json.loads(r[0])["review_id"] for r in db.execute("SELECT record_json FROM results WHERE label_config=?",(label_config,)) if json.loads(r[0])["status"]=="completed")}


def export_progress(db_path, outdir, label_config):
    outdir = Path(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    db = connect(db_path)
    # This is a progress export, not grading/records.jsonl: pending records stay visible.
    fd,tmp = tempfile.mkstemp(dir=outdir)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        for source in db.execute("SELECT * FROM source_reviews ORDER BY source_order"):
            saved = db.execute("SELECT record_json FROM results WHERE review_id=? AND label_config=?",(source["review_id"],label_config)).fetchone()
            record = json.loads(saved[0]) if saved else {"review_id":source["review_id"],"source_sha256":source["source_sha256"],
                  "status":source["source_status"], **({"reason":source["reason"]} if source["reason"] else {})}
            f.write(course.canonical(record)+"\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp,outdir/"records_progress.jsonl")
    calls = [json.loads(r[0]) for r in db.execute("SELECT call_json FROM calls ORDER BY rowid")]
    fd,tmp = tempfile.mkstemp(dir=outdir)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        for call in calls:
            f.write(course.canonical(call)+"\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp,outdir/"calls.jsonl")
    atomic_json(outdir/"status.json",status(db_path,label_config))
    db.close()
