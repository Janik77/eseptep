import tempfile
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from accounts.models import UserProfile, ClientProject, SupplierProfile
from calculators.models import PriceBook, MaterialPrice
from projects.models import PlanAnalysisBudget, ProjectUpload, PlanConfirmation

@override_settings(ESEPTEP_DEMO_MODE=True,PRODUCTION=False)
class MeetingDemoTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings=override_settings(PRIVATE_MEDIA_ROOT=self.temp.name)
        settings.enable();self.addCleanup(settings.disable)

    def seed(self, **kwargs):
        call_command('seed_meeting_demo',confirm_isolated=True,verbosity=0,**kwargs)

    def test_seed_repeat_preserves_accounts_prices_and_budget(self):
        self.seed()
        client=User.objects.get(username='demo-client@example.test')
        password=client.password
        PlanAnalysisBudget.objects.create(pk=1,reserved_cents=80)
        first=(User.objects.count(),UserProfile.objects.count(),ClientProject.objects.count(),SupplierProfile.objects.count(),MaterialPrice.objects.count())
        self.seed()
        self.assertEqual(first,(User.objects.count(),UserProfile.objects.count(),ClientProject.objects.count(),SupplierProfile.objects.count(),MaterialPrice.objects.count()))
        self.assertEqual(User.objects.get(pk=client.pk).password,password)
        self.assertEqual(PlanAnalysisBudget.objects.get(pk=1).reserved_cents,80)
        self.seed(price_version='v2')
        self.assertEqual(PriceBook.objects.get(is_active=True).version,'meeting-demo-v2')
        self.seed()
        self.assertEqual(PriceBook.objects.get(is_active=True).version,'meeting-demo-v2')

    def test_seed_refuses_foreign_database(self):
        User.objects.create_user('real-customer')
        with self.assertRaises(CommandError):self.seed()
        self.assertEqual(User.objects.count(),1)

    def test_sample_is_repeatable_private_and_never_calls_ai(self):
        from unittest.mock import patch
        self.seed();self.client.force_login(User.objects.get(username='demo-client@example.test'))
        with patch('projects.plan_analysis.analyze') as api:
            first=self.client.post('/projects/examples/select/',{'sample':'clear'})
            second=self.client.post('/projects/examples/select/',{'sample':'clear'})
            self.assertEqual(first.url,second.url)
            self.assertEqual(ProjectUpload.objects.count(),1)
            api.assert_not_called()
        self.assertContains(self.client.get(first.url),'От плана к смете')
        self.assertFalse(PlanAnalysisBudget.objects.exists())

    def test_last_manual_confirmation_survives_return(self):
        self.seed();self.client.force_login(User.objects.get(username='demo-client@example.test'))
        response=self.client.post('/projects/examples/select/',{'sample':'unreadable'})
        self.client.post(response.url,{'action':'confirm','name':'Ванная','area':'36,5'})
        page=self.client.get(response.url)
        self.assertContains(page,'36.50')
        self.assertEqual(PlanConfirmation.objects.get().snapshot['area'],'36.50')

    @override_settings(ESEPTEP_DEMO_MODE=False)
    def test_demo_off(self):
        with self.assertRaises(CommandError):self.seed()
        self.assertEqual(self.client.post('/projects/examples/select/',{'sample':'clear'}).status_code,404)
