import importlib.util
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deployed_dashboard',Path(__file__).resolve().parents[1]/'backend/api/dashboard.py')
dashboard=importlib.util.module_from_spec(spec);spec.loader.exec_module(dashboard)

class BackendTests(unittest.TestCase):
    def request(self,key):
        seen=[]
        def response(req,timeout):
            seen.append(req);return io.BytesIO(json.dumps([{'value':{'saved':'artifact'}}]).encode())
        with patch.dict(os.environ,{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_PUBLISHABLE_KEY':key,'SPOTIFY_DATASET_ID':'1'}),patch.object(dashboard.urllib.request,'urlopen',response):
            self.assertEqual(dashboard.dashboard(),{'saved':'artifact'})
        return seen[0]
    def test_modern_publishable_key_is_not_sent_as_jwt(self):
        req=self.request('sb_publishable_test');self.assertEqual(req.get_header('Apikey'),'sb_publishable_test');self.assertIsNone(req.get_header('Authorization'))
    def test_legacy_anon_key_remains_supported(self):
        req=self.request('eyJ_test');self.assertEqual(req.get_header('Authorization'),'Bearer eyJ_test')
    def test_dataset_id_cannot_inject_a_query(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_PUBLISHABLE_KEY':'sb_publishable_test','SPOTIFY_DATASET_ID':'1&select=*'}),patch.object(dashboard.urllib.request,'urlopen') as call:
            with self.assertRaises(ValueError):dashboard.dashboard()
            call.assert_not_called()
