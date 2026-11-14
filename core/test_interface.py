from django.test import TestCase
from django.urls import reverse


class InterfaceRegressionTests(TestCase):
    def test_home_explains_workflow_without_unverified_claims(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'Ваш ремонт.')
        self.assertContains(response, 'Концептуальный интерьер · AI-иллюстрация')
        self.assertContains(response, 'DEMO')
        self.assertContains(response, 'width="1536" height="1024"')
        self.assertContains(response, 'Начать расчёт')
        self.assertContains(response, 'Анализ файла пока демонстрационный')
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

    def test_first_iteration_styles_only_selected_pages(self):
        tile = self.client.get(reverse('calculators:detail', args=['plitka-keramogranit']))
        self.assertContains(tile, 'body class="editorial-calculator"')
        self.assertContains(tile, 'calculator-editorial.css')
        other = self.client.get(reverse('calculators:detail', args=['elektrika']))
        self.assertNotContains(other, 'calculator-editorial.css')
        self.assertNotContains(other, 'editorial.css')
        dashboard = self.client.get(reverse('accounts:login'))
        self.assertNotContains(dashboard, 'editorial.css')

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
