from django.test import TestCase
from django.urls import reverse


class InterfaceRegressionTests(TestCase):
    def test_home_explains_workflow_without_unverified_claims(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'Планируйте ремонт проще')
        self.assertContains(response, 'class="direction-card"', count=3)
        self.assertContains(response, reverse('calculators:home'))
        self.assertContains(response, reverse('marketplace:home'))
        self.assertContains(response, reverse('projects:upload'))
        self.assertNotContains(response, 'renovation-hero.webp')
        self.assertContains(response, 'демонстрационный')
        self.assertNotContains(response, 'проверенные специалисты')
        self.assertNotContains(response, 'data-slider')

    def test_catalog_keeps_descriptions_and_distinct_accessible_names(self):
        response = self.client.get(reverse('calculators:home'))
        self.assertContains(response, 'aria-label="Открыть калькулятор:', count=12)
        self.assertNotContains(response, 'Загрузка API')

    def test_calculator_has_parameter_and_result_panels(self):
        response = self.client.get(reverse('calculators:detail', args=['natyazhnoy-potolok']))
        self.assertContains(response, 'calculator-workspace')
        self.assertContains(response, 'Заполните параметры')
        self.assertContains(response, 'data-calc-form')

    def test_demo_cards_cannot_be_mistaken_for_live_orders(self):
        response = self.client.post(reverse('calculators:detail', args=['natyazhnoy-potolok']), {'area': '42', 'rooms': '1'})
        self.assertContains(response, 'Демонстрационные профили')
        self.assertContains(response, 'Это не предложения реальных исполнителей')
        self.assertContains(response, 'Заказ недоступен.')
        self.assertNotContains(response, 'Проверенные профили')
        self.assertNotContains(response, '>Заказать</a>')

    def test_all_twelve_calculators_use_same_minimal_system(self):
        from calculators.definitions import CALCULATORS
        for calculator in CALCULATORS:
            response = self.client.get(reverse('calculators:detail', args=[calculator['slug']]))
            self.assertContains(response, 'minimal.css')
            self.assertContains(response, 'calculator-detail-hero')
            self.assertContains(response, 'calculator-workspace--unified')
            self.assertNotContains(response, 'editorial.css')
            self.assertNotContains(response, 'tile-swatch')
        self.assertContains(self.client.get(reverse('accounts:login')), 'minimal.css')

    def test_catalog_filters_progressively_enhance_all_twelve_links(self):
        from calculators.definitions import CALCULATORS
        response = self.client.get(reverse('calculators:home'))
        self.assertContains(response, 'data-catalog-toolbar hidden')
        self.assertContains(response, 'data-work-card', count=12)
        for item in CALCULATORS:
            self.assertContains(response, reverse('calculators:detail', args=[item['slug']]))
        self.assertContains(response, 'data-catalog-search')
        self.assertContains(response, 'data-catalog-reset')

    def test_tile_errors_link_to_inputs_and_keep_entered_values(self):
        response = self.client.post(reverse('calculators:detail', args=['plitka-keramogranit']), {
            'area': '-2', 'zone': 'floor', 'tile_format': '60x60'
        })
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="error-area"')
        self.assertContains(response, 'id="error-area"')
        self.assertContains(response, 'value="-2"')

    def test_invalid_login_has_visible_general_error(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'not-found@example.test', 'password': 'Wrong-test-password'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="form-errors" role="alert"')
