from copy import deepcopy
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Calculation, ClientProject, ServiceRequest, SupplierProfile, UserProfile


@override_settings(ESEPTEP_DEMO_MODE=True, PRODUCTION=False)
class MeetingSupplierTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user('meeting-client', password='test-only')
        UserProfile.objects.create(user=self.customer, role='client')
        self.supplier_user = User.objects.create_user('demo-supplier@example.test', password='test-only')
        UserProfile.objects.create(user=self.supplier_user, role='supplier')
        self.supplier = SupplierProfile.objects.create(user=self.supplier_user, company_name='DEMO STORE', city='Шымкент', address='Тест')
        self.other_user = User.objects.create_user('other-supplier', password='test-only')
        UserProfile.objects.create(user=self.other_user, role='supplier')
        SupplierProfile.objects.create(user=self.other_user, company_name='OTHER STORE', city='Шымкент', address='Тест')
        self.project = ClientProject.objects.create(user=self.customer, title='Demo apartment', city='Шымкент', area_m2='36.50', rooms=2)
        self.data = {'input': {'area':'36.50','zone':'floor','tile_format':'60x60'}, 'selected_variant':'economy',
            'selected_variant_label':'Эконом', 'materials':[{'title':'Плитка','quantity':'42','unit':'м²','total':100}],
            'admin_quote': {'store_name':'DEMO STORE', 'version':'demo-v1', 'subtotal':'100', 'coverage':1,'required':2,
                            'rows':[], 'missing':[], 'complete':False}, 'plan_source':{'area':'36.50','confirmed':True}}
        self.calculation = Calculation.objects.create(project=self.project, calculator_slug='plitka-keramogranit',
            area_m2=Decimal('36.50'),rooms=2,thickness=0,segment='economy',grand_total=100,result_data=deepcopy(self.data))
        self.preview = reverse('accounts:supplier_request_preview',args=[self.calculation.pk])
        self.client.force_login(self.customer)

    def submit(self):
        page = self.client.get(self.preview)
        token = page.context['request_token']
        post = {'confirm':'yes','request_token':token}
        result = self.client.post(self.preview,post)
        return result,post

    def test_get_is_preview_and_requires_explicit_confirmation(self):
        page=self.client.get(self.preview)
        self.assertContains(page,'DEMO STORE')
        self.assertContains(page,'36.50')
        self.assertFalse(ServiceRequest.objects.exists())
        invalid=self.client.post(self.preview,{'request_token':page.context['request_token']})
        self.assertContains(invalid,'подтвердите отправку')
        self.assertFalse(ServiceRequest.objects.exists())

    def test_repeat_new_preview_refresh_create_exactly_one_targeted_request(self):
        response,post=self.submit()
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(self.preview,post).url,response.url)
        repeated,_=self.submit()
        self.assertEqual(repeated.url,response.url)
        self.client.get(response.url)
        service=ServiceRequest.objects.get()
        self.assertEqual(service.target_supplier,self.supplier)
        self.assertEqual(service.client,self.customer)
        self.assertEqual(service.request_snapshot['result']['plan_source']['area'],'36.50')

    def test_private_visibility_and_supplier_viewed_status(self):
        response,_=self.submit()
        service=ServiceRequest.objects.get()
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(response.url).status_code,404)
        dashboard=self.client.get(reverse('accounts:dashboard_supplier'))
        self.assertNotContains(dashboard,'Demo apartment')
        self.assertEqual(self.client.post(reverse('accounts:dashboard_supplier'),{
            'request_id':service.pk,'total_price':'100','message':'not allowed'}).status_code,404)
        self.client.force_login(self.supplier_user)
        dashboard=self.client.get(reverse('accounts:dashboard_supplier'))
        self.assertContains(dashboard,'Demo apartment')
        self.assertContains(dashboard,'42')
        self.client.get(response.url)
        service.refresh_from_db()
        self.assertEqual(service.status,'new') # read-only GET
        self.client.post(response.url,{'action':'mark_viewed'})
        self.client.post(response.url,{'action':'mark_viewed'})
        service.refresh_from_db()
        self.assertEqual(service.status,'viewed')
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(response.url),'Просмотрена')
        self.assertEqual(self.client.post(response.url,{'action':'mark_viewed'}).status_code,403)

    def test_snapshot_does_not_follow_changed_calculation_or_prices(self):
        response,_=self.submit()
        changed=deepcopy(self.data);changed['admin_quote']['subtotal']='999';changed['materials'][0]['quantity']='999'
        self.calculation.result_data=changed;self.calculation.grand_total=999;self.calculation.save()
        service=ServiceRequest.objects.get()
        self.assertEqual(service.request_snapshot['result']['materials'][0]['quantity'],'42')
        self.assertEqual(service.request_snapshot['result']['admin_quote']['subtotal'],'100')
        self.assertContains(self.client.get(response.url),'42')

    def test_owner_role_and_signed_body_boundaries(self):
        page=self.client.get(self.preview)
        token=page.context['request_token']
        self.assertContains(self.client.post(self.preview,{'confirm':'yes','request_token':token+'x'}),'подтвердите отправку')
        other=User.objects.create_user('other-client');UserProfile.objects.create(user=other,role='client')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.preview).status_code,404)
        self.assertEqual(self.client.post(self.preview,{'confirm':'yes','request_token':token}).status_code,404)
        self.client.force_login(self.supplier_user)
        self.assertEqual(self.client.get(self.preview).status_code,403)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_price_snapshot_change_invalidates_preview_not_reprices_request(self):
        page=self.client.get(self.preview)
        self.calculation.result_data['admin_quote']['version']='demo-v2';self.calculation.save()
        response=self.client.post(self.preview,{'confirm':'yes','request_token':page.context['request_token']})
        self.assertContains(response,'подтвердите отправку')
        self.assertFalse(ServiceRequest.objects.exists())

    @override_settings(ESEPTEP_DEMO_MODE=False)
    def test_disabled_without_demo_mode(self):
        self.assertEqual(self.client.get(self.preview).status_code,404)

    @override_settings(PRODUCTION=True)
    def test_disabled_in_production(self):
        self.assertEqual(self.client.get(self.preview).status_code,404)

    def test_inactive_recipient_disallows_new_request(self):
        self.supplier.is_active=False;self.supplier.save()
        self.assertEqual(self.client.get(self.preview).status_code,404)
