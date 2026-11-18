from calculators.submission_test_helpers import post_result
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
import hashlib,json
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from accounts.models import UserProfile,ClientProject,Calculation
from calculators.models import DemolitionFilmEdition
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.services import calculate_materials,save_calculation_for_user
from calculators.demolition_parameters import LEGACY_VERSION,STALE_MESSAGE
from calculators.views import _get_form_data

class DemolitionParameterTests(TestCase):
    def setUp(self):
        self.definition=CALCULATORS_BY_SLUG['demontazh']
        self.data={'area':'42','demolition_type':'partial','selected_variant':'optimal'}
        self.user=User.objects.create_user('film-client')
        UserProfile.objects.create(user=self.user,role='client')
        self.project=ClientProject.objects.create(user=self.user,title='Synthetic film',area_m2=42,rooms=1)

    def edition(self,v='film-v1',value='1.30',**extra):
        return DemolitionFilmEdition.objects.create(version=v,consumption=Decimal(value),source_note='SYNTHETIC preliminary parameter',source_date=date(2026,1,1),**extra)

    def test_45_legacy_results_exact_parity(self):
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('demolition_baseline.json').read_text())
        for case in fixture['cases']:
            result=calculate_materials(self.definition,case['input'])
            params=result.pop('parameter_snapshot')
            self.assertEqual(params['consumption'],'1.20')
            digest=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(digest,case['digest'],case['input'])
        self.assertEqual(DemolitionFilmEdition.objects.count(),0)

    def test_three_types_three_variants_only_film_and_derived_totals_change(self):
        cases=[{**self.data,'demolition_type':t,'selected_variant':v} for t in ['cosmetic','partial','full'] for v in ['base','optimal','maximum']]
        originals=[calculate_materials(self.definition,d) for d in cases]
        self.edition(is_active=True,published_at=timezone.now())
        for data,before in zip(cases,originals):
            after=calculate_materials(self.definition,data)
            for previous,current in zip(before['variants'],after['variants']):
                self.assertEqual(previous['materials'][1]['quantity'],51)
                self.assertEqual(current['materials'][1]['quantity'],55)
                self.assertEqual(previous['materials'][:1]+previous['materials'][2:],current['materials'][:1]+current['materials'][2:])
                price=previous['materials'][1]['reference_price']
                self.assertEqual(current['materials'][1]['reference_total']-previous['materials'][1]['reference_total'],4*price)
            self.assertEqual(after['materials'][1]['quantity'],55)

    def test_other_eleven_unchanged(self):
        before={slug:calculate_materials(d,_get_form_data(d,None)) for slug,d in CALCULATORS_BY_SLUG.items() if slug!='demontazh'}
        self.edition(is_active=True,published_at=timezone.now())
        for slug,expected in before.items():self.assertEqual(calculate_materials(CALCULATORS_BY_SLUG[slug],_get_form_data(CALCULATORS_BY_SLUG[slug],None)),expected)

    def test_missing_stale_token_and_forged_value_do_not_save(self):
        self.client.force_login(self.user)
        for version in [None,'old']:
            payload={**self.data,'action':'save_estimate','project_id':self.project.pk,'consumption':'999'}
            if version:payload['parameter_version']=version
            response=post_result(self.client, '/calculators/demontazh/',payload)
            self.assertContains(response,STALE_MESSAGE)
            self.assertEqual(Calculation.objects.count(),0)
        payload['parameter_version']=LEGACY_VERSION
        response=post_result(self.client, '/calculators/demontazh/',payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(Calculation.objects.get().result_data['materials'][1]['quantity'],51)

    def test_snapshot_and_legacy_read_do_not_recalculate(self):
        first=self.edition(is_active=True,published_at=timezone.now())
        result=calculate_materials(self.definition,self.data)
        _,saved=save_calculation_for_user(self.user,'demontazh',result,self.project.pk)
        snapshot=deepcopy(saved.result_data)
        first.is_active=False;first.save()
        self.edition('film-v2','1.40',is_active=True,published_at=timezone.now())
        with self.assertRaises(ValidationError):save_calculation_for_user(self.user,'demontazh',result,self.project.pk)
        self.client.force_login(self.user)
        for lang in ['ru','kk']:
            self.client.cookies['django_language']=lang
            self.assertContains(self.client.get(f'/accounts/calculations/{saved.pk}/'),'film-v1')
        saved.refresh_from_db();self.assertEqual(saved.result_data,snapshot)
        saved.result_data.pop('parameter_snapshot');saved.save(update_fields=['result_data']);old=deepcopy(saved.result_data)
        self.assertEqual(self.client.get(f'/accounts/calculations/{saved.pk}/').status_code,200)
        saved.refresh_from_db();self.assertEqual(saved.result_data,old)

    def test_invalid_units_values_and_reserved_version_rejected(self):
        for extra in [{'unit':'rolls'},{'unit':'kg_per_m2'},{'consumption':Decimal('0')},{'consumption':Decimal('-1')},{'consumption':Decimal('100')},{'consumption':Decimal('1.001')},{'consumption':Decimal('NaN')},{'consumption':Decimal('Infinity')},{'version':LEGACY_VERSION}]:
            data=dict(version='invalid',consumption=Decimal('1.20'),source_note='Synthetic',source_date=date(2026,1,1));data.update(extra)
            with self.assertRaises(ValidationError):DemolitionFilmEdition(**data).full_clean()
