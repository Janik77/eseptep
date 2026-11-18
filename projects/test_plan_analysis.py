import io
import json
import tempfile
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from .models import ProjectUpload, PlanAnalysisBudget, PlanConfirmation
from .plan_analysis import analyze, normalize_rooms, PlanError


class PlanPilotTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings_context = override_settings(PRIVATE_MEDIA_ROOT=self.temp.name, OPENAI_LIVE_CONFIRMED=True, PLAN_AI_ENABLED=True, OPENAI_API_KEY='unit-test-placeholder', PRODUCTION=False)
        self.settings_context.enable()
        self.addCleanup(self.settings_context.disable)
        self.addCleanup(self.temp.cleanup)
        self.user = User.objects.create_user('plan-client')
        self.client.force_login(self.user)
        image = io.BytesIO()
        Image.new('RGB', (100, 100), 'white').save(image, 'PNG')
        self.raw = image.getvalue()
        self.upload = ProjectUpload.objects.create(user=self.user, file=SimpleUploadedFile('plan.png', self.raw))

    def response(self, area=4.8):
        response = io.BytesIO(json.dumps({'status': 'completed', 'id': 'test-response', 'usage': {'input_tokens': 100, 'output_tokens': 50}, 'output': [{'content': [{'type': 'output_text', 'text': json.dumps({'rooms': [{'name': 'Ванная', 'kind': 'bathroom', 'source': 'stated' if area else 'unknown', 'area': area, 'page': 1, 'evidence': 'invented'}]})}]}]}).encode())
        return json.loads(response.getvalue())

    @patch('projects.plan_analysis.responses_create')
    def test_reclick_reupload_and_language_are_not_charged_again(self, api):
        api.return_value = self.response()
        first = analyze(self.upload)
        self.assertEqual(first.rooms[0]['area'], '4.80')
        self.assertIsNone(first.rooms[0]['line'])
        self.assertEqual(analyze(self.upload).pk, first.pk)
        duplicate = ProjectUpload.objects.create(user=self.user, file=SimpleUploadedFile('again.png', self.raw))
        self.assertEqual(analyze(duplicate).pk, first.pk)
        self.client.get(f'/projects/{self.upload.pk}/plan/', HTTP_ACCEPT_LANGUAGE='kk')
        self.assertEqual(api.call_count, 1)
        self.assertEqual(PlanAnalysisBudget.objects.get(pk=1).reserved_cents, 20)

    @patch('projects.plan_analysis.responses_create', side_effect=TimeoutError)
    def test_unknown_attempt_never_retries_or_refunds(self, api):
        self.assertEqual(analyze(self.upload).status, 'unknown')
        analyze(self.upload)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(PlanAnalysisBudget.objects.get(pk=1).reserved_cents, 20)

    @patch('projects.plan_analysis.responses_create')
    def test_budget_ceiling(self, api):
        PlanAnalysisBudget.objects.create(pk=1, reserved_cents=200)
        self.assertEqual(analyze(self.upload).error_code, 'budget_limit')
        api.assert_not_called()

    @override_settings(OPENAI_API_KEY='')
    def test_missing_key_no_charge(self):
        with self.assertRaises(PlanError):
            analyze(self.upload)
        self.assertFalse(PlanAnalysisBudget.objects.exists())

    def test_manual_confirmation_and_tamper(self):
        url = f'/projects/{self.upload.pk}/plan/'
        response = self.client.post(url, {'action': 'confirm', 'name': 'Ванная', 'area': '5,25'})
        self.assertEqual(response.status_code, 302)
        record = PlanConfirmation.objects.get()
        self.assertEqual(record.snapshot['area'], '5.25')
        page = self.client.get(response.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '5.25')
        altered = self.client.get(response.url.replace('area=5.25', 'area=9.00'))
        self.assertContains(altered, 'Площадь отличается')

    def test_ownership(self):
        self.client.force_login(User.objects.create_user('other-plan-client'))
        self.assertEqual(self.client.get(f'/projects/{self.upload.pk}/plan/').status_code, 404)
        self.assertEqual(self.client.get(f'/projects/{self.upload.pk}/plan/page/1/').status_code, 404)

    def test_unknown_and_dimensions(self):
        rooms = normalize_rooms([{'name': 'Ванная', 'source': 'unknown', 'area': 4.8}, {'name':'B', 'source':'dimensions', 'width':2, 'length':2.4}], [(b'', '')])
        self.assertIsNone(rooms[0]['area'])
        self.assertEqual(rooms[1]['area'], '4.80')

    def test_floor_calculation_saved_with_confirmed_source(self):
        from accounts.models import UserProfile, Calculation, ClientProject
        UserProfile.objects.get_or_create(user=self.user, defaults={'role': 'client'})
        response = self.client.post(f'/projects/{self.upload.pk}/plan/', {'action': 'confirm', 'name': 'Ванная', 'area': '5,25'})
        from urllib.parse import urlparse, parse_qs
        params = {k:v[0] for k,v in parse_qs(urlparse(response.url).query).items()}
        params.pop('_preview')
        path = urlparse(response.url).path
        rendered = self.client.post(path, params)
        result = rendered.context['result']
        self.assertEqual(result['plan_source']['area'], '5.25')
        project = ClientProject.objects.create(user=self.user, title='Test plan', area_m2=40, rooms=2)
        payload = {**params, 'project_id':str(project.pk), 'action':'save_estimate', 'selected_variant':'economy',
                   'submission_token': rendered.context['submission_token'],
                   'parameter_version': (result.get('parameter_snapshot') or {}).get('version', ''),
                   'price_book_version': (result.get('admin_quote') or {}).get('version', '')}
        saved = self.client.post(path, payload)
        self.assertEqual(saved.status_code, 302, saved.context['form_errors'] if saved.context else '')
        again = self.client.post(path, payload)
        self.assertEqual(again.url, saved.url)
        calculation = Calculation.objects.get()
        self.assertEqual(calculation.result_data['plan_source']['area'], '5.25')
        self.assertEqual(calculation.result_data['input']['zone'], 'floor')

    @patch('projects.plan_analysis.responses_create')
    def test_unreadable_value_requires_manual_confirmation_and_kazakh(self, api):
        api.return_value = self.response(None)
        analyze(self.upload)
        url = f'/projects/{self.upload.pk}/plan/'
        page = self.client.get(url, HTTP_ACCEPT_LANGUAGE='kk')
        self.assertContains(page, 'Аудан анықталмады')
        self.assertContains(page, 'value=""')
        rejected = self.client.post(url, {'action':'confirm', 'room':'0', 'name':'Ванная','area':''})
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(PlanConfirmation.objects.exists())
        self.client.post(url, {'action':'confirm','room':'0','name':'Ванная','area':'6.12'})
        snapshot = PlanConfirmation.objects.get().snapshot
        self.assertEqual(snapshot['area'], '6.12')
        self.assertTrue(snapshot['manually_corrected'])
        self.assertIsNone(snapshot['original']['area'])

    def test_pdf_limit_and_real_text_locator(self):
        from pathlib import Path
        from .plan_analysis import pages
        raw = Path(__file__).resolve().parent.parent.joinpath('tests/fixtures/plans/apartment-explication.pdf').read_bytes()
        upload = ProjectUpload.objects.create(user=self.user, file=SimpleUploadedFile('plan.pdf', raw))
        _, frames = pages(upload)
        rooms = normalize_rooms([{'name':'Ванная','source':'stated','area':4.8,'page':1,'evidence':'3   Ванная          4,8 м²'}], frames)
        self.assertIsNotNone(rooms[0]['line'])
        self.assertEqual(rooms[0]['evidence'], '3   Ванная          4,8 м²')

    @patch('projects.plan_analysis.responses_create')
    def test_corrupt_legacy_file_is_manual_fallback_not_500(self, api):
        broken = ProjectUpload.objects.create(user=self.user, file=SimpleUploadedFile('broken.png', b'not an image'))
        page = self.client.post(f'/projects/{broken.pk}/plan/', {'action':'analyze'})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Не удалось прочитать файл')
        self.assertEqual(self.client.get(f'/projects/{broken.pk}/plan/page/1/').status_code, 404)
        api.assert_not_called()
