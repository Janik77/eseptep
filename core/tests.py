from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from core.templatetags.eseptep_i18n import money


class PresentationRegressionTests(TestCase):
    def test_money_preserves_fraction_and_groups_without_mutation(self):
        for value, expected in [(593060, '593 060'), (Decimal('593060.50'), '593 060,5'), (0, '0'), (1000.0, '1 000')]:
            self.assertEqual(money(value), expected)

    def test_tile_input_precision_and_no_duplicate_metrics_in_both_languages(self):
        for language in ['ru', 'kk']:
            self.client.cookies['django_language'] = language
            response = self.client.post(reverse('calculators:detail', args=['plitka-keramogranit']), {'area':'36.5', 'zone':'bathroom', 'tile_format':'60x60'})
            self.assertEqual(response.status_code, 200)
            result = response.context['result']
            self.assertIsNotNone(result)
            fields = response.context['form_fields']
            self.assertEqual(next(f['value'] for f in fields if f['name'] == 'area'), '36.5')
            self.assertFalse(set(f['label'] for f in fields) & set(m['label'] for m in result['metrics']))
            self.assertNotContains(response, 'Площадь укладки</b>36')
            self.assertContains(response, money(result['grand_total']))
