"""Real admin POST coverage; synthetic data, no real shop prices."""
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import PriceBook, MaterialPrice, SelfLevelMixEdition, DemolitionFilmEdition, RenovationRateEdition
from .material_keys import BY_KEY


class AdminGuidanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('synthetic-admin', password='synthetic-only')
        self.client.force_login(self.user)
        self.client.cookies['django_language'] = 'ru'

    def test_admin_price_draft_edit_publish_and_immutable(self):
        entry = next(iter(BY_KEY.values()))
        book = PriceBook.objects.create(store_name='Synthetic', version='qa-v1', source_note='Synthetic only', price_date=date(2026, 1, 1))
        # Get the actual add/edit form, including Russian labels and guidance.
        url = reverse('admin:calculators_pricebook_change', args=[book.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Цена за единицу, ₸')
        self.assertContains(response, 'Сохранение создаёт черновик')
        # A calculator without variants uses an empty stable variant key.
        from .material_keys import variant_keys
        from .definitions import CALCULATORS
        slug = next(c['slug'] for c in CALCULATORS if variant_keys(c['slug']) == {''})
        data = {'store_name': 'Synthetic updated', 'version': 'qa-v1', 'source_note': 'Synthetic only', 'price_date': '2026-01-01',
                'entries-TOTAL_FORMS': '1', 'entries-INITIAL_FORMS': '0', 'entries-MIN_NUM_FORMS': '0', 'entries-MAX_NUM_FORMS': '1000',
                'entries-0-calculator_slug': slug, 'entries-0-variant_key': '', 'entries-0-material_key': entry['key'],
                'entries-0-unit': entry['unit'], 'entries-0-price': '12.34', 'entries-0-price_basis': 'canonical', '_save': '1'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        book.refresh_from_db()
        self.assertIsNone(book.published_at)
        self.assertEqual(book.entries.get().price, Decimal('12.34'))
        response = self.client.post(reverse('admin:calculators_pricebook_changelist'), {'action': 'activate', '_selected_action': str(book.pk), 'index': '0'}, follow=True)
        self.assertContains(response, 'Прайс опубликован. Сохранённые сметы не изменились.')
        book.refresh_from_db()
        self.assertTrue(book.is_active)
        self.assertIsNotNone(book.published_at)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(MaterialPrice.objects.get(book=book).price, Decimal('12.34'))

    def test_typed_edition_admin_forms_publish_and_reject_edit(self):
        fixtures = [
            (SelfLevelMixEdition, {'consumption': '15.50', 'source_date': '2026-01-01'}),
            (DemolitionFilmEdition, {'consumption': '1.30', 'source_date': '2026-01-01'}),
            (RenovationRateEdition, {'economy_rate': '100', 'standard_rate': '200', 'premium_rate': '300', 'effective_date': '2026-01-01'}),
        ]
        for model, values in fixtures:
            with self.subTest(model=model.__name__):
                prefix = 'admin:calculators_' + model._meta.model_name
                response = self.client.get(reverse(prefix + '_add'))
                self.assertContains(response, 'Источник и область применения')
                self.assertContains(response, 'Публикация')
                data = {'version': model.__name__ + '-qa', 'source_note': 'Synthetic only', **values, '_save': '1'}
                self.assertEqual(self.client.post(reverse(prefix + '_add'), data).status_code, 302)
                obj = model.objects.get(version=data['version'])
                self.assertIsNone(obj.published_at)
                self.assertEqual(self.client.post(reverse(prefix + '_changelist'), {'action': 'activate', '_selected_action': str(obj.pk), 'index': '0'}).status_code, 302)
                obj.refresh_from_db()
                self.assertTrue(obj.is_active)
                self.assertEqual(self.client.post(reverse(prefix + '_change', args=[obj.pk]), data).status_code, 403)

    def test_wrong_unit_has_readable_error(self):
        from .admin import MaterialPriceForm
        row = next(iter(BY_KEY.values()))
        form = MaterialPriceForm(data={'calculator_slug': 'malyarka', 'variant_key': '', 'material_key': row['key'], 'unit': 'wrong', 'price': '12'})
        self.assertFalse(form.is_valid())
        self.assertIn('единица не совпадает', str(form.errors))
