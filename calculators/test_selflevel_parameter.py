from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
import hashlib,json
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from accounts.models import UserProfile, ClientProject
from calculators.models import SelfLevelMixEdition
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.services import calculate_materials, save_calculation_for_user
from calculators.views import _get_form_data
from calculators.self_level_parameters import current_parameters, LEGACY_VERSION


class SelfLevelParameterTests(TestCase):
    def setUp(self):
        self.definition=CALCULATORS_BY_SLUG['nalivnoy-pol']
        self.data={'area':'36.5','thickness':'1.25'}
        self.user=User.objects.create_user('selflevel-client')
        UserProfile.objects.create(user=self.user,role='client')
        self.project=ClientProject.objects.create(user=self.user,title='Synthetic floor',city='Test',area_m2=36.5,rooms=1)

    def edition(self,version='mix-v1',value='30.00',**kwargs):
        return SelfLevelMixEdition.objects.create(version=version,consumption=Decimal(value),source_note='SYNTHETIC parameter test, not a product recommendation',source_date=date(2026,1,1),**kwargs)

    def test_default_identical_to_captured_base_results(self):
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('selflevel_baseline.json').read_text())
        for case in fixture['selflevel']:
            actual=calculate_materials(self.definition,case['input'])
            params=actual.pop('parameter_snapshot')
            self.assertEqual(actual,case['result'])
            self.assertEqual(params['consumption'],'15');self.assertEqual(params['unit'],'kg_per_m2_cm');self.assertEqual(params['bag_mass_kg'],25)
        self.assertEqual(SelfLevelMixEdition.objects.count(),0)

    def test_no_effect_on_other_eleven_calculators(self):
        self.edition(is_active=True,published_at=timezone.now())
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('selflevel_baseline.json').read_text())
        for slug,case in fixture['defaults'].items():
            if slug=='nalivnoy-pol':continue
            result=calculate_materials(CALCULATORS_BY_SLUG[slug],case['input'])
            digest=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(digest,case['digest'],slug)

    def test_only_main_mixture_quantity_changes_and_snapshot_freezes(self):
        original=calculate_materials(self.definition,self.data)
        first=self.edition(is_active=True,published_at=timezone.now())
        changed=calculate_materials(self.definition,self.data)
        self.assertEqual(original['materials'][0]['quantity'],28)
        self.assertEqual(changed['materials'][0]['quantity'],55)
        self.assertEqual(original['materials'][1:],changed['materials'][1:])
        _,saved=save_calculation_for_user(self.user,'nalivnoy-pol',changed,self.project.pk)
        snapshot=deepcopy(saved.result_data)
        first.is_active=False;first.save()
        self.edition('mix-v2','20.00',is_active=True,published_at=timezone.now())
        self.client.force_login(self.user)
        for lang in ['ru','kk']:
            self.client.cookies['django_language']=lang
            response=self.client.get(f'/accounts/calculations/{saved.pk}/')
            self.assertContains(response,'mix-v1');self.assertNotContains(response,'mix-v2')
        saved.refresh_from_db();self.assertEqual(saved.result_data,snapshot)
        with self.assertRaises(ValidationError):save_calculation_for_user(self.user,'nalivnoy-pol',changed,self.project.pk)
        self.assertEqual(self.project.calculations.count(),1)

    def test_typing_and_fixed_unit_reject_invalid_editions(self):
        for value in ['0','-1','100','0.001','NaN','Infinity']:
            row=SelfLevelMixEdition(version='invalid',consumption=Decimal(value),source_note='Synthetic',source_date=date(2026,1,1))
            with self.assertRaises(ValidationError):row.full_clean()
        row=SelfLevelMixEdition(version='wrong-unit',consumption=15,unit='kg_per_m2_mm',source_note='Synthetic',source_date=date(2026,1,1))
        with self.assertRaises(ValidationError):row.full_clean()

    def test_technical_maximum_fits_existing_saved_money_precision(self):
        self.edition(value='99.99',is_active=True,published_at=timezone.now())
        result=calculate_materials(self.definition,{'area':'10000','thickness':'20'})
        self.assertEqual(result['materials'][0]['quantity'],799920)
        self.assertLessEqual(result['grand_total'],Decimal('9999999999.99'))
        self.assertEqual(result['grand_total'],2323553760)

    def test_stale_form_and_direct_post_cannot_override_parameter(self):
        self.edition(is_active=True,published_at=timezone.now())
        self.client.force_login(self.user)
        payload={**self.data,'project_id':self.project.pk,'action':'save_estimate','parameter_version':LEGACY_VERSION,'consumption':'999'}
        response=self.client.post('/calculators/nalivnoy-pol/',payload)
        self.assertEqual(response.status_code,200);self.assertEqual(self.project.calculations.count(),0)
        self.assertEqual(response.context['result']['parameter_snapshot']['consumption'],'30.00')
        payload['parameter_version']='mix-v1'
        response=self.client.post('/calculators/nalivnoy-pol/',payload)
        self.assertEqual(response.status_code,302);self.assertEqual(self.project.calculations.count(),1)
