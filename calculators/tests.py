from calculators.submission_test_helpers import post_result
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
                    response = post_result(self.client, reverse('calculators:detail', args=[calculator['slug']]), data)
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
                        response = post_result(self.client, reverse('calculators:detail', args=[calculator['slug']]), data)
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
                    response = post_result(self.client, reverse('calculators:detail', args=[calculator['slug']]), data)
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
        project = ClientProject.objects.create(user=user, title='Synthetic', city='Test', area_m2=60, rooms=2)
        for calculator in CALCULATORS:
            with self.subTest(slug=calculator['slug']):
                url = reverse('calculators:detail', args=[calculator['slug']])
                preview = post_result(self.client, url, defaults(calculator))
                parameter_version = (preview.context['result'].get('parameter_snapshot') or {}).get('version', '')
                response = post_result(self.client, url, {**defaults(calculator), 'action': 'save_estimate', 'project_id': project.pk, 'parameter_version': parameter_version})
                self.assertEqual(response.status_code, 302)
                saved = Calculation.objects.latest('pk')
                saved.full_clean()
        self.assertEqual(Calculation.objects.count(), 12)


class CalculatorArithmeticTests(TestCase):
    def assert_result_consistent(self, result):
        variants = result.get('variants', [result])
        for variant in variants:
            rows = variant['materials']
            for row in rows:
                self.assertGreaterEqual(row['quantity'], 0)
                self.assertGreaterEqual(row['reference_price'], 0)
                self.assertEqual(row['reference_total'], round(row['quantity'] * row['reference_price']))
                self.assertEqual(row['total'], row['reference_total'])
            material_sum = sum(row['reference_total'] for row in rows)
            self.assertEqual(variant['materials_total'], material_sum)
            if 'key' in variant:
                self.assertEqual(variant['total'], material_sum + variant['extra'])
        self.assertEqual(result['materials_total'], sum(row['total'] for row in result['materials']))
        self.assertEqual(result['grand_total'], result['materials_total'] + result['labor_total'] + result.get('additional_total', 0))

    def test_all_calculators_choices_boundaries_and_reference_neighbors(self):
        from itertools import product
        for calculator in CALCULATORS:
            choice_fields = [field for field in calculator['fields'] if field['type'] == 'select']
            choices = product(*[[option['value'] for option in field['options']] for field in choice_fields])
            for chosen in choices:
                for area in ('1', '19.99', '20', '20.01', '42', '60', '10000'):
                    for count in ('1', '2', '100'):
                        data = defaults(calculator)
                        data.update(zip([field['name'] for field in choice_fields], chosen))
                        for field in calculator['fields']:
                            if field['name'] == 'area':
                                data['area'] = area
                            elif field.get('step') == 1:
                                data[field['name']] = count
                        with self.subTest(slug=calculator['slug'], data=data):
                            if calculator['slug'] == 'plitka-keramogranit' and data['tile_format'] == 'large' and data['zone'] in {'floor', 'bathroom'}:
                                with self.assertRaises(InputValidationError):
                                    calculate_materials(calculator, data)
                            else:
                                self.assert_result_consistent(calculate_materials(calculator, data))

    def test_ceiling_negative_niche_regression(self):
        from .definitions import CALCULATORS_BY_SLUG
        result = calculate_materials(CALCULATORS_BY_SLUG['natyazhnoy-potolok'], {'area': '20', 'rooms': '1', 'selected_variant': 'economy'})
        niche = next(row for row in result['materials'] if row['title'] == 'Скрытый карниз / ниша')
        self.assertEqual(niche['reference_total'], 6000)
        self.assertEqual(result['materials_total'], 103600)
        self.assert_result_consistent(result)

    def test_legacy_budget_helpers_never_mutate_rows(self):
        from copy import deepcopy
        from .services import _adjust_variant_rows_total, _adjust_self_level_total
        rows = [{'quantity': 1, 'reference_price': 6000, 'reference_total': 6000, 'total': 6000}]
        original = deepcopy(rows)
        self.assertEqual(_adjust_variant_rows_total(rows, 10), -5990)
        self.assertEqual(_adjust_self_level_total(rows, 10), -5990)
        self.assertEqual(rows, original)

    def test_all_variants_render_and_persist_matching_rows_totals_and_copy(self):
        user = get_user_model().objects.create_user(username='synthetic-variants')
        UserProfile.objects.get_or_create(user=user)
        self.client.force_login(user)
        project = ClientProject.objects.create(user=user, title='Synthetic variants', city='Test', area_m2=60, rooms=2)
        for calculator in CALCULATORS:
            initial = calculate_materials(calculator, defaults(calculator))
            for variant in initial.get('variants', []):
                data = {**defaults(calculator), 'selected_variant': variant['key']}
                with self.subTest(slug=calculator['slug'], variant=variant['key']):
                    response = post_result(self.client, reverse('calculators:detail', args=[calculator['slug']]), data)
                    result = response.context['result']
                    self.assertEqual(result['selected_variant_label'], variant['title'])
                    self.assertEqual(result['materials'], variant['materials'])
                    self.assertIn(variant['title'], result['copy_text'])
                    self.assert_result_consistent(result)
                    response = post_result(self.client, reverse('calculators:detail', args=[calculator['slug']]), {**data, 'action': 'save_estimate', 'project_id': project.pk, 'parameter_version': (result.get('parameter_snapshot') or {}).get('version', '')})
                    self.assertEqual(response.status_code, 302)
                    saved = Calculation.objects.latest('pk')
                    saved.full_clean()
                    self.assertEqual(saved.materials_total, result['materials_total'])
                    self.assertEqual(saved.grand_total, result['grand_total'])
                    self.assertEqual(saved.result_data['selected_variant'], variant['key'])
                    if variant['key'] in {'economy', 'comfort', 'business'}:
                        self.assertEqual(saved.segment, variant['key'])
                    self.assertEqual(saved.result_data['materials'], result['materials'])

    def test_plumbing_surcharge_is_separate_and_visible(self):
        from .definitions import CALCULATORS_BY_SLUG
        calculator = CALCULATORS_BY_SLUG['santehnika']
        response = post_result(self.client, reverse('calculators:detail', args=[calculator['slug']]), {**defaults(calculator), 'selected_variant': 'business'})
        result = response.context['result']
        self.assertEqual(result['additional_total'], 150000)
        self.assertContains(response, 'Дополнительная сумма пакета (состав не указан)')
        self.assert_result_consistent(result)
