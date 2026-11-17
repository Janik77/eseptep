from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from accounts import tests as account_tests
from django.test import TestCase
from accounts.models import Calculation, ClientProject
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.services import calculate_materials, save_calculation_for_user


class ProjectSelectionTests(TestCase):
    user = account_tests.AccountWorkflowTests.user
    def setUp(self):
        account_tests.AccountWorkflowTests.setUp(self)
        self.slug = 'demontazh'
        self.result = calculate_materials(CALCULATORS_BY_SLUG[self.slug], {'area': '60', 'demolition_type': 'partial'})
        self.newer = ClientProject.objects.create(user=self.owner, title='Newer', city='Астана', area_m2=80, rooms=3)

    def test_selected_project_not_latest(self):
        project, calculation = save_calculation_for_user(self.owner, self.slug, self.result, self.project.pk)
        self.assertEqual(project.pk, self.project.pk)
        self.assertEqual(calculation.project_id, self.project.pk)
        self.assertFalse(self.newer.calculations.exists())

    def test_missing_foreign_finished_project_rejected(self):
        for pk in [None, '', 'bad', self.project.pk]:
            if pk == self.project.pk:
                self.project.status = 'done'
                self.project.save()
            with self.assertRaises(ValidationError):
                save_calculation_for_user(self.owner, self.slug, self.result, pk)
        with self.assertRaises(ValidationError):
            save_calculation_for_user(self.other, self.slug, self.result, self.newer.pk)
        self.assertFalse(Calculation.objects.exists())

    def test_provider_or_guest_cannot_save(self):
        for user in [self.master, self.supplier, AnonymousUser()]:
            with self.assertRaises(PermissionDenied):
                save_calculation_for_user(user, self.slug, self.result, self.project.pk)

    def test_http_missing_project_is_error_without_save(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('calculators:detail', args=[self.slug]), {'area': '60', 'demolition_type': 'partial', 'parameter_version': self.result['parameter_snapshot']['version'], 'action': 'save_estimate'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Выберите проект')
        self.assertFalse(Calculation.objects.exists())

    def test_http_save_selected_project(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('calculators:detail', args=[self.slug]), {'area': '60', 'demolition_type': 'partial', 'parameter_version': self.result['parameter_snapshot']['version'], 'action': 'save_estimate', 'project_id': self.project.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Calculation.objects.get().project_id, self.project.pk)

    def test_unbounded_or_invalid_project_id_is_field_error(self):
        self.client.force_login(self.owner)
        for value in ['9' * 5000, str(2**63), '0', '-1', '１２', '', '1.5']:
            with self.subTest(value=value[:25]):
                response = self.client.post(reverse('calculators:detail', args=[self.slug]), {
                    'area': '60', 'demolition_type': 'partial', 'parameter_version': self.result['parameter_snapshot']['version'],
                    'action': 'save_estimate', 'project_id': value})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Выберите проект')
                self.assertIsNotNone(response.context['result'])
        self.assertFalse(Calculation.objects.exists())

    def test_saved_detail_retains_snapshot_without_recalculation(self):
        from unittest.mock import patch
        self.client.force_login(self.owner)
        payload = {'area': '20.5', 'rooms': '1', 'selected_variant': 'economy',
                   'action': 'save_estimate', 'project_id': self.project.pk}
        response = self.client.post(reverse('calculators:detail', args=['natyazhnoy-potolok']), payload)
        saved = Calculation.objects.get()
        self.assertEqual(saved.segment, 'economy')
        self.assertEqual(saved.result_data['selected_variant'], 'economy')
        url = reverse('accounts:calculation_detail', args=[saved.pk])
        self.assertRedirects(response, url)
        with patch('calculators.services.calculate_materials', side_effect=AssertionError('No recalculation')):
            for _ in range(2):
                page = self.client.get(url)
                self.assertContains(page, '20.5')
                self.assertContains(page, 'Эконом')
                self.assertContains(page, self.project.title)
                self.assertEqual(page.context['calculation'].grand_total, saved.grand_total)
        self.assertEqual(Calculation.objects.count(), 1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('accounts:calculation_detail', args=['9' * 5000])).status_code, 404)
