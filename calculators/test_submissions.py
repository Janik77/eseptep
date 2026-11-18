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
