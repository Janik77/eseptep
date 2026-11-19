from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import signing
from .models import (UserProfile,ClientProject,SupplierProfile,ServiceRequest,
                     SavedWholeEstimate,WholeSupplierOffer,SupplierResponse)
from .whole_views import digest
from projects.models import ProjectUpload,WholePlanEstimate


@override_settings(ESEPTEP_DEMO_MODE=True,PRODUCTION=False,PLAN_AI_ENABLED=False)
class WholeSupplierTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('owner')
        self.other=User.objects.create_user('other')
        for u in (self.owner,self.other): UserProfile.objects.create(user=u,role='client')
        self.vendor=User.objects.create_user('demo-supplier@example.test')
        UserProfile.objects.create(user=self.vendor,role='supplier')
        self.supplier=SupplierProfile.objects.create(user=self.vendor,company_name='Synthetic test shop',city='Test',address='Test')
        self.foreign_vendor=User.objects.create_user('foreign-vendor')
        UserProfile.objects.create(user=self.foreign_vendor,role='supplier')
        SupplierProfile.objects.create(user=self.foreign_vendor,company_name='Other shop',city='Test',address='Test')
        self.project=ClientProject.objects.create(user=self.owner,title='Test apartment',city='Test',area_m2=72,rooms=5)
        self.other_project=ClientProject.objects.create(user=self.other,title='Private',city='Test',area_m2=30,rooms=1)
        self.upload=ProjectUpload.objects.create(user=self.owner,file='synthetic-not-read.pdf')
        self.snapshot={'version':'whole-floor-v1','rooms':[{'name':'Living','area':'18','known':True,'finish':'laminate'}],
            'known_area':'18.00','priced_subtotal':'200.00','materials_total':None,'price_source':'Synthetic prices only',
            'procurement':[{'title':'Laminate','unit':'м²','quantity':'2','unit_price':'100','line_total':'200','material_key':'m1'},
                           {'title':'Underlay','unit':'м²','quantity':'2.25','unit_price':None,'line_total':None,'material_key':'m2'}]}
        self.source=WholePlanEstimate.objects.create(upload=self.upload,fingerprint='a'*64,snapshot=deepcopy(self.snapshot))
        self.upload.ai_summary={'whole_estimate_id':self.source.pk};self.upload.save()
        self.client.force_login(self.owner)

    def saved(self):
        response=self.client.post(reverse('accounts:save_whole',args=[self.source.pk]),{'project_id':self.project.pk})
        self.assertEqual(response.status_code,302)
        return SavedWholeEstimate.objects.get()

    def requested(self):
        saved=self.saved()
        page=self.client.get(reverse('accounts:whole_preview',args=[saved.pk]))
        self.assertEqual(page.status_code,200)
        token=page.context['token']
        url=reverse('accounts:whole_preview',args=[saved.pk])
        for _ in range(2): self.assertEqual(self.client.post(url,{'token':token,'confirm':'yes'}).status_code,302)
        self.assertEqual(ServiceRequest.objects.count(),1)
        return ServiceRequest.objects.get()

    def test_save_preview_request_are_owned_immutable_and_idempotent(self):
        req=self.requested()
        saved=SavedWholeEstimate.objects.get()
        self.assertEqual(SavedWholeEstimate.objects.count(),1)
        self.client.post(reverse('accounts:save_whole',args=[self.source.pk]),{'project_id':self.project.pk})
        self.assertEqual(SavedWholeEstimate.objects.count(),1)
        before=deepcopy(req.request_snapshot)
        self.source.snapshot['procurement'][0]['unit_price']='999';self.source.save()
        from calculators.models import PriceBook
        from django.utils import timezone
        PriceBook.objects.create(store_name='New synthetic store',version='new-test-price',source_note='Test only',price_date=timezone.now().date(),published_at=timezone.now(),is_active=True)
        self.source.refresh_from_db();saved.refresh_from_db();req.refresh_from_db()
        self.assertEqual(saved.snapshot,self.snapshot)
        self.assertEqual(req.request_snapshot,before)
        self.assertEqual(self.client.get(reverse('accounts:saved_whole_pdf',args=[saved.pk])).status_code,200)
        self.assertContains(self.client.get(reverse('accounts:dashboard_client')), 'Смета и ответ магазина')
        self.assertEqual(self.client.post(reverse('accounts:save_whole',args=[self.source.pk]),{'project_id':self.other_project.pk}).status_code,404)
        self.client.force_login(self.other)
        for name,arg in [('whole_saved',saved.pk),('whole_preview',saved.pk),('saved_whole_pdf',saved.pk),('whole_request',req.pk),('whole_offer_pdf',req.pk)]:
            self.assertEqual(self.client.get(reverse('accounts:'+name,args=[arg])).status_code,404)
        self.assertEqual(self.client.post(reverse('accounts:save_whole',args=[self.source.pk]),{'project_id':self.other_project.pk}).status_code,404)
        self.client.force_login(self.foreign_vendor)
        self.assertEqual(self.client.get(reverse('accounts:whole_request',args=[req.pk])).status_code,404)

    def test_stale_revision_and_preview_fail_closed(self):
        self.upload.ai_summary={'whole_estimate_id':999};self.upload.save()
        self.assertEqual(self.client.post(reverse('accounts:save_whole',args=[self.source.pk]),{'project_id':self.project.pk}).status_code,400)
        self.upload.ai_summary={'whole_estimate_id':self.source.pk};self.upload.save()
        saved=self.saved();url=reverse('accounts:whole_preview',args=[saved.pk])
        token=self.client.get(url).context['token']
        self.project.title='Changed project';self.project.save()
        self.assertEqual(self.client.post(url,{'token':token,'confirm':'yes'}).status_code,400)
        self.assertFalse(ServiceRequest.objects.exists())
        fresh=self.client.get(url).context['token']
        self.assertEqual(self.client.post(url,{'token':fresh}).status_code,400)

    def test_line_offer_partial_unknown_zero_and_duplicate_submission(self):
        req=self.requested();self.client.force_login(self.vendor)
        url=reverse('accounts:whole_request',args=[req.pk]);page=self.client.get(url)
        token=page.context['token']
        data={'token':token,'price_0':'0','availability_0':'available','price_1':'100','availability_1':'unknown','message':'Synthetic quote only'}
        for _ in range(2):self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(WholeSupplierOffer.objects.count(),1)
        offer=WholeSupplierOffer.objects.get()
        self.assertEqual(offer.snapshot['confirmed_subtotal'],'0.00')
        self.assertIsNone(offer.snapshot['total'])
        self.assertEqual(offer.snapshot['unconfirmed'],1)
        self.assertIsNone(offer.snapshot['lines'][1]['line_total'])
        data['price_0']='999'
        self.assertEqual(self.client.post(url,data).status_code,302)
        offer.refresh_from_db();self.assertEqual(offer.snapshot['lines'][0]['unit_price'],'0')
        self.assertEqual(self.client.get(reverse('accounts:whole_offer_pdf',args=[req.pk])).status_code,200)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url),'Synthetic quote only')
        self.assertEqual(self.client.post(url,data).status_code,403)
        for language in ('ru','kk'):
            page=self.client.get(url,HTTP_ACCEPT_LANGUAGE=language)
            self.assertEqual(page.status_code,200)
            self.assertEqual(self.client.get(reverse('accounts:whole_offer_pdf',args=[req.pk]),HTTP_ACCEPT_LANGUAGE=language).status_code,200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('accounts:whole_offer_pdf',args=[req.pk])).status_code,404)

    def test_invalid_offer_and_generic_dashboard_cannot_bypass(self):
        req=self.requested();self.client.force_login(self.vendor)
        url=reverse('accounts:whole_request',args=[req.pk]);token=self.client.get(url).context['token']
        for price in ('-1','NaN','Infinity','1.234','1e999'):
            response=self.client.post(url,{'token':token,'price_0':price,'availability_0':'available'})
            self.assertEqual(response.status_code,200)
            self.assertFalse(WholeSupplierOffer.objects.exists())
            self.assertContains(response,'Проверьте цены')
        self.client.post(reverse('accounts:dashboard_supplier'),{'request_id':req.pk,'total_price':'1'})
        self.assertFalse(SupplierResponse.objects.exists())
        self.assertFalse(WholeSupplierOffer.objects.exists())
        self.supplier.is_active=False;self.supplier.save()
        self.assertEqual(self.client.post(url,{'token':token,'price_0':'1'}).status_code,404)

    def test_complete_offer_sum_comes_from_frozen_quantities_not_post(self):
        req=self.requested();self.client.force_login(self.vendor)
        url=reverse('accounts:whole_request',args=[req.pk]);token=self.client.get(url).context['token']
        data={'token':token,'price_0':'12,50','availability_0':'available','price_1':'10','availability_1':'available','quantity_0':'999999','total':'1'}
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(WholeSupplierOffer.objects.get().snapshot['total'],'47.50')

    def test_missing_confirmation_and_expired_tokens_create_nothing(self):
        saved=self.saved();url=reverse('accounts:whole_preview',args=[saved.pk])
        page=self.client.get(url);token=page.context['token']
        with patch('django.core.signing.time.time',return_value=1):
            old=signing.dumps(signing.loads(token,salt='whole-request-v1'),salt='whole-request-v1')
        self.assertEqual(self.client.post(url,{'token':old,'confirm':'yes'}).status_code,400)
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertEqual(self.client.get(reverse('accounts:save_whole',args=[self.source.pk])).status_code,200)
        self.assertEqual(SavedWholeEstimate.objects.count(),1)

    def test_csrf_is_required_for_mutations(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(reverse('accounts:save_whole',args=[self.source.pk]),{'project_id':self.project.pk}).status_code,403)
        self.assertFalse(SavedWholeEstimate.objects.exists())
