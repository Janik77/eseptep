from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override
from pypdf import PdfReader

from accounts.models import Calculation, ClientProject
from .definitions import CALCULATORS_BY_SLUG
from .services import calculate_materials
from .pdf import build_saved_pdf


class SavedPdfTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('pdf-owner')
        project = ClientProject.objects.create(user=self.owner,title='Ә Ғ Қ Ң Ө Ұ Ү Һ І · demo',city='Шымкент',area_m2=Decimal('36.5'),rooms=2)
        self.result = calculate_materials(CALCULATORS_BY_SLUG['plitka-keramogranit'],{'area':'36.5','zone':'floor','tile_format':'60x60','selected_variant':'comfort'})
        rows = self.result['materials']
        quote = {'store_name':'DEMO store','version':'demo-price-v1','source_note':'Demo prices only','price_date':'2026-11-18','coverage':3,'required':5,'complete':False,'subtotal':'123.45',
                 'rows':[{'material_title':row['title'],'quantity':str(row['quantity']),'unit_label':row['unit'],'line_total':'41.15'} for row in rows[:3]],
                 'missing':[{'material_title':row['title'],'quantity':str(row['quantity']),'unit_label':row['unit']} for row in rows[3:]]}
        self.calculation = Calculation.objects.create(project=project,calculator_slug='plitka-keramogranit',area_m2=Decimal('36.5'),rooms=1,thickness=1,segment='comfort',materials_total=self.result['materials_total'],grand_total=self.result['grand_total'],
            result_data={'input':{'area':'36.5','zone':'floor','tile_format':'60x60'},'materials':rows,'admin_quote':quote,'selected_variant_label':'Комфорт','plan_source':{'name':'Ванная','area':'36.5'}})
        self.url = reverse('calculators:saved_pdf',args=[self.calculation.pk])

    def text(self, data):
        return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)

    def test_36_5_source_does_not_use_purchase_rounding(self):
        metric = next(m for m in self.result['metrics'] if m['label']=='Площадь укладки')
        self.assertEqual(metric['value'],36.5)
        self.assertEqual([r['quantity'] for r in self.result['materials']], [42, 10, 7, 15, 1278])
        self.assertEqual(self.result['grand_total'],593060)
        self.assertEqual(self.result['meta']['area'],36.5)
        self.assertEqual(self.result['meta']['input']['area'],'36.5')
        for row in self.result['materials']:
            self.assertEqual(row['quantity_basis']['area'],'36.5')
            self.assertEqual(row['quantity_basis']['mode'],'ceiling')

    def test_owner_export_contains_saved_precision_price_missing_and_kazakh_glyphs(self):
        self.client.force_login(self.owner)
        with override('ru'), patch('calculators.pricing.quotation',side_effect=AssertionError('Must not recalculate')):
            response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('no-store',response['Cache-Control'])
        text=self.text(response.content)
        for value in ['36,5','123,45','demo-price-v1','Цена по запросу','Ә Ғ Қ Ң Ө Ұ Ү Һ І']:
            self.assertIn(value,text)
        self.assertNotIn('36 м²',text)
        self.assertIn('3 из 5',text)
        self.assertEqual(self.calculation.result_data['admin_quote']['subtotal'],'123.45')

    def test_owner_only_and_get_only(self):
        self.assertEqual(self.client.get(self.url).status_code,302)
        self.client.force_login(User.objects.create_user('pdf-other'))
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url).status_code,405)
        self.assertEqual(self.client.get(reverse('calculators:saved_pdf',args=['abc'])).status_code,404)

    def test_both_languages_snapshot_unchanged(self):
        snapshot = self.calculation.result_data.copy()
        for lang in ('ru','kk'):
            with override(lang):
                text=self.text(build_saved_pdf(self.calculation))
            self.assertIn('36,5',text)
            self.assertIn('Ә Ғ Қ Ң Ө Ұ Ү Һ І',text)
            self.assertIn('123,45',text)
        self.assertEqual(self.calculation.result_data,snapshot)

    def test_rendered_parameters_do_not_repeat_input_area_or_zone(self):
        response=self.client.post(reverse('calculators:detail',args=['plitka-keramogranit']),{'area':'36.5','zone':'floor','tile_format':'60x60'})
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'36 м²')
        metrics=response.context['result']['metrics']
        self.assertFalse(any(m['label'] in ('Площадь укладки','Зона','Формат плитки') for m in metrics))
