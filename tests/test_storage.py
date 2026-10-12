import json
import tempfile
import unittest
from pathlib import Path
from spotify_pipeline import storage,lean,analysis
from spotify_pipeline.core import atomic_json

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name);self.db_path=self.out/'control.sqlite'
        source={'review_id':'original-id','source_sha256':'source-hash','review_text':'Cannot play','text_sha256':'text-hash'}
        record={**source,'status':'completed','topic':'playback','intent':'complaint','severity':4,'sentiment':-.5,
                'needs_review':False,'entities':[],'evidence_quote':'Cannot play','label_config':'frozen'}
        db=lean.control(self.db_path);lean.put(db,'test','frozen',source,{'record':record});db.commit();db.close()
        atomic_json(self.out/'records.json',[record])
        atomic_json(self.out/'enrichment_run.json',{'scope':'test','label_config':'frozen','stop_reason':'completed','nonempty_reviews':1})
        atomic_json(self.out/'ingestion_report.json',{'profile':{'file_sha256':'file-hash'}})
        members,ranked,claims=analysis.ranking([record])
        for filename,rows in [('membership.csv',members),('ranking.csv',ranked),('claims.csv',claims)]:
            analysis.csv_save(self.out/filename,rows,list(rows[0]))
        self.pack={'issues':[{**ranked[0],'evidence':[{'review_id':'original-id','quote':'Cannot play'}]}]}
        atomic_json(self.out/'aggregate_evidence.json',self.pack)
        atomic_json(self.out/'recommendations.json',[{'issue_id':'issue_playback','action':'Investigate playback','reason':'A review reports blocked playback.',
                  'claim_ids':['issue_playback_complaint_count'],'evidence_review_ids':['original-id']}])
        (self.out/'memo.md').write_text('Saved reviewed memo')
    def tearDown(self):self.tmp.cleanup()
    def test_checked_analysis_is_persisted_without_model_calls(self):
        result=storage.save(self.out,self.db_path)
        self.assertEqual(result['new_model_calls'],0);self.assertEqual(result['stored_membership_rows'],1)
        db=lean.control(self.db_path)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM stored_analysis').fetchone()[0],6)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],0);db.close()
    def test_planted_pack_metric_cannot_overwrite_accepted_database_artifact(self):
        storage.save(self.out,self.db_path);db=lean.control(self.db_path)
        original=db.execute("SELECT sha256 FROM stored_analysis WHERE artifact_kind='dashboard'").fetchone()[0];db.close()
        self.pack['issues'][0]['severity_sum']=999;atomic_json(self.out/'aggregate_evidence.json',self.pack)
        with self.assertRaises(ValueError):storage.save(self.out,self.db_path)
        db=lean.control(self.db_path)
        self.assertEqual(db.execute("SELECT sha256 FROM stored_analysis WHERE artifact_kind='dashboard'").fetchone()[0],original);db.close()
