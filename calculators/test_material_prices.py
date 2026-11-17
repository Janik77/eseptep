from copy import deepcopy
from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserProfile, SupplierProfile, SupplierMaterial, ClientProject
from calculators.models import PriceBook, MaterialPrice
from calculators.material_keys import material_key
from calculators.offers import material_offers
from calculators.pricing import quotation, attach_quotation
from calculators.services import calculate_materials, save_calculation_for_user
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data


class MaterialPricingTests(TestCase):
    def setUp(self):
        self.definition = CALCULATORS_BY_SLUG['plitka-keramogranit']
        self.result = calculate_materials(self.definition, _get_form_data(self.definition, None))
        self.row = self.result['materials'][0]
        self.owner = User.objects.create_user('supplier-test', password='test-only')
        UserProfile.objects.create(user=self.owner, role='supplier')
        self.supplier = SupplierProfile.objects.create(user=self.owner, company_name='Synthetic store', city='Test', address='Test', whatsapp='PRIVATE-NOT-FOR-DISPLAY')
        self.product = SupplierMaterial.objects.create(supplier=self.supplier, name=self.row['title'], unit=self.row['unit'], price=Decimal('12.34'), category='Synthetic', stock_status='Supplier statement')

    def book(self):
        return PriceBook.objects.create(store_name='Synthetic store', version='synthetic-v1', source_note='Synthetic tests only', price_date=date(2026, 1, 1), published_at=timezone.now(), is_active=True)

    def test_publication_is_explicit_and_no_personal_contact_exposed(self):
        self.assertEqual(material_offers([self.row])[0]['products'], [])
        self.product.is_published = True; self.product.save()
        products = material_offers([self.row])[0]['products']
        self.assertEqual(len(products), 1)
        self.assertNotIn('PRIVATE', str(products))
        self.supplier.is_active = False; self.supplier.save()
        self.assertEqual(material_offers([self.row])[0]['products'], [])

    def test_unit_and_name_mismatch_fail_closed(self):
        self.product.is_published = True; self.product.unit='wrong-unit'; self.product.save()
        self.assertEqual(material_offers([self.row])[0]['products'], [])

    def test_no_price_book_does_not_change_reference_formulas(self):
        original = deepcopy(self.result)
        attach_quotation('plitka-keramogranit', self.result)
        self.assertIsNone(self.result['admin_quote'])
        for key in ['materials', 'grand_total', 'additional_total', 'reference_total']:
            self.assertEqual(original[key], self.result[key])

    def test_scoped_decimal_partial_and_complete_quote(self):
        book = self.book()
        row = {**self.row, 'quantity': 3}
        MaterialPrice.objects.create(book=book, calculator_slug='plitka-keramogranit', variant_key='comfort', material_key=material_key(row['title'],row['unit']), unit=row['unit'], price=Decimal('12.34'))
        quote = quotation('plitka-keramogranit', 'comfort', [row], book)
        self.assertTrue(quote['complete']); self.assertEqual(quote['subtotal'], '37.02')
        for slug,variant in [('plitka-keramogranit','business'),('malyarka','comfort')]:
            other = quotation(slug,variant,[row],book)
            self.assertFalse(other['complete']); self.assertEqual(other['coverage'],0)
        unknown = {**row, 'title':'Unregistered specification'}
        self.assertFalse(quotation('plitka-keramogranit','comfort',[row,unknown],book)['complete'])

    def test_saved_quote_is_historical_snapshot(self):
        book=self.book()
        MaterialPrice.objects.create(book=book, calculator_slug='plitka-keramogranit', variant_key=self.result['selected_variant'], material_key=material_key(self.row['title'],self.row['unit']), unit=self.row['unit'], price=Decimal('12.34'))
        attach_quotation('plitka-keramogranit',self.result)
        client=User.objects.create_user('client-test');UserProfile.objects.create(user=client,role='client')
        project=ClientProject.objects.create(user=client,title='Synthetic',city='Test',area_m2=60,rooms=2)
        _,saved=save_calculation_for_user(client,'plitka-keramogranit',self.result,project.pk)
        before=deepcopy(saved.result_data)
        book.is_active=False;book.save()
        saved.refresh_from_db()
        self.assertEqual(saved.result_data,before)
        self.assertEqual(saved.result_data['admin_quote']['version'],'synthetic-v1')

    def test_supplier_can_edit_own_but_not_other_material(self):
        url=reverse('accounts:supplier_material_edit',args=[self.product.pk])
        self.client.force_login(self.owner);self.assertEqual(self.client.get(url).status_code,200)
        other=User.objects.create_user('other');UserProfile.objects.create(user=other,role='supplier')
        SupplierProfile.objects.create(user=other,company_name='Other')
        self.client.force_login(other);self.assertEqual(self.client.get(url).status_code,404)
        self.client.logout();self.assertEqual(self.client.get(url).status_code,302)

    def test_live_result_has_real_empty_states_in_both_languages(self):
        for language in ['ru','kk']:
            self.client.cookies['django_language']=language
            response=self.client.post(reverse('calculators:detail',args=['plitka-keramogranit']),_get_form_data(self.definition,None))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'class="material-offers admin-quote"')
            self.assertNotContains(response,'PRIVATE-NOT-FOR-DISPLAY')

    def test_changed_price_version_prevents_silent_save(self):
        self.book()
        client=User.objects.create_user('save-client');UserProfile.objects.create(user=client,role='client')
        project=ClientProject.objects.create(user=client,title='Synthetic',city='Test',area_m2=60,rooms=2)
        self.client.force_login(client)
        data={**_get_form_data(self.definition,None),'action':'save_estimate','project_id':str(project.pk),'price_book_version':'old-version'}
        response=self.client.post(reverse('calculators:detail',args=['plitka-keramogranit']),data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(project.calculations.count(),0)
        data['price_book_version']='synthetic-v1'
        response=self.client.post(reverse('calculators:detail',args=['plitka-keramogranit']),data)
        self.assertEqual(response.status_code,302)
        self.assertEqual(project.calculations.count(),1)
