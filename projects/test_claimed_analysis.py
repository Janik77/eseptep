import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from .models import PlanAnalysis, PlanAnalysisBudget
from .test_plan_input_gate import model, png, room


@override_settings(PLAN_AI_ENABLED=True, OPENAI_LIVE_CONFIRMED=True,
                   OPENAI_API_KEY='unit-test-placeholder', OPENAI_MODEL='gpt-6.1-sol',
                   PRODUCTION=False)
class ClaimedAnalysisTests(TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        override = override_settings(PRIVATE_MEDIA_ROOT=media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.account = User.objects.create_user('buyer@example.test', password='Fixture-only-123!')
        UserProfile.objects.create(user=self.account, role='client', city='Шымкент')
        self.raw = png('synthetic-original')

    def upload(self, client, name='floor.png', raw=None, action='upload_calculate'):
        response = client.post(reverse('projects:upload'), {
            'action': action, 'file': SimpleUploadedFile(name, self.raw if raw is None else raw),
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        return response.context['upload'], response.context.get('estimate')

    def claim(self, guest, estimate):
        result = guest.post(reverse('accounts:whole_guest_save', args=[estimate.pk]), {'next': 'save'})
        self.assertRedirects(result, reverse('accounts:login'))
        result = guest.post(reverse('accounts:login'), {
            'username': self.account.username, 'password': 'Fixture-only-123!',
        }, follow=True)
        self.assertEqual(result.resolver_match.url_name, 'whole_saved')

    @patch('projects.plan_analysis.responses_create')
    def test_renamed_after_real_guest_claim_reuses_analysis_not_manual_spaces(self, api):
        api.return_value = model(rooms=[room(area=8)])
        upload, initial = self.upload(self.client)
        self.client.post(reverse('projects:whole_plan', args=[upload.pk]), {
            'action': 'update', 'estimate_id': initial.pk, 'room': 0, 'area': '9.50', 'name': 'Edited room',
        })
        url = reverse('projects:whole_plan', args=[upload.pk])
        edited = self.client.get(url).context['estimate']
        self.claim(self.client, edited)
        api.return_value = model(rooms=[room(area=99)])
        with override_settings(PLAN_AI_ENABLED=False, OPENAI_API_KEY=''):
            repeated, estimate = self.upload(self.client, 'renamed.png')
        self.assertNotEqual(upload.pk, repeated.pk)
        self.assertEqual(estimate.snapshot['known_area'], '8.00')
        self.assertEqual(estimate.snapshot['analysis_id'], initial.snapshot['analysis_id'])
        self.assertEqual(self.client.get(url).context['estimate'].snapshot['known_area'], '9.50')
        api.assert_called_once()
        self.assertEqual(PlanAnalysis.objects.count(), 1)
        self.assertEqual(PlanAnalysisBudget.objects.get().reserved_cents, 20)


    @patch('projects.plan_analysis.responses_create')
    def test_only_explicit_claim_into_that_account_can_reuse(self, api):
        guest = self.client
        api.return_value = model(rooms=[room(area=8)])
        first, original = self.upload(guest)
        other_user = User.objects.create_user('other@example.test')
        other = Client()
        other.force_login(other_user)
        self.assertEqual(other.get(reverse('projects:whole_plan', args=[first.pk])).status_code, 404)
        api.return_value = model(rooms=[room(area=18)])
        _, unclaimed = self.upload(other, 'other.png')
        self.assertEqual(unclaimed.snapshot['known_area'], '18.00')
        self.claim(guest, original)
        fresh_guest = Client()
        api.return_value = model(rooms=[room(area=28)])
        _, guest_result = self.upload(fresh_guest, 'new-guest.png')
        self.assertEqual(guest_result.snapshot['known_area'], '28.00')
        _, other_again = self.upload(other, 'other-2.png')
        self.assertEqual(other_again.snapshot['known_area'], '18.00')
        _, buyer = self.upload(guest, 'buyer.png')
        self.assertEqual(buyer.snapshot['known_area'], '8.00')
        self.assertEqual(api.call_count, 3)
        self.assertEqual(PlanAnalysisBudget.objects.get().reserved_cents, 60)

    @patch('projects.plan_analysis.responses_create')
    def test_distinct_source_bytes_with_same_normalized_pixels_cannot_reuse(self, api):
        api.return_value = model(rooms=[room(area=8)])
        _, initial = self.upload(self.client)
        self.claim(self.client, initial)
        api.return_value = model(rooms=[room(area=13)])
        _, estimate = self.upload(self.client, raw=png('different original metadata'))
        self.assertEqual(estimate.snapshot['known_area'], '13.00')
        self.assertEqual(api.call_count, 2)

    @patch('projects.plan_analysis.responses_create')
    def test_claiming_renamed_guest_copy_does_not_expose_unclaimed_original(self, api):
        api.return_value = model(rooms=[room(area=8)])
        first_upload, _ = self.upload(self.client)
        duplicate, guest_estimate = self.upload(self.client, 'guest-rename.png')
        self.assertNotEqual(first_upload.pk, duplicate.pk)
        self.assertEqual(PlanAnalysis.objects.get().upload_id, first_upload.pk)
        self.claim(self.client, guest_estimate)
        first_upload.refresh_from_db()
        self.assertIsNone(first_upload.user_id)
        self.assertEqual(self.client.get(reverse('projects:whole_plan', args=[first_upload.pk])).status_code, 404)
        _, new_estimate = self.upload(self.client, 'renamed-after-login.png')
        self.assertIsNone(new_estimate)
        api.assert_called_once()
        self.assertEqual(PlanAnalysisBudget.objects.get().reserved_cents, 20)

    @patch('projects.plan_analysis.responses_create')
    def test_running_and_unknown_claimed_results_do_not_trigger_retry(self, api):
        api.return_value = model(rooms=[room(area=8)])
        _, initial = self.upload(self.client)
        self.claim(self.client, initial)
        original = PlanAnalysis.objects.get()
        for status, code in [('running', ''), ('unknown', 'api_failed')]:
            with self.subTest(status=status):
                PlanAnalysis.objects.filter(pk=original.pk).update(status=status, error_code=code)
                upload, estimate = self.upload(self.client, f'{status}.png')
                page = self.client.get(reverse('projects:whole_plan', args=[upload.pk]))
                self.assertEqual(page.context['analysis'].status, status)
                self.assertEqual(page.context['analysis'].pk, original.pk)
                self.assertIsNone(estimate)
        api.assert_called_once()
        self.assertEqual(PlanAnalysisBudget.objects.get().reserved_cents, 20)

    @patch('projects.plan_analysis.responses_create')
    def test_analyze_rechecks_claim_made_after_initial_miss(self, api):
        api.return_value = model(rooms=[room(area=8)])
        fixture, original = self.upload(self.client)
        buyer = Client()
        buyer.force_login(self.account)
        with patch('projects.plan_analysis.validate_configuration', side_effect=lambda: self.claim(self.client, original)):
            _, estimate = self.upload(buyer, 'while-claiming.png')
        self.assertEqual(estimate.snapshot['analysis_id'], PlanAnalysis.objects.get(upload=fixture).pk)
        api.assert_called_once()
        self.assertEqual(PlanAnalysisBudget.objects.get().reserved_cents, 20)

    @patch('projects.plan_analysis.responses_create')
    def test_offline_fixture_is_never_promoted_to_general_live_reuse(self, api):
        api.return_value = model(rooms=[room(area=8)])
        _, initial = self.upload(self.client)
        PlanAnalysis.objects.update(model='offline-fixture')
        self.claim(self.client, initial)
        api.return_value = model(rooms=[room(area=13)])
        _, normal = self.upload(self.client, 'signed-in-real.png')
        self.assertEqual(normal.snapshot['known_area'], '13.00')
        self.assertEqual(api.call_count, 2)
