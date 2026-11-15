from copy import deepcopy
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override
from calculators.definitions import CALCULATORS, CALCULATORS_BY_SLUG
from calculators.services import calculate_materials
from accounts.models import Calculation
from core.localization import system_tree, system_text, localize_result


class LocalizationTests(TestCase):
    def test_language_cookie_survives_navigation_and_js_catalog(self):
        response = self.client.post(reverse('set_language'), {'language': 'kk', 'next': '/calculators/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/calculators/')
        for url in ['/', '/calculators/', '/accounts/login/', '/accounts/register/', '/projects/upload/', '/marketplace/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, 'lang="kk"')
        self.assertContains(self.client.get('/'), 'Материалдарды есептеу')
        self.assertContains(self.client.get('/jsi18n/'), 'django.catalog')

    def test_all_calculators_keep_numeric_inputs_on_safe_get_preview(self):
        self.client.cookies['django_language'] = 'kk'
        for calculator in CALCULATORS:
            data = {f['name']: str(f.get('default', '')) for f in calculator['fields']}
            data['_preview'] = '1'
            response = self.client.get(reverse('calculators:detail', args=[calculator['slug']]), data)
            self.assertEqual(response.status_code, 200, calculator['slug'])
            self.assertIsNotNone(response.context['result'], calculator['slug'])
            self.assertEqual(response.context['form_data'], {k:v for k,v in data.items() if k != '_preview'})
        self.assertEqual(Calculation.objects.count(), 0)

    def test_preview_never_runs_mutation_actions(self):
        calculator = CALCULATORS_BY_SLUG['plitka-keramogranit']
        data = {f['name']: str(f.get('default', '')) for f in calculator['fields']}
        data.update(_preview='1', action='save_estimate', project_id='1', selected_variant='business')
        response = self.client.get(reverse('calculators:detail', args=[calculator['slug']]), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['result']['selected_variant'], 'business')
        self.assertEqual(Calculation.objects.count(), 0)

    def test_display_translation_does_not_mutate_canonical_definitions_or_result(self):
        calculator = CALCULATORS_BY_SLUG['plitka-keramogranit']
        before = deepcopy(calculator)
        data = {f['name']: str(f.get('default', '')) for f in calculator['fields']}
        result = calculate_materials(calculator, data)
        snapshot = deepcopy(result)
        with override('kk'):
            displayed = system_tree(result)
            localize_result(displayed, system_tree(calculator))
            self.assertNotEqual(displayed['copy_text'], result['copy_text'])
            self.assertEqual(system_text('Материал'), 'Материал')
        self.assertEqual(result, snapshot)
        self.assertEqual(calculator, before)

    def test_unknown_upload_cannot_be_read_via_language_preview(self):
        self.assertEqual(self.client.get('/projects/upload/?upload_id=999999').status_code, 404)
