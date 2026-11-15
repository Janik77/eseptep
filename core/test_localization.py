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

    def test_account_forms_have_explicit_localized_labels(self):
        from accounts.forms import MasterProfileForm, SupplierMaterialForm, EseptepAuthenticationForm
        from core.localization import localize_form
        with override('kk'):
            master = localize_form(MasterProfileForm())
            material = localize_form(SupplierMaterialForm())
            self.assertEqual(str(master.fields['full_name'].label), 'Аты-жөні')
            self.assertEqual(str(material.fields['name'].label), 'Материал атауы')
            login = EseptepAuthenticationForm(data={'username': 'missing@example.test', 'password': 'not-a-real-password'})
            self.assertFalse(login.is_valid())
            self.assertIn('электрондық пошта', str(login.errors))

    def test_decimal_validation_uses_kazakh_plural_messages(self):
        from accounts.forms import SupplierMaterialForm
        with override('kk'):
            form = SupplierMaterialForm(data={'name':'Example', 'category':'Example', 'unit':'m', 'price':'3.11111', 'stock_status':'Example'})
            self.assertFalse(form.is_valid())
            self.assertIn('Үтірден кейін 2 цифрдан', str(form.errors['price']))

    def test_all_definition_technical_values_are_language_invariant(self):
        with override('kk'):
            for definition in CALCULATORS:
                localized = system_tree(definition)
                self.assertEqual(localized['slug'], definition['slug'])
                for original, translated in zip(definition['fields'], localized['fields']):
                    self.assertEqual(original['name'], translated['name'])
                    self.assertEqual(original.get('default'), translated.get('default'))
                    self.assertEqual([x['value'] for x in original.get('options', [])], [x['value'] for x in translated.get('options', [])])

    def test_kazakh_prices_use_complete_messages_with_natural_word_order(self):
        from django.template import Template, Context
        samples = [
            ('от ₸ {{ amount }}', '₸ 12000 бастап'),
            ('₸ {{ amount }} за {{ unit }}', 'м² үшін ₸ 12000'),
            ('Справочно ₸ {{ amount }} за {{ unit }}', 'Анықтамалық баға: м² үшін ₸ 12000'),
        ]
        for source, expected in samples:
            template = Template('{% load i18n %}{% blocktranslate %}' + source + '{% endblocktranslate %}')
            with override('kk'):
                self.assertEqual(template.render(Context({'amount': '12000', 'unit': 'м²'})), expected)
            with override('ru'):
                self.assertEqual(template.render(Context({'amount': '12000', 'unit': 'м²'})), source.replace('{{ amount }}', '12000').replace('{{ unit }}', 'м²'))
        self.client.cookies['django_language'] = 'kk'
        for calculator in CALCULATORS:
            data = {f['name']: str(f.get('default', '')) for f in calculator['fields']}
            response = self.client.get(reverse('calculators:detail', args=[calculator['slug']]), {**data, '_preview': '1'})
            self.assertNotContains(response, 'бастап ₸')
            self.assertNotRegex(response.content.decode(), r'₸\s*[\d\s.,]+\s+үшін')
