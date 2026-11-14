from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Calculation, ClientProject, ServiceRequest, UserProfile
from .definitions import CALCULATORS
from .services import calculate_materials
from .validation import InputValidationError, MAX_AREA, MAX_COUNT, validate_calculator_input


def defaults(calculator):
    return {field['name']: str(field['default']) for field in calculator['fields']}


class CalculatorValidationTests(TestCase):
    def test_all_twelve_defaults_and_inclusive_boundaries(self):
        self.assertEqual(len(CALCULATORS), 12)
        for calculator in CALCULATORS:
            for boundary in ('default', 'min', 'max'):
                data = defaults(calculator)
                for field in calculator['fields']:
                    if field['type'] != 'select' and boundary != 'default':
                        data[field['name']] = str(field.get(boundary, 1 if boundary == 'min' else MAX_COUNT if field.get('step') == 1 else MAX_AREA))
                with self.subTest(slug=calculator['slug'], boundary=boundary):
                    result = calculate_materials(calculator, data)
                    self.assertGreater(result['grand_total'], 0)
                    self.assertLess(result['grand_total'], 10**10)
                    response = self.client.post(reverse('calculators:detail', args=[calculator['slug']]), data)
                    self.assertEqual(response.status_code, 200)
                    self.assertIsNotNone(response.context['result'])

    def test_every_numeric_field_rejects_bad_values_without_persistence(self):
        user = get_user_model().objects.create_user(username='synthetic-calculator')
        UserProfile.objects.get_or_create(user=user)
        self.client.force_login(user)
        for calculator in CALCULATORS:
            for field in calculator['fields']:
                if field['type'] == 'select':
                    bad_values = ['', 'unknown', '<script>']
                else:
                    bad_values = ['', 'abc', '-1', '0', '1e1000', 'NaN', 'Infinity', '-Infinity', '1,2,3', '1.001', '9'*1000]
                    if field.get('step') == 1:
                        bad_values += ['1.5', '1,5']
                for value in bad_values:
                    data = {**defaults(calculator), field['name']: value, 'action': 'save_estimate'}
                    with self.subTest(slug=calculator['slug'], field=field['name'], value=value[:30]):
                        with self.assertRaises(InputValidationError):
                            calculate_materials(calculator, data)
                        response = self.client.post(reverse('calculators:detail', args=[calculator['slug']]), data)
                        self.assertEqual(response.status_code, 200)
                        self.assertIsNone(response.context['result'])
                        self.assertTrue(response.context['form_errors'])
                        self.assertEqual(response.context['form_data'][field['name']], value)
        self.assertEqual(Calculation.objects.count(), 0)
        self.assertEqual(ClientProject.objects.count(), 0)
        self.assertEqual(ServiceRequest.objects.count(), 0)

    def test_missing_fields_and_invalid_variant(self):
        for calculator in CALCULATORS:
            with self.subTest(slug=calculator['slug']):
                for data in ({}, {**defaults(calculator), 'selected_variant': 'bogus'}, {**defaults(calculator), 'selected_variant': ''}):
                    response = self.client.post(reverse('calculators:detail', args=[calculator['slug']]), data)
                    self.assertTrue(response.context['form_errors'])
                    self.assertIsNone(response.context['result'])

    def test_comma_decimals_and_integer_values(self):
        for calculator in CALCULATORS:
            data = defaults(calculator)
            for field in calculator['fields']:
                if field['type'] != 'select':
                    data[field['name']] = '2,0' if field.get('step') == 1 else '2,5'
            with self.subTest(slug=calculator['slug']):
                cleaned = validate_calculator_input(calculator, data)
                self.assertNotIn(',', ''.join(cleaned.values()))
                self.assertGreater(calculate_materials(calculator, data)['grand_total'], 0)

    def test_valid_save_for_every_calculator(self):
        user = get_user_model().objects.create_user(username='synthetic-valid')
        UserProfile.objects.get_or_create(user=user)
        self.client.force_login(user)
        for calculator in CALCULATORS:
            with self.subTest(slug=calculator['slug']):
                response = self.client.post(reverse('calculators:detail', args=[calculator['slug']]), {**defaults(calculator), 'action': 'save_estimate'})
                self.assertEqual(response.status_code, 302)
                saved = Calculation.objects.latest('pk')
                saved.full_clean()
        self.assertEqual(Calculation.objects.count(), 12)
