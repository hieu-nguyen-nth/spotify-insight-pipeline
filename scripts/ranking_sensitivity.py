#!/usr/bin/env python3
"""Offline needs_review sensitivity; never changes the required baseline or labels."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def calculate(path):
    digest = hashlib.sha256()
    counts = Counter()
    scores = Counter()
    unflagged_counts = Counter()
    unflagged_scores = Counter()
    seen = set()
    flagged = completed = flagged_complaints = 0
    with Path(path).open('rb') as source:
        for line in source:
            digest.update(line)
            if not line.strip():
                continue
            record = json.loads(line)
            rid = record['review_id']
            if rid in seen:
                raise ValueError('Duplicate review ID: ' + rid)
            seen.add(rid)
            if record['status'] == 'quarantined':
                continue
            if record['status'] != 'completed':
                raise ValueError('Expected completed or quarantined records.')
            flag = record['needs_review']
            severity = record['severity']
            if type(flag) is not bool or type(severity) is not int or not 1 <= severity <= 5:
                raise ValueError('Invalid needs_review flag or severity.')
            completed += 1
            flagged += flag
            if record['intent'] not in ('complaint', 'cancellation'):
                continue
            issue = 'issue_' + record['topic']
            counts[issue] += 1
            scores[issue] += severity
            flagged_complaints += flag
            if not flag:
                unflagged_counts[issue] += 1
                unflagged_scores[issue] += severity

    def ordered(count, score):
        return [dict(rank=index, issue_id=issue, complaint_count=count[issue],
                     severity_sum=value, priority_score=value)
                for index, (issue, value) in enumerate(
                    sorted(score.items(), key=lambda item: (-item[1], item[0])), 1)]

    return {
        'version': 'needs-review-sensitivity-v1',
        'input_sha256': digest.hexdigest(),
        'completed_records': completed,
        'needs_review_records': flagged,
        'complaint_cancellation_records': sum(counts.values()),
        'flagged_complaint_cancellation_records': flagged_complaints,
        'baseline': ordered(counts, scores),
        'unflagged_diagnostic': ordered(unflagged_counts, unflagged_scores),
        'diagnostic_policy': 'Exclude needs_review=true only in this separate sensitivity scenario.',
        'limitations': 'Exclusion introduces its own selection bias. This is neither a corrected ranking nor a population or accuracy estimate.',
        'original_labels_and_baseline_changed': False,
        'new_model_calls': 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', type=Path, default=Path('grading/records.jsonl'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = calculate(args.records)
    raw = json.dumps(result, indent=2) + '\n'
    if args.out:
        if args.out.resolve() == args.records.resolve():
            parser.error('Output must not overwrite input records.')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(raw)
    print(raw, end='')


if __name__ == '__main__':
    main()
