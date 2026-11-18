from calculators.submission_test_helpers import post_result
"""Independent synthetic price audit; does not access real store data."""
from datetime import date
from decimal import Decimal
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import UserProfile, ClientProject
from calculators.models import PriceBook, MaterialPrice
from calculators.material_keys import material_key
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data
from calculators.services import calculate_materials
from calculators.pricing import attach_quotation

class IndependentPriceAudit(TestCase):
 def setUp(self):
  self.definition=CALCULATORS_BY_SLUG['plitka-keramogranit']
  self.data={**_get_form_data(self.definition,None),'area':'36.5'}
  self.user=User.objects.create_user('audit-client'); UserProfile.objects.create(user=self.user,role='client')
  self.project=ClientProject.objects.create(user=self.user,title='User title Ә',city='Test',area_m2=40,rooms=1)
  self.client.force_login(self.user)
 def make_book(self,version,price):
  book=PriceBook.objects.create(store_name='<script>store()</script>',version=version,source_note='<script>source()</script>',price_date=date(2026,1,1),published_at=timezone.now(),is_active=True)
  result=calculate_materials(self.definition,self.data)
  for variant in result['variants']:
   for row in variant['materials']:
    MaterialPrice.objects.create(book=book,calculator_slug=self.definition['slug'],variant_key=variant['key'],material_key=material_key(row['title'],row['unit']),unit=row['unit'],price=price)
  return book
 def test_snapshot_survives_new_price_and_stale_post_creates_nothing(self):
  first=self.make_book('audit-v1',Decimal('12.34'))
  data={**self.data,'action':'save_estimate','project_id':self.project.pk,'price_book_version':'audit-v1','selected_variant':'business'}
  response=post_result(self.client, '/calculators/plitka-keramogranit/',data)
  self.assertEqual(response.status_code,302)
  saved=self.project.calculations.get(); snapshot=deepcopy(saved.result_data)
  self.assertEqual(snapshot['admin_quote']['variant_key'],'business')
  total=sum(Decimal(row['line_total']) for row in snapshot['admin_quote']['rows'])
  self.assertEqual(total,Decimal(snapshot['admin_quote']['subtotal']))
  first.is_active=False;first.save()
  second=self.make_book('audit-v2',Decimal('31.87'))
  response=post_result(self.client, '/calculators/plitka-keramogranit/',data)
  self.assertEqual(response.status_code,200);self.assertEqual(self.project.calculations.count(),1)
  saved.refresh_from_db();self.assertEqual(saved.result_data,snapshot)
  for lang in ['ru','kk']:
   self.client.cookies['django_language']=lang
   page=self.client.get(f'/accounts/calculations/{saved.pk}/')
   self.assertContains(page,'audit-v1');self.assertNotContains(page,'audit-v2')
   self.assertNotContains(page,'<script>store()</script>');self.assertContains(page,'&lt;script&gt;store()&lt;/script&gt;')
  saved.refresh_from_db();self.assertEqual(saved.result_data,snapshot)
 def test_nonstaff_cannot_publish_admin_price(self):
  book=self.make_book('admin-denial',Decimal('12.34'));book.is_active=False;book.published_at=None;book.save()
  response=post_result(self.client, '/admin/calculators/pricebook/',{'action':'activate','_selected_action':str(book.pk)})
  self.assertEqual(response.status_code,302);book.refresh_from_db();self.assertFalse(book.is_active);self.assertIsNone(book.published_at)
