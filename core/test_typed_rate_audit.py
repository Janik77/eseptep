from datetime import date
from decimal import Decimal
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from calculators.models import RenovationRateEdition
from projects.models import ProjectUpload
from core.renovation_rates import renovation_estimate, rate_configuration

class IndependentTypedAudit(TestCase):
 def setUp(self):
  self.owner=User.objects.create_user('independent-owner')
  self.other=User.objects.create_user('independent-other')
  self.upload=ProjectUpload.objects.create(user=self.owner,file='synthetic-never-read.png',area=Decimal('1.25'),repair_level='standard')
  self.edition=RenovationRateEdition.objects.create(version='independent-v1',source_note='<script>unsafe()</script>',effective_date=date(2026,1,1),economy_rate=Decimal('1.01'),standard_rate=Decimal('2.50'),premium_rate=Decimal('3.99'),is_active=True,published_at=timezone.now())
 def test_owner_authorization_snapshot_decimal_and_escape(self):
  data={'action':'estimate','upload_id':self.upload.pk,'area':'1.25','repair_level':'standard','rate_version':self.edition.version}
  for user in [None,self.other]:
   if user:self.client.force_login(user)
   r=self.client.post('/projects/upload/',data)
   self.assertEqual(r.status_code,404)
  self.upload.refresh_from_db(); self.assertEqual(self.upload.estimate_snapshot,{})
  self.client.force_login(self.owner)
  r=self.client.post('/projects/upload/',data)
  self.assertEqual(r.status_code,200)
  self.assertContains(r,'&lt;script&gt;unsafe()&lt;/script&gt;')
  self.assertNotContains(r,'<script>unsafe()</script>')
  self.upload.refresh_from_db(); old=deepcopy(self.upload.estimate_snapshot)
  self.assertEqual(old['total'],3)
  self.assertEqual(Decimal(old['rate_per_m2']),Decimal('2.50'))
  self.assertEqual(old['configuration']['unit'],'KZT/m2')
  for lang in ['ru','kk']:
   self.client.cookies['django_language']=lang
   r=self.client.get(f'/projects/upload/?upload_id={self.upload.pk}')
   self.assertEqual(r.status_code,200)
   self.upload.refresh_from_db();self.assertEqual(self.upload.estimate_snapshot,old)
 def test_nonstaff_admin_and_invalid_input_do_not_mutate(self):
  self.client.force_login(self.owner)
  before=list(RenovationRateEdition.objects.values())
  r=self.client.post('/admin/calculators/renovationrateedition/',{'action':'deactivate','_selected_action':[self.edition.pk]})
  self.assertEqual(r.status_code,302)
  self.assertEqual(list(RenovationRateEdition.objects.values()),before)
  for area in ['NaN','Infinity','-1','0','99999999999999999999','1.001']:
   r=self.client.post('/projects/upload/',{'action':'estimate','upload_id':self.upload.pk,'area':area,'repair_level':'standard','rate_version':self.edition.version})
   self.assertEqual(r.status_code,200)
   self.assertTrue(r.context['estimate_form'].errors)
   self.upload.refresh_from_db();self.assertEqual(self.upload.estimate_snapshot,{})
 def test_decimal_rounding_edges(self):
  config=rate_configuration()
  for area in ['0.01','1','1.25','999999.99']:
   for level,rate in config['rates'].items():
    self.assertEqual(renovation_estimate(area,level,config)['total'],round(Decimal(area)*Decimal(rate)))
