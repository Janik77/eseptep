from django.test import TestCase
from django.urls import reverse


class InterfaceRegressionTests(TestCase):
    def test_home_explains_workflow_without_unverified_claims(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'Сначала расчёт.')
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
