from copy import deepcopy
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone, translation
from pypdf import PdfReader

from calculators.models import MaterialPrice, PriceBook
from calculators.price_import import HEADERS, import_floor_prices, parse_floor_prices
from calculators.pricing import quotation
from projects.whole_pdf import build_pdf
from projects.whole_plan import calculate_snapshot


DATA = ','.join(HEADERS) + '\n' + """laminate,м²,pack,2.2,102
underlay,м²,canonical,,2
skirting,м,canonical,,3
tile_60x60,м²,pack,1.44,9.70
"""
META = dict(store='Synthetic shop', version='synthetic-floor-v1', source='Synthetic test price list',
            date_text='2026-11-20')


class FloorPriceImportTests(TestCase):
    def publish(self, book):
        # This is deliberately separate from import (production publication uses admin).
        PriceBook.objects.filter(is_active=True).update(is_active=False)
        book.is_active, book.published_at = True, timezone.now()
        book.save(update_fields=['is_active', 'published_at'])

    def test_preview_and_draft_never_publish(self):
        self.assertEqual(import_floor_prices(DATA.encode(), **META), (None, 4))
        self.assertFalse(PriceBook.objects.exists())
        book, count = import_floor_prices(DATA.encode(), write=True, **META)
        self.assertEqual(count, 4)
        self.assertFalse(book.is_active)
        self.assertIsNone(book.published_at)
        self.assertEqual(book.entries.get(material_key='mat_0067').pack_coverage, Decimal('2.2'))
        with self.assertRaises(ValidationError):
            import_floor_prices(DATA.encode(), write=True, **META)
        self.assertEqual(PriceBook.objects.count(), 1)

    def test_bad_row_does_not_leave_partial_draft(self):
        for row in ('unknown,м²,canonical,,1', 'underlay,упак,pack,2,1',
                    'underlay,м²,pack,,1', 'underlay,м²,pack,0,1',
                    'underlay,м²,pack,2.22222,1', 'underlay,м²,canonical,0,1',
                    'underlay,м²,canonical,,NaN', 'underlay,м²,canonical,,0',
                    'underlay,м²,canonical,,12345678901', 'underlay,м²,canonical,,-1',
                    'laminate,м²,canonical,,1'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                suffix = DATA.splitlines()[0] + '\nlaminate,м²,pack,2.2,102\n' + row
                import_floor_prices(suffix.encode(), write=True, **META)
            self.assertFalse(PriceBook.objects.exists())
        self.assertEqual(parse_floor_prices((DATA.splitlines()[0]+'\nlaminate,м²,pack,"2,2","3,50"').encode())[0]['price'], Decimal('3.50'))

    def test_pack_rounding_is_opt_in_and_boundary_exact(self):
        book, _ = import_floor_prices(DATA.encode(), write=True, **META)
        for qty, pack_count in [('4.3999', '2'), ('4.4', '2'), ('4.4001', '3')]:
            materials = [{'title':'Ламинат', 'unit':'м²', 'quantity':qty}]
            plain = quotation('laminat-spc-parket', '', materials, book)
            self.assertEqual(plain['rows'], [])
            quote = quotation('laminat-spc-parket', '', materials, book, include_packs=True)
            self.assertEqual(quote['rows'][0]['purchase_quantity'], pack_count)

    def test_grouped_pack_cost_and_pdf_use_frozen_values(self):
        draft, _ = import_floor_prices(DATA.encode(), write=True, **META)
        self.publish(draft)
        rooms = [{'index':i, 'name':f'Комната {i+1}', 'area':'24', 'finish':'laminate',
                  'finish_source':'user'} for i in range(2)]
        snapshot = calculate_snapshot(rooms, 1)
        laminate = next(row for row in snapshot['procurement'] if row['material_key']=='mat_0067')
        self.assertEqual(Decimal(laminate['quantity']), Decimal('51'))  # includes existing reserve
        self.assertEqual((laminate['purchase_unit'], laminate['purchase_quantity'], laminate['pack_coverage']),
                         ('pack','24','2.2'))
        self.assertEqual(laminate['line_total'], '2448.00')
        self.assertTrue(any(row['line_total'] is None for row in snapshot['procurement']))
        for room in snapshot['rooms']:
            allocated = next(row for row in room['materials'] if row['material_key']=='mat_0067')
            self.assertNotIn('purchase_quantity', allocated)
            self.assertEqual(allocated['line_total'], '1224.00')
        copy = deepcopy(snapshot)
        newer, _ = import_floor_prices(DATA.replace('2.2,102','2.2,200').encode(), write=True,
                                      **{**META,'version':'synthetic-floor-v2'})
        self.publish(newer)
        self.assertNotEqual(calculate_snapshot(rooms, 1)['priced_subtotal'], snapshot['priced_subtotal'])
        self.assertEqual(snapshot, copy)
        with translation.override('ru'):
            content = build_pdf(SimpleNamespace(snapshot=snapshot, pk=1, created_at=datetime.now(dt_timezone.utc)))
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
        self.assertIn('24 упак.',text)
        self.assertIn('2448.00',text)
        self.assertIn(snapshot['priced_subtotal'],text)

    def test_existing_admin_import_permission_preview_and_draft_only(self):
        from django.contrib.auth.models import User
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse
        staff = User.objects.create_user('limited', is_staff=True)
        editor = User.objects.create_superuser('price-editor','editor@example.test','unused-synthetic-passphrase')
        url = reverse('admin:calculators_pricebook_import_csv')
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(editor)
        self.assertContains(self.client.get(reverse('admin:calculators_pricebook_changelist')),url)
        page = self.client.post(url, {**{k:META[k] for k in ['store','source','version']},
            'date':META['date_text'],'file':SimpleUploadedFile('synthetic.csv',DATA.encode())})
        self.assertContains(page,'Проверено строк')
        self.assertFalse(PriceBook.objects.exists())
        token=page.context['token']
        self.assertEqual(self.client.post(url,{'confirm':'yes','token':token}).status_code,302)
        book=PriceBook.objects.get();self.assertFalse(book.is_active);self.assertIsNone(book.published_at)
        self.assertEqual(self.client.post(url,{'confirm':'yes','token':token}).status_code,400)
        self.assertEqual(PriceBook.objects.count(),1)
