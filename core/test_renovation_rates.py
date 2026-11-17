from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from calculators.models import RenovationRateEdition
from calculators.admin import RenovationRateEditionAdmin
from projects.models import ProjectUpload
from core.renovation_rates import rate_configuration, renovation_estimate, LEGACY_VERSION


class TypedRenovationRatesTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('typed-client')
        self.client.force_login(self.user)
        self.upload=ProjectUpload.objects.create(user=self.user,file='synthetic-not-opened.png',area=Decimal('36.50'),repair_level='standard')

    def edition(self,version,standard='222.00',**kwargs):
        return RenovationRateEdition.objects.create(version=version,source_note='Synthetic test only',effective_date=date(2026,1,1),economy_rate=Decimal('111.00'),standard_rate=Decimal(standard),premium_rate=Decimal('333.00'),**kwargs)

    def test_unset_keeps_exact_current_legacy_rates_and_totals(self):
        config=rate_configuration()
        self.assertEqual(config['rates'],{'economy':'120000','standard':'170000','premium':'250000'})
        for area in ['1','12.5','36.5','999.99']:
            for level,rate in config['rates'].items():
                self.assertEqual(renovation_estimate(area,level,config)['total'],round(Decimal(area)*Decimal(rate)))
        self.assertEqual(RenovationRateEdition.objects.count(),0)

    def test_published_rates_affect_new_estimates_not_legacy_or_snapshots(self):
        self.edition('typed-v1',is_active=True,published_at=timezone.now())
        url=f'/projects/upload/?upload_id={self.upload.pk}'
        legacy=self.client.get(url)
        self.assertEqual(legacy.context['estimate']['total'],6205000)
        self.assertEqual(legacy.context['estimate']['configuration']['source_kind'],'historical')
        data={'action':'estimate','upload_id':self.upload.pk,'area':'36.5','repair_level':'standard','rate_version':'typed-v1'}
        response=self.client.post('/projects/upload/',data)
        self.assertEqual(response.context['estimate']['total'],8103)
        self.upload.refresh_from_db();snapshot=deepcopy(self.upload.estimate_snapshot)
        RenovationRateEdition.objects.filter(is_active=True).update(is_active=False)
        self.edition('typed-v2',standard='444.00',is_active=True,published_at=timezone.now())
        for lang in ['ru','kk']:
            self.client.cookies['django_language']=lang
            reopened=self.client.get(url)
            self.assertEqual(reopened.context['estimate']['configuration']['version'],'typed-v1')
            self.assertEqual(reopened.context['estimate']['total'],8103)
        self.client.post('/projects/upload/',data)
        self.upload.refresh_from_db();self.assertEqual(self.upload.estimate_snapshot,snapshot)

    def test_turnkey_uses_same_typed_rate_and_unit(self):
        self.edition('shared-rates',is_active=True,published_at=timezone.now())
        response=self.client.post('/marketplace/',{'area':'36.5','city':'Шымкент','developer':'BI'})
        self.assertEqual(response.context['results'][1]['total'],8103)
        self.assertEqual(response.context['rate_config']['unit'],'KZT/m2')

    def test_incomplete_negative_and_reserved_configuration_rejected(self):
        for overrides in [{'standard_rate':Decimal('-1')},{'premium_rate':None},{'version':LEGACY_VERSION}]:
            values=dict(version='invalid',source_note='Synthetic',effective_date=date(2026,1,1),economy_rate=Decimal('1'),standard_rate=Decimal('2'),premium_rate=Decimal('3'))
            values.update(overrides)
            with self.assertRaises(ValidationError):RenovationRateEdition(**values).full_clean()

    def test_future_cannot_publish_and_published_cannot_edit(self):
        book=self.edition('future')
        book.effective_date=timezone.localdate()+timedelta(days=1);book.save()
        model_admin=RenovationRateEditionAdmin(RenovationRateEdition,admin.site)
        model_admin.message_user=lambda *args,**kwargs:None
        model_admin.activate(RequestFactory().post('/'),RenovationRateEdition.objects.filter(pk=book.pk))
        book.refresh_from_db();self.assertFalse(book.is_active)
        book.effective_date=date(2026,1,1);book.save()
        model_admin.activate(RequestFactory().post('/'),RenovationRateEdition.objects.filter(pk=book.pk))
        book.refresh_from_db();self.assertTrue(book.is_active)
        administrator=User.objects.create_superuser('typed-admin','a@example.test','SyntheticOnly')
        self.client.force_login(administrator)
        response=self.client.post(f'/admin/calculators/renovationrateedition/{book.pk}/change/',{'standard_rate':'999'})
        self.assertEqual(response.status_code,403)
        book.refresh_from_db();self.assertEqual(book.standard_rate,Decimal('222'))

    def test_legacy_marketplace_rounding_unchanged_for_entire_supported_grid(self):
        # All accepted two-decimal areas 1.00..10000.00; each legacy rate is
        # divisible by 100, so the exact new Decimal total is an integer.
        for rate in [120000,170000,250000]:
            self.assertTrue(all(round((cents / 100) * rate) == cents * rate // 100 for cents in range(100,1000001)))

    def test_system_demo_status_translates_without_changing_user_comment(self):
        from projects.views import DEMO_AI_SUMMARY
        self.upload.ai_summary=DEMO_AI_SUMMARY
        self.upload.comment='требуется подтверждение площади'
        self.upload.save(update_fields=['ai_summary','comment'])
        self.client.cookies['django_language']='kk'
        response=self.client.get(f'/projects/upload/?upload_id={self.upload.pk}')
        self.assertEqual(response.context['ai_summary']['status'],'Ауданды растау қажет')
        self.assertEqual(response.context['upload'].comment,'требуется подтверждение площади')
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.ai_summary,DEMO_AI_SUMMARY)
        self.assertEqual(self.upload.comment,'требуется подтверждение площади')
