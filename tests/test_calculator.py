import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('calculator',Path(__file__).resolve().parents[1]/'cost/calculator.py')
calc=importlib.util.module_from_spec(spec);spec.loader.exec_module(calc)

class CalculatorTests(unittest.TestCase):
    def test_editable_limits_preserve_measured_usage_and_no_invented_speedup(self):
        a=calc.calculate(*self.data())
        b=calc.calculate(*self.data(),max_workers=2,output_token_cap=512)
        self.assertEqual(a['measurements'],b['measurements']);self.assertEqual(a['api_total_usd'],b['api_total_usd'])
        self.assertEqual(a['scenarios'][0]['seconds_estimate'],b['scenarios'][0]['seconds_estimate'])
        self.assertEqual(b['worker_limit'],2);self.assertEqual(b['output_token_cap_local'],512)
    def test_unpriced_fallback_remains_unknown_and_priced_assumption_affects_only_projection(self):
        a=calc.calculate(*self.data(),fallback_fraction=.01)
        self.assertIsNone(a['scenarios'][0]['api_usd']);self.assertIsNone(a['scenarios'][0]['seconds_estimate'])
        b=calc.calculate(*self.data(),fallback_fraction=.01,fallback_usd_per_review=.001)
        self.assertIsNotNone(b['scenarios'][0]['api_usd']);self.assertEqual(a['api_total_usd'],b['api_total_usd'])
        self.assertEqual(b['execution_fallback_limit'],0)
    def data(self):
        run={'temperature':'cold','unique_texts':100,'input_rows':100,'completed':100,'model_requests':2,'wall_seconds':2,'stage_seconds':{'enrich':1,'verify':.1,'group':.3,'memo':.4,'rank':.0001}}
        calls=[{'request_id':'e','role':'enrich','provider':'typesafe','model':'jev-1.13.0','input_tokens':20000,'output_tokens':1000,'review_ids':['a']},
               {'request_id':'v','role':'verify','provider':'typesafe','model':'jev-1.13.0','input_tokens':1000,'output_tokens':100,'review_ids':['a']*10}]
        prices=[{'provider':'typesafe','model':'jev-1.13.0','unit':'input_token','usd_per_unit':'0.000000042'}, {'provider':'typesafe','model':'jev-1.13.0','unit':'output_token','usd_per_unit':'0'}]
        return [run],calls,prices
    def test_doubled_api_rates_preserve_measurements_and_time(self):
        runs,calls,rates=self.data();a=calc.calculate(runs,calls,rates)
        doubled=[dict(r,usd_per_unit=str(float(r['usd_per_unit'])*2)) for r in rates];b=calc.calculate(runs,calls,doubled)
        self.assertAlmostEqual(float(b['api_total_usd']),2*float(a['api_total_usd']))
        self.assertEqual(a['measurements'],b['measurements'])
        self.assertEqual(a['scenarios'][0]['seconds_estimate'],b['scenarios'][0]['seconds_estimate'])
        self.assertIsNone(b['local_compute_usd'])
    def test_volume_changes_only_projections(self):
        data=self.data();a=calc.calculate(*data,unique=1000);b=calc.calculate(*data,unique=2000)
        self.assertEqual(a['measurements'],b['measurements']);self.assertEqual(a['api_total_usd'],b['api_total_usd'])
        self.assertGreater(float(b['scenarios'][0]['api_usd']),float(a['scenarios'][0]['api_usd']))
    def test_unknown_paid_usage_stays_unknown(self):
        runs,calls,rates=self.data();calls[0]['input_tokens']=None
        result=calc.calculate(runs,calls,rates)
        self.assertIsNone(result['api_total_usd']);self.assertIsNone(result['scenarios'][0]['api_usd'])
    def test_local_failure_does_not_imply_paid_api_bill(self):
        runs,calls,rates=self.data();calls.append({'request_id':'local','role':'group','provider':'local_llamacpp','input_tokens':None,'output_tokens':None})
        result=calc.calculate(runs,calls,rates)
        self.assertIsNotNone(result['api_total_usd']);self.assertIsNone(result['local_compute_usd'])
    def test_prior_consumption_and_checkpoints_affect_budget_not_measured_usage(self):
        data=self.data();a=calc.calculate(*data,budget=1,unique=1000,nonempty=2000)
        b=calc.calculate(*data,budget=1,unique=1000,nonempty=2000,prior_spend=.5,checkpoint_allowance=.5)
        self.assertEqual(a['api_total_usd'],b['api_total_usd'])
        self.assertFalse(a['scenarios'][0]['exceeds_api_budget'])
        self.assertTrue(b['scenarios'][0]['exceeds_api_budget'])
    def test_incremental_checkpoint_projects_from_new_work_not_reused_rows(self):
        runs,calls,rates=self.data();baseline=calc.calculate(runs,calls,rates)
        runs[0].pop('temperature');runs[0].update(state='completed',input_rows=500,completed=500,unique_texts=479,new_unique_enrichment_work=100)
        checkpoint=calc.calculate(runs,calls,rates)
        self.assertEqual(checkpoint['scenarios'][0]['api_usd'],baseline['scenarios'][0]['api_usd'])
        self.assertEqual(checkpoint['measured_enrichment_work'],100)
    def test_completed_credit_reduces_future_work_without_changing_measurements(self):
        data=self.data();a=calc.calculate(*data,unique=1000,nonempty=2000)
        b=calc.calculate(*data,unique=1000,nonempty=2000,completed_unique=100)
        self.assertEqual(a['measurements'],b['measurements']);self.assertEqual(a['api_total_usd'],b['api_total_usd'])
        self.assertEqual(b['scenarios'][0]['unique_enrichment_work'],900)
        self.assertLess(float(b['scenarios'][0]['api_usd']),float(a['scenarios'][0]['api_usd']))
        self.assertEqual(a['scenarios'][1],b['scenarios'][1])
        with self.assertRaises(ValueError):calc.calculate(*data,completed_unique=484190)
