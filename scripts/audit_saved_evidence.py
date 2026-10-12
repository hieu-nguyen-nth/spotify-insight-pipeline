#!/usr/bin/env python3
"""Audit saved evidence and golden errors offline, without inference or relabeling."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, records):
    golden = root / 'reports/golden50'
    with (golden / 'human_labels_as_evaluated.csv').open(newline='') as source:
        human = {r['review_id']: r for r in csv.DictReader(source)}
    predictions = json.loads((golden / 'records.json').read_text())
    ids = [r['review_id'] for r in predictions]
    if len(ids) != 50 or len(set(ids)) != 50 or set(ids) != set(human):
        raise ValueError('Golden IDs must match all 50 original human labels.')
    notes = json.loads((golden / 'follow_up_case_notes.json').read_text())
    topics, sentiment = [], []
    for record in predictions:
        rid = record['review_id']
        label = human[rid]
        text = label['review_text']
        if hashlib.sha256(text.encode()).hexdigest() != record['text_sha256']:
            raise ValueError('Golden source text hash mismatch: ' + rid)
        if label['topic'] != record['topic']:
            topics.append(dict(review_id=rid, review_text=text,
                               original_human_topic=label['topic'], model_topic=record['topic'],
                               assistant_observation=notes['topic'][rid],
                               student_case_decision=None))
        sentiment.append(dict(review_id=rid, review_text=text,
                              original_human_sentiment=float(label['sentiment']),
                              saved_vader_sentiment=record['sentiment'],
                              absolute_error=round(abs(float(label['sentiment']) - record['sentiment']), 6)))
    sentiment.sort(key=lambda row: (-row['absolute_error'], row['review_id']))
    for row in sentiment[:10]:
        row['assistant_observation'] = notes['sentiment'][row['review_id']]
    case_review = dict(
        reviewer='Codex assistant inspection of saved texts; no new human labels or model calls',
        selection='All topic disagreements; ten largest sentiment absolute errors, ties by review ID',
        human_labels_sha256=sha(golden / 'human_labels_as_evaluated.csv'),
        predictions_sha256=sha(golden / 'records.json'),
        original_evaluation_sha256=sha(golden / 'evaluation.json'),
        topic_disagreements=sorted(topics, key=lambda row: row['review_id']),
        largest_sentiment_errors=sentiment[:10],
        sentiment_mae=round(sum(row['absolute_error'] for row in sentiment) / len(sentiment), 6),
        original_topic_agreement=(50 - len(topics)) / 50,
        student_statement='Student accepts the model topic in most disputed cases; exact case decisions not supplied.',
        student_statement_source='student_review_decision.json',
        labels_predictions_prompts_modified=False, new_model_calls=0)

    subset = root / 'reports/completed_subset'
    recommendations = json.loads((subset / 'recommendations.json').read_text())
    dashboard = json.loads((subset / 'dashboard.json').read_text())
    original = json.loads((root / 'reports/submission_review/dashboard_before_result_revision.json').read_text())
    for key in ('dataset', 'overview', 'ranking', 'claims', 'issue_evidence', 'verification'):
        if dashboard[key] != original[key]:
            raise ValueError('Frozen dashboard baseline changed: ' + key)
    if dashboard['recommendations'] != recommendations:
        raise ValueError('Dashboard and recommendation artifact differ.')
    required = {(r['issue_id'], rid) for r in recommendations for rid in r['evidence_review_ids']}
    with (subset / 'membership.csv').open(newline='') as source:
        membership = {(r['issue_id'], r['review_id']) for r in csv.DictReader(source)}
    if not required <= membership:
        raise ValueError('A cited review is absent from its issue membership.')
    wanted = {rid for _, rid in required}
    found, seen = {}, set()
    digest = hashlib.sha256()
    with records.open('rb') as source:
        for line in source:
            digest.update(line)
            if not line.strip():
                continue
            record = json.loads(line)
            rid = record['review_id']
            if rid in seen:
                raise ValueError('Duplicate saved review ID: ' + rid)
            seen.add(rid)
            if rid in wanted:
                found[rid] = record
    if set(found) != wanted:
        raise ValueError('A cited review is missing from saved records.')
    sensitivity = json.loads((subset / 'ranking_sensitivity.json').read_text())
    if digest.hexdigest() != sensitivity['input_sha256']:
        raise ValueError('Saved records differ from the frozen sensitivity input.')
    quotes = {(i['issue_id'], e['review_id']): e['quote']
              for i in dashboard['issue_evidence'] for e in i['evidence']}
    evidence = []
    for issue, rid in sorted(required):
        record = found[rid]
        quote = quotes[(issue, rid)]
        if (record['status'] != 'completed' or record['intent'] not in ('complaint', 'cancellation')
                or 'issue_' + record['topic'] != issue or quote not in record['evidence_quote']):
            raise ValueError('Cited quote or issue provenance mismatch: ' + rid)
        evidence.append(dict(issue_id=issue, review_id=rid, severity=record['severity'],
                             needs_review=record['needs_review'], source_sha256=record['source_sha256'],
                             quote=quote, membership_verified=True))
    checks = dict(saved_records_sha256=digest.hexdigest(), cited_reviews=len(evidence),
                  issue_membership_and_quote_checks='pass', golden_source_hash_checks='pass',
                  baseline_unchanged=True, labels_modified=False, new_model_calls=0)
    return case_review, evidence, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', type=Path, default=Path('grading/records.jsonl'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for name in ('golden_case_review.json', 'recommendation_evidence.csv', 'checks.json'):
        if (args.out / name).resolve() == args.records.resolve():
            parser.error('Output must not overwrite input records.')
    cases, evidence, checks = audit(root, args.records)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in [('golden_case_review.json', cases), ('checks.json', checks)]:
        (args.out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    with (args.out / 'recommendation_evidence.csv').open('w', newline='') as destination:
        rows = [{key: value for key, value in row.items() if key != 'quote'}
                | {'quote_json': json.dumps(row['quote'], ensure_ascii=False)} for row in evidence]
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
