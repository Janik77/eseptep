"""Software regressions only: these tests do not certify construction methods."""
from copy import deepcopy
from math import ceil
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .definitions import CALCULATORS_BY_SLUG
from .services import (
    ELECTRIC_REFERENCE_MATRIX, TILE_REFERENCE_MATRIX,
    _scaled_electric_quantities, _tile_reference, calculate_materials,
)
from .validation import InputValidationError


class PilotAlgorithmRegressionTests(TestCase):
    def test_electrical_fraction_near_reference_is_scaled_not_rounded_to_kit(self):
        calculator = CALCULATORS_BY_SLUG['elektrika']
        for rooms in (2, 3):
            for area in (59.99, 60, 60.01):
                with self.subTest(area=area, rooms=rooms):
                    result = calculate_materials(calculator, {'area': str(area), 'rooms': str(rooms)})
                    reference = ELECTRIC_REFERENCE_MATRIX[(60, rooms)]
                    expected = reference['comfort_materials'] if area == 60 else _scaled_electric_quantities(area, rooms, reference)
                    self.assertEqual({row['title']: row['quantity'] for row in result['materials']}, expected)
                    self.assertEqual(result['meta']['area'], area)

    def test_tile_fraction_near_reference_scales_every_row(self):
        calculator = CALCULATORS_BY_SLUG['plitka-keramogranit']
        for ref_key, reference in TILE_REFERENCE_MATRIX.items():
            ref_area, zone, tile_format = ref_key
            for area in (ref_area - .01, ref_area, ref_area + .01):
                with self.subTest(key=ref_key, area=area):
                    result = calculate_materials(calculator, {'area': str(area), 'zone': zone, 'tile_format': tile_format})
                    expected = {title: quantity if area == ref_area else ceil(quantity * area / ref_area)
                                for title, quantity, _, _ in reference['materials']}
                    self.assertEqual({row['title']: row['quantity'] for row in result['materials']}, expected)

    def test_tile_reference_never_substitutes_available_zone_and_format(self):
        for area in (1, 20, 50, 100, 10000):
            for zone, tile_format in {key[1:] for key in TILE_REFERENCE_MATRIX}:
                with self.subTest(area=area, zone=zone, tile_format=tile_format):
                    key, _ = _tile_reference(area, zone, tile_format)
                    self.assertEqual(key[1:], (zone, tile_format))

    def test_missing_tile_kits_are_explicit_form_errors_not_fabricated_results(self):
        calculator = CALCULATORS_BY_SLUG['plitka-keramogranit']
        for zone in ('floor', 'bathroom'):
            data = {'area': '50.01', 'zone': zone, 'tile_format': 'large'}
            with self.assertRaises(InputValidationError) as raised:
                calculate_materials(calculator, data)
            self.assertIn('tile_format', raised.exception.errors)
            response = self.client.post(reverse('calculators:detail', args=[calculator['slug']]), data)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context['result'])
            self.assertEqual(response.context['form_data']['area'], '50.01')
            self.assertIn('Для выбранной зоны', response.context['form_errors'][0])

    def test_drywall_fraction_is_not_marked_exact_for_variant_budget(self):
        from .services import _drywall_variant_from_comfort, DRYWALL_REFERENCE_MATRIX
        calculator = CALCULATORS_BY_SLUG['gipsokarton-potolok']
        ref_key, ref = next(iter(DRYWALL_REFERENCE_MATRIX['ceiling'].items()))
        area, rooms = ref_key
        with patch('calculators.services._drywall_variant_from_comfort', wraps=_drywall_variant_from_comfort) as build:
            calculate_materials(calculator, {'area': str(area + .01), 'rooms': str(rooms), 'construction_type': 'ceiling'})
        self.assertEqual(build.call_args_list[0].args[4], round(ref['totals']['economy'] * (area + .01) / area))

    def test_reference_data_is_not_mutated_by_fractional_calculation(self):
        before = deepcopy((ELECTRIC_REFERENCE_MATRIX, TILE_REFERENCE_MATRIX))
        calculate_materials(CALCULATORS_BY_SLUG['elektrika'], {'area': '60.01', 'rooms': '3'})
        calculate_materials(CALCULATORS_BY_SLUG['plitka-keramogranit'], {'area': '20.01', 'zone': 'bathroom', 'tile_format': '60x60'})
        self.assertEqual((ELECTRIC_REFERENCE_MATRIX, TILE_REFERENCE_MATRIX), before)

    def test_every_calculator_fractional_input_and_all_variants_keep_consistent_totals(self):
        from .definitions import CALCULATORS
        from .tests import defaults
        for calculator in CALCULATORS:
            data = defaults(calculator)
            # Includes floor_area and thickness, not only a field named area.
            for field in calculator['fields']:
                if field['type'] != 'select' and field.get('step') != 1:
                    data[field['name']] = '2,5' if field['name'] == 'thickness' else '36,51'
            initial = calculate_materials(calculator, data)
            variants = initial.get('variants') or [None]
            for variant in variants:
                selected_data = {**data, 'selected_variant': variant['key']} if variant else data
                with self.subTest(slug=calculator['slug'], variant=variant and variant['key']):
                    result = calculate_materials(calculator, selected_data)
                    self.assertEqual(result['materials_total'], sum(row['reference_total'] for row in result['materials']))
                    self.assertEqual(result['grand_total'], result['materials_total'] + result['labor_total'] + result.get('additional_total', 0))
                    for row in result['materials']:
                        self.assertEqual(row['reference_total'], round(row['quantity'] * row['reference_price']))
                    for field in calculator['fields']:
                        if field['type'] != 'select' and field.get('step') != 1:
                            self.assertEqual(result['meta']['input'][field['name']], selected_data[field['name']].replace(',', '.'))
                    if variant:
                        self.assertEqual(result['selected_variant'], variant['key'])
