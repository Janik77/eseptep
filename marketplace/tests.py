from django.test import TestCase
from django.urls import reverse


class PackageValidationTests(TestCase):
    def test_valid_defaults_comma_and_boundaries(self):
        for area in ('1', '60', '60,5', '10000'):
            response = self.client.post(reverse('marketplace:home'), {'area': area, 'city': 'Астана', 'developer': 'BI'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['results']), 3)
            self.assertEqual(response.context['results'][0]['total'], round(float(area.replace(',', '.')) * 120000))

    def test_invalid_inputs_preserved_with_errors(self):
        for field, values in {'area': ['', 'abc', '-1', '0', 'NaN', 'Infinity', '-Infinity', '10001', '1e1000', '1,2,3', '1.001'], 'city': ['', 'Unknown'], 'developer': ['', 'Unknown']}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    response = self.client.post(reverse('marketplace:home'), {'area': '60', 'city': 'Астана', 'developer': 'BI', field: value})
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.context['results'])
                    self.assertIn(field, response.context['form_errors'])
                    self.assertEqual(response.context['form_data'][field], value)
        response = self.client.post(reverse('marketplace:home'), {})
        self.assertEqual(len(response.context['form_errors']), 3)
