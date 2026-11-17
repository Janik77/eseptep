from datetime import date
from decimal import Decimal
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from calculators.models import SelfLevelMixEdition
from calculators.services import calculate_materials,save_calculation_for_user
from calculators.self_level_parameters import LEGACY_VERSION
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data
from calculators.pricing import attach_quotation
from accounts.models import UserProfile,ClientProject,Calculation

class IndependentSelfLevelAudit(TestCase):
 def setUp(self):
  self.user=User.objects.create_user('selflevel-audit')
  UserProfile.objects.create(user=self.user,role='client')
  self.project=ClientProject.objects.create(user=self.user,title='Synthetic',area_m2=60,rooms=2)
  self.definition=CALCULATORS_BY_SLUG['nalivnoy-pol']
  self.data={**_get_form_data(self.definition,None),'area':'36.5','thickness':'2'}
 def edition(self,v='independent-consumption-v1',value='20.00'):
  return SelfLevelMixEdition.objects.create(version=v,source_note='<script>bad()</script>',source_date=date(2026,1,1),consumption=Decimal(value),is_active=True,published_at=timezone.now())
 def test_only_mixture_quantity_and_derived_totals_change(self):
  before=calculate_materials(self.definition,self.data)
  self.edition()
  after=calculate_materials(self.definition,self.data)
  self.assertEqual(after['materials'][1:],before['materials'][1:])
  self.assertEqual(before['materials'][0]['quantity'],44)
  self.assertEqual(after['materials'][0]['quantity'],59)
  self.assertEqual(after['parameter_snapshot']['unit'],'kg_per_m2_cm')
  self.assertEqual(after['parameter_snapshot']['bag_mass_kg'],25)
 def test_saved_snapshot_stale_save_and_other_calculator_isolation(self):
  before={slug:calculate_materials(d,_get_form_data(d,None)) for slug,d in CALCULATORS_BY_SLUG.items() if slug!='nalivnoy-pol'}
  self.edition()
  result=calculate_materials(self.definition,self.data);attach_quotation('nalivnoy-pol',result)
  _,saved=save_calculation_for_user(self.user,'nalivnoy-pol',result,self.project.pk)
  old=deepcopy(saved.result_data)
  SelfLevelMixEdition.objects.update(is_active=False)
  self.edition('independent-v2','16.75')
  with self.assertRaises(ValidationError):save_calculation_for_user(self.user,'nalivnoy-pol',result,self.project.pk)
  self.assertEqual(Calculation.objects.count(),1)
  saved.refresh_from_db();self.assertEqual(saved.result_data,old)
  for slug,d in CALCULATORS_BY_SLUG.items():
   if slug!='nalivnoy-pol':self.assertEqual(calculate_materials(d,_get_form_data(d,None)),before[slug],slug)
 def test_unknown_unit_range_reserved_version_rejected(self):
  for override in [{'unit':'kg_per_m2_mm'},{'unit':'kg_per_m3'},{'consumption':Decimal('0')},{'consumption':Decimal('-1')},{'consumption':Decimal('100')},{'consumption':Decimal('1.001')},{'version':LEGACY_VERSION}]:
   values=dict(version='test',source_note='Synthetic only',source_date=date(2026,1,1),consumption=Decimal('15'))
   values.update(override)
   with self.assertRaises(ValidationError):SelfLevelMixEdition(**values).full_clean()
 def test_public_source_escape_and_nonstaff_no_mutation(self):
  edition=self.edition()
  self.client.force_login(self.user)
  response=self.client.post('/calculators/nalivnoy-pol/',self.data)
  self.assertContains(response,'&lt;script&gt;bad()&lt;/script&gt;')
  self.assertNotContains(response,'<script>bad()</script>')
  before=list(SelfLevelMixEdition.objects.values())
  response=self.client.post('/admin/calculators/selflevelmixedition/',{'action':'deactivate','_selected_action':[edition.pk]})
  self.assertEqual(response.status_code,302)
  self.assertEqual(list(SelfLevelMixEdition.objects.values()),before)
 def test_published_admin_post_cannot_modify_parameter(self):
  edition=self.edition()
  administrator=User.objects.create_superuser('selflevel-audit-admin','a@example.test','Synthetic-Only')
  self.client.force_login(administrator)
  response=self.client.post(f'/admin/calculators/selflevelmixedition/{edition.pk}/change/',{'consumption':'99.99','version':edition.version,'source_note':'mutate','source_date':'2026-01-01'})
  self.assertEqual(response.status_code,403)
  edition.refresh_from_db();self.assertEqual(edition.consumption,Decimal('20.00'))
