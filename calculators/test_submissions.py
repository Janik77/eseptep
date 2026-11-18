from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import Calculation, CalculationSubmission, ClientProject, ServiceRequest, UserProfile
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data


class SubmissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('submission-client')
        UserProfile.objects.create(user=self.user, role='client')
        self.project = ClientProject.objects.create(user=self.user, title='Synthetic', city='Test', area_m2=60, rooms=2)
        self.client.force_login(self.user)
        self.url = reverse('calculators:detail', args=['elektrika'])
        self.inputs = _get_form_data(CALCULATORS_BY_SLUG['elektrika'])

    def payload(self, action='save_estimate'):
        response = self.client.post(self.url, self.inputs)
        return {**self.inputs, 'action': action, 'project_id': str(self.project.pk),
                'submission_token': response.context['submission_token']}

    def test_duplicate_each_action_returns_same_record(self):
        for action in ('save_estimate', 'request_master', 'request_supplier'):
            data = self.payload(action)
            first = self.client.post(self.url, data)
            second = self.client.post(self.url, data)
            self.assertEqual(first.status_code, 302)
            self.assertEqual(first.url, second.url)
        self.assertEqual(Calculation.objects.count(), 3)
        self.assertEqual(ServiceRequest.objects.count(), 2)
        self.assertEqual(CalculationSubmission.objects.count(), 3)

    def test_missing_tampered_foreign_and_changed_inputs_fail_closed(self):
        data = self.payload()
        other = get_user_model().objects.create_user('other-submission-client')
        UserProfile.objects.create(user=other, role='client')
        for change in ({'submission_token': ''}, {'submission_token': 'tampered'}, {'area': '61'}):
            response = self.client.post(self.url, {**data, **change})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form_errors'])
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, data).status_code, 200)
        self.assertEqual(Calculation.objects.count(), 0)

    def test_anonymous_render_token_cannot_be_used_after_login(self):
        self.client.logout()
        data = self.payload()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, data).status_code, 200)
        self.assertEqual(Calculation.objects.count(), 0)

    def test_replay_fingerprint_and_fresh_calculation(self):
        data = self.payload()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        response = self.client.post(self.url, {**data, 'selected_variant': 'business'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_errors'])
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        self.assertEqual(Calculation.objects.count(), 2)

    def test_request_failure_rolls_back_receipt_and_calculation(self):
        data = self.payload('request_master')
        with patch('calculators.submissions.ServiceRequest.objects.create', side_effect=ValidationError('Synthetic failure')):
            self.assertEqual(self.client.post(self.url, data).status_code, 200)
        self.assertEqual(Calculation.objects.count(), 0)
        self.assertEqual(CalculationSubmission.objects.count(), 0)
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_replay_does_not_revalidate_new_pricing(self):
        data = self.payload()
        first = self.client.post(self.url, data)
        with patch('calculators.views.save_calculation_for_user', side_effect=AssertionError('must not save twice')):
            replay = self.client.post(self.url, data)
        self.assertEqual(first.url, replay.url)

    def test_database_unique_constraint(self):
        self.client.post(self.url, self.payload())
        receipt = CalculationSubmission.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CalculationSubmission.objects.create(user=self.user, nonce=receipt.nonce,
                action=receipt.action, fingerprint=receipt.fingerprint)

    def test_token_for_another_calculator_is_rejected(self):
        from calculators.submissions import result_token
        data = self.payload()
        # Even an otherwise valid signature and identical fields must not cross slugs.
        data['submission_token'] = result_token(self.user, 'santehnika', self.inputs)
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_errors'])
        self.assertEqual(CalculationSubmission.objects.count(), 0)
        self.assertEqual(Calculation.objects.count(), 0)

    def test_foreign_and_closed_projects_roll_back_receipt(self):
        other = get_user_model().objects.create_user('foreign-project-owner')
        foreign = ClientProject.objects.create(user=other, title='Foreign', area_m2=60, rooms=2)
        closed = ClientProject.objects.create(user=self.user, title='Closed', area_m2=60, rooms=2, status='done')
        for project in (foreign, closed):
            data = {**self.payload('request_supplier'), 'project_id': str(project.pk)}
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form_errors'])
            self.assertEqual(CalculationSubmission.objects.count(), 0)
            self.assertEqual(Calculation.objects.count(), 0)
            self.assertEqual(ServiceRequest.objects.count(), 0)

    def test_consumed_token_cannot_change_project(self):
        second = ClientProject.objects.create(user=self.user, title='Second', area_m2=60, rooms=2)
        data = self.payload()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        response = self.client.post(self.url, {**data, 'project_id': str(second.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_errors'])
        self.assertEqual(Calculation.objects.count(), 1)
        self.assertEqual(second.calculations.count(), 0)

    def test_completed_replay_after_real_price_publication_keeps_old_snapshot(self):
        from datetime import date
        from django.utils import timezone
        from calculators.models import PriceBook
        first_book = PriceBook.objects.create(store_name='Synthetic', version='submission-price-v1',
            source_note='Synthetic', price_date=date(2026, 1, 1), published_at=timezone.now(), is_active=True)
        data = {**self.payload('request_master'), 'price_book_version': first_book.version}
        first = self.client.post(self.url, data)
        self.assertEqual(first.status_code, 302)
        before = Calculation.objects.get().result_data
        PriceBook.objects.filter(pk=first_book.pk).update(is_active=False)
        PriceBook.objects.create(store_name='Synthetic', version='submission-price-v2',
            source_note='Synthetic', price_date=date(2026, 1, 2), published_at=timezone.now(), is_active=True)
        replay = self.client.post(self.url, data)
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(first.url, replay.url)
        self.assertEqual(Calculation.objects.count(), 1)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(Calculation.objects.get().result_data, before)
        self.assertEqual(before['admin_quote']['version'], 'submission-price-v1')
        self.assertEqual(before['admin_quote']['method_version'], 'reference-quantities@pilot-exact-match-v2')
