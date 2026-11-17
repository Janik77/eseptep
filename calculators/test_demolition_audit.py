from datetime import date
from decimal import Decimal
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from calculators.models import DemolitionFilmEdition
from calculators.services import calculate_materials,save_calculation_for_user
from calculators.demolition_parameters import LEGACY_VERSION
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data
from accounts.models import UserProfile,ClientProject,Calculation

class IndependentDemolitionAudit(TestCase):
 def setUp(self):
  self.user=User.objects.create_user('film-audit');UserProfile.objects.create(user=self.user,role='client')
  self.project=ClientProject.objects.create(user=self.user,title='Synthetic',area_m2=42,rooms=2)
  self.definition=CALCULATORS_BY_SLUG['demontazh']
  self.data={'area':'42','demolition_type':'partial','selected_variant':'optimal'}
 def edition(self,version='film-audit-v1',value='1.30'):
  return DemolitionFilmEdition.objects.create(version=version,source_note='<script>unsafe()</script>',source_date=date(2026,1,1),consumption=Decimal(value),is_active=True,published_at=timezone.now())
 def test_all_types_variants_only_film_changes(self):
  cases=[{'area':'42','demolition_type':t,'selected_variant':v} for t in ['cosmetic','partial','full'] for v in ['base','optimal','maximum']]
  before=[calculate_materials(self.definition,data) for data in cases];self.edition()
  for data,old in zip(cases,before):
   new=calculate_materials(self.definition,data)
   self.assertEqual(new['selected_variant'],data['selected_variant'])
   self.assertEqual(new['parameter_snapshot']['unit'],'m2_per_m2')
   for a,b in zip(old['variants'],new['variants']):
    self.assertEqual(a['materials'][1]['quantity'],51)
    self.assertEqual(b['materials'][1]['quantity'],55)
    self.assertEqual(a['materials'][:1]+a['materials'][2:],b['materials'][:1]+b['materials'][2:])
    self.assertEqual(b['total']-a['total'],4*b['materials'][1]['reference_price'])
 def test_other_calculators_and_snapshots_unchanged(self):
  others={s:calculate_materials(d,_get_form_data(d,None)) for s,d in CALCULATORS_BY_SLUG.items() if s!='demontazh'}
  self.edition();r=calculate_materials(self.definition,self.data)
  _,saved=save_calculation_for_user(self.user,'demontazh',r,self.project.pk);old=deepcopy(saved.result_data)
  DemolitionFilmEdition.objects.update(is_active=False);self.edition('film-audit-v2','1.40')
  with self.assertRaises(ValidationError):save_calculation_for_user(self.user,'demontazh',r,self.project.pk)
  self.assertEqual(Calculation.objects.count(),1);saved.refresh_from_db();self.assertEqual(saved.result_data,old)
  for s,d in CALCULATORS_BY_SLUG.items():
   if s!='demontazh':self.assertEqual(calculate_materials(d,_get_form_data(d,None)),others[s])
 def test_unknown_unit_and_invalid_parameters_rejected(self):
  for override in [{'unit':'rolls'},{'unit':'m2_per_m3'},{'consumption':Decimal('0')},{'consumption':Decimal('-1')},{'consumption':Decimal('100')},{'consumption':Decimal('1.301')},{'version':LEGACY_VERSION}]:
   values=dict(version='invalid',source_note='Synthetic',source_date=date(2026,1,1),consumption=Decimal('1.20'));values.update(override)
   with self.assertRaises(ValidationError):DemolitionFilmEdition(**values).full_clean()
 def test_escaped_source_and_nonstaff_denial(self):
  e=self.edition();self.client.force_login(self.user)
  r=self.client.post('/calculators/demontazh/',self.data)
  self.assertContains(r,'&lt;script&gt;unsafe()&lt;/script&gt;');self.assertNotContains(r,'<script>unsafe()</script>')
  before=list(DemolitionFilmEdition.objects.values())
  r=self.client.post('/admin/calculators/demolitionfilmedition/',{'action':'deactivate','_selected_action':[e.pk]})
  self.assertEqual(r.status_code,302);self.assertEqual(list(DemolitionFilmEdition.objects.values()),before)
 def test_published_parameter_admin_readonly(self):
  e=self.edition();u=User.objects.create_superuser('film-audit-admin','admin@example.test','SyntheticOnly');self.client.force_login(u)
  r=self.client.post(f'/admin/calculators/demolitionfilmedition/{e.pk}/change/',{'consumption':'99.99','source_note':'changed','source_date':'2026-01-01','version':e.version})
  self.assertEqual(r.status_code,403);e.refresh_from_db();self.assertEqual(e.consumption,Decimal('1.30'))
