"""Synthetic audit fixtures: reject misleading quote/membership/baseline evidence."""
import csv
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('saved_audit', ROOT / 'scripts/audit_saved_evidence.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SavedEvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('human_labels_as_evaluated.csv', 'records.json', 'evaluation.json', 'follow_up_case_notes.json'):
            destination = self.root / 'reports/golden50' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'reports/golden50' / name, destination)
        for name in ('dashboard.json', 'recommendations.json'):
            destination = self.root / 'reports/completed_subset' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'reports/completed_subset' / name, destination)
        original = self.root / 'reports/submission_review/dashboard_before_result_revision.json'
        original.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'reports/submission_review/dashboard_before_result_revision.json', original)
        dashboard = json.loads((self.root / 'reports/completed_subset/dashboard.json').read_text())
        self.records = self.root / 'records.jsonl'
        self.rows = []
        membership = []
        for issue in dashboard['issue_evidence'][:3]:
            for example in issue['evidence']:
                membership.append(dict(issue_id=issue['issue_id'], review_id=example['review_id']))
                self.rows.append(dict(review_id=example['review_id'], status='completed', intent='complaint',
                                      topic=issue['issue_id'].removeprefix('issue_'), evidence_quote=example['quote'],
                                      source_sha256='a' * 64, severity=5, needs_review=True))
        with (self.root / 'reports/completed_subset/membership.csv').open('w', newline='') as source:
            writer = csv.DictWriter(source, fieldnames=['issue_id', 'review_id'])
            writer.writeheader()
            writer.writerows(membership)
        self.save_records()

    def save_records(self):
        raw = ''.join(json.dumps(row) + '\n' for row in self.rows).encode()
        self.records.write_bytes(raw)
        (self.root / 'reports/completed_subset/ranking_sensitivity.json').write_text(
            json.dumps({'input_sha256': hashlib.sha256(raw).hexdigest()}))

    def test_valid_evidence_keeps_original_agreement_and_no_adjudication(self):
        cases, evidence, checks = audit.audit(self.root, self.records)
        self.assertEqual(len(evidence), 9)
        self.assertEqual(cases['original_topic_agreement'], .68)
        self.assertTrue(all(row['student_case_decision'] is None for row in cases['topic_disagreements']))
        self.assertEqual(checks['new_model_calls'], 0)

    def test_quote_absent_from_source_is_rejected(self):
        self.rows[0]['evidence_quote'] = 'A different source text.'
        self.save_records()
        with self.assertRaisesRegex(ValueError, 'quote or issue provenance'):
            audit.audit(self.root, self.records)

    def test_missing_issue_membership_is_rejected(self):
        (self.root / 'reports/completed_subset/membership.csv').write_text('issue_id,review_id\n')
        with self.assertRaisesRegex(ValueError, 'absent from its issue membership'):
            audit.audit(self.root, self.records)

    def test_editorial_update_cannot_change_frozen_priority(self):
        path = self.root / 'reports/completed_subset/dashboard.json'
        dashboard = json.loads(path.read_text())
        dashboard['ranking'][0]['priority_score'] += 1
        path.write_text(json.dumps(dashboard))
        with self.assertRaisesRegex(ValueError, 'Frozen dashboard baseline changed: ranking'):
            audit.audit(self.root, self.records)
