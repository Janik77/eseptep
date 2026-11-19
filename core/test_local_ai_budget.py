import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .local_ai_budget import initialize,status,reserve,reconcile,usage_bound,BudgetError

class LocalBudgetTests(SimpleTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.sqlite3'
        initialize(self.path,3,{'synthetic':'test'})
        self.payload={'model':'gpt-6.1-sol','service_tier':'default','max_output_tokens':1800,'input':'test'}
        self.response={'status':'completed','model':'gpt-6.1-sol','service_tier':'default','id':'resp_synthetic','usage':{'input_tokens':2547,'output_tokens':258,'total_tokens':2805}}
    def test_sequential_qa_and_owner_fit_without_releasing_history(self):
        self.assertEqual(status(self.path)['accounted_cents'],203)
        one=reserve(self.path,self.payload)
        self.assertEqual(status(self.path)['remaining_cents'],197)
        with self.assertRaises(BudgetError):reserve(self.path,{**self.payload,'input':'second'})
        reconcile(self.path,one,self.response);reconcile(self.path,one,self.response)
        self.assertEqual(status(self.path)['accounted_cents'],206)
        reserve(self.path,{**self.payload,'input':'owner'})
        self.assertEqual(status(self.path)['accounted_cents'],806)
    def test_timeout_missing_usage_and_duplicate_never_refund(self):
        ticket=reserve(self.path,self.payload)
        for data in ({}, {**self.response,'usage':{'input_tokens':-1,'output_tokens':1,'total_tokens':0}}):
            with self.assertRaises(BudgetError):reconcile(self.path,ticket,data)
        with self.assertRaises(BudgetError):reserve(self.path,self.payload)
        self.assertEqual(status(self.path)['accounted_cents'],803)
    def test_concurrent_requests_only_one_context_hold(self):
        def attempt(n):
            try:return reserve(self.path,{**self.payload,'input':str(n)})
            except BudgetError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(attempt,[1,2]))
        self.assertEqual(sum(x is not None for x in r),1)
        self.assertEqual(status(self.path)['accounted_cents'],803)
    def test_upper_bound_and_invalid_model(self):
        self.assertEqual(usage_bound({'status':'completed','id':'resp_test','usage':{'input_tokens':1050000,'output_tokens':1800,'total_tokens':1051800}}),581)
        with self.assertRaises(BudgetError):reserve(self.path,{**self.payload,'model':'other'})
    @override_settings(OPENAI_API_KEY='mock-only',OPENAI_LIVE_CONFIRMED=True,OPENAI_MODEL='gpt-6.1-sol',OPENAI_MAX_OUTPUT_TOKENS=1800,OPENAI_TIMEOUT_SECONDS=45)
    @patch('core.openai_client.OpenAI')
    def test_sdk_charges_guard_and_settles_once_no_retry(self,sdk):
        from .openai_client import responses_create
        sdk.return_value.__enter__.return_value.responses.create.return_value.model_dump.return_value=self.response
        with override_settings(LOCAL_AI_BUDGET_PATH=str(self.path)):
            responses_create(input='test',max_output_tokens=1800)
            with self.assertRaises(BudgetError):responses_create(input='test',max_output_tokens=1800)
        self.assertEqual(sdk.call_count,1)
        self.assertEqual(sdk.call_args.kwargs['max_retries'],0)
        self.assertEqual(status(self.path)['accounted_cents'],206)
