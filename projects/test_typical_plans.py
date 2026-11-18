import json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from django.test import TestCase,override_settings
from django.conf import settings
from projects.models import PlanAnalysis
from projects.demo_samples import typical_plans
from core.openai_client import safe_error_code,ALLOWED_MODELS
from accounts.ai_explanation import minimized_snapshot

@override_settings(ESEPTEP_DEMO_MODE=True,PLAN_AI_ENABLED=False,OPENAI_LIVE_CONFIRMED=False)
class TypicalPlansTests(TestCase):
 def test_catalog_has_no_predetermined_bathroom_answer(self):
  r=self.client.get('/projects/upload/')
  self.assertContains(r,'Выбрать типовую планировку');self.assertNotContains(r,'Начните с готового примера');self.assertNotContains(r,'ванная 4,8');self.assertNotContains(r,'value="unreadable"')
  self.assertEqual(len(typical_plans()),3)
 def test_selection_never_calls_api_and_preview_private(self):
  with patch('projects.plan_analysis.responses_create') as api:
   for item in typical_plans():
    r=self.client.post('/projects/examples/select/',{'sample':item['key']});self.assertEqual(r.status_code,302)
    view=self.client.get(r.url);self.assertContains(view,'Проанализировать план');self.assertNotContains(view,'Что прочитал ИИ')
   self.assertFalse(api.called);self.assertEqual(PlanAnalysis.objects.count(),0)
 def test_ground_truth_is_own_and_consistent(self):
  data=json.loads(Path(settings.BASE_DIR,'tests/fixtures/plans/typical-manifest.json').read_text(encoding='utf8'))
  for item in data:
   self.assertAlmostEqual(sum(r['area'] for r in item['ground_truth']),item['area'])
   self.assertGreaterEqual(sum(r['kind']=='bathroom' for r in item['ground_truth']),1)
   self.assertTrue(Path(settings.BASE_DIR,'tests/fixtures/plans',item['pdf']).exists())
   self.assertNotIn('ground_truth',typical_plans()[0])
 def test_provider_errors_are_whitelisted_and_null_quote_safe(self):
  self.assertIn('gpt-6.1-sol',ALLOWED_MODELS)
  self.assertEqual(safe_error_code(SimpleNamespace(status_code=401,code='invalid_api_key')),'invalid_api_key')
  self.assertEqual(safe_error_code(SimpleNamespace(status_code=400,code='secret-looking-arbitrary')),'http_400')
  c=SimpleNamespace(result_data={'admin_quote':None,'materials':[{'title':'test','reference_price':2,'reference_total':6}]},calculator_slug='plitka-keramogranit',grand_total=6)
  result=minimized_snapshot(c);self.assertEqual(result['materials'][0]['reference_total'],6)

 @override_settings(OPENAI_API_KEY='synthetic-test-key',OPENAI_MODEL='gpt-6.1-sol',OPENAI_LIVE_CONFIRMED=True,PLAN_AI_ENABLED=True,OPENAI_PILOT_MAX_RESERVED_CENTS=20)
 def test_single_call_ceiling_and_replay(self):
  from projects.models import ProjectUpload,PlanAnalysisBudget
  from projects.plan_analysis import analyze
  a=ProjectUpload.objects.create(file='synthetic-a.png',guest_session_key='qa')
  b=ProjectUpload.objects.create(file='synthetic-b.png',guest_session_key='qa')
  response={'status':'completed','output':[{'content':[{'type':'output_text','text':'{"rooms":[]}'}]}]}
  with patch('projects.plan_analysis.pages',side_effect=[(b'a',[(b'image','')]),(b'b',[(b'image','')]),(b'a',[(b'image','')])]),patch('projects.plan_analysis.responses_create',return_value=response) as api:
   self.assertEqual(analyze(a).status,'completed')
   self.assertEqual(analyze(b).error_code,'budget_limit')
   self.assertEqual(analyze(a).status,'completed')
   self.assertEqual(api.call_count,1)
  self.assertEqual(PlanAnalysisBudget.objects.get(pk=1).reserved_cents,20)
