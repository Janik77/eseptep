from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from core.openai_client import AIConfigurationError
from projects.models import PlanAnalysisBudget
from .models import Calculation, ClientProject, UserProfile
from .ai_explanation import explain

@override_settings(ESTIMATE_AI_ENABLED=True,OPENAI_LIVE_CONFIRMED=True,OPENAI_API_KEY='unit-placeholder',PRODUCTION=False)
class ExplanationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('explanation-owner')
        UserProfile.objects.create(user=self.user,role='client')
        project=ClientProject.objects.create(user=self.user,title='PRIVATE PROJECT',city='PRIVATE CITY',area_m2=36.5,rooms=2,repair_segment='comfort')
        self.calc=Calculation.objects.create(project=project,calculator_slug='plitka-keramogranit',area_m2=4.8,rooms=1,thickness=1,segment='comfort',grand_total=5000,
            result_data={'input':{'area':'4.8','zone':'floor','private_name':'PRIVATE NAME'},'materials':[{'title':'Tile','quantity':6,'unit':'m2'}], 'plan_source':{'name':'PRIVATE ROOM'}})
        self.client.force_login(self.user)
        self.url=f'/accounts/calculations/{self.calc.pk}/explain/'

    @patch('accounts.ai_explanation.responses_create')
    def test_repeat_cache_snapshot_privacy(self,api):
        api.return_value={'status':'completed','usage':{'input_tokens':20},'output':[{'content':[{'type':'output_text','text':'<script>unsafe</script> explanation'}]}]}
        first=self.client.post(self.url);self.assertEqual(first.status_code,302)
        self.client.post(self.url);self.client.get(first.url)
        self.assertEqual(api.call_count,1)
        payload=api.call_args.kwargs['input'];self.assertNotIn('PRIVATE',payload)
        self.calc.refresh_from_db();self.assertEqual(self.calc.grand_total,5000)
        self.assertEqual(PlanAnalysisBudget.objects.get(pk=1).reserved_cents,20)
        self.assertContains(self.client.get(first.url),'&lt;script&gt;')

    @patch('accounts.ai_explanation.responses_create',side_effect=TimeoutError('SECRET SHOULD NOT LEAK'))
    def test_unknown_not_retried_or_refunded(self,api):
        self.client.post(self.url);self.client.post(self.url)
        self.assertEqual(api.call_count,1)
        self.assertEqual(self.calc.ai_explanations.get().status,'unknown')
        self.assertEqual(PlanAnalysisBudget.objects.get(pk=1).reserved_cents,20)

    @patch('accounts.ai_explanation.responses_create')
    def test_shared_budget_and_owner_only(self,api):
        PlanAnalysisBudget.objects.create(pk=1,reserved_cents=200)
        self.client.post(self.url);api.assert_not_called()
        self.assertEqual(self.calc.ai_explanations.get().error_code,'budget_limit')
        other=User.objects.create_user('other');self.client.force_login(other)
        self.assertEqual(self.client.post(self.url).status_code,404)

    @patch('accounts.ai_explanation.responses_create')
    @override_settings(OPENAI_LIVE_CONFIRMED=False)
    def test_key_alone_cannot_trigger_request(self,api):
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.client.post(self.url);api.assert_not_called()
        self.assertFalse(self.calc.ai_explanations.exists())
        self.assertFalse(PlanAnalysisBudget.objects.exists())
