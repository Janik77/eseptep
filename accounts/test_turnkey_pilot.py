from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import MasterProfile, MasterResponse, ServiceRequest, UserProfile
from calculators.models import RenovationRateEdition


@override_settings(ESEPTEP_DEMO_MODE=True, PRODUCTION=False)
class DemoTurnkeyTests(TestCase):
    def setUp(self):
        call_command('seed_meeting_demo',confirm_isolated=True,verbosity=0)
        self.owner = User.objects.get(username='demo-client@example.test')
        self.master = User.objects.get(username='demo-master@example.test')

    def quote(self, client=None):
        client = client or self.client
        seen=client.post(reverse('marketplace:home'),{'city':'Шымкент','area':'36,5'})
        standard=seen.context['results'][1]
        self.assertEqual(standard['total'],6205000)
        self.assertTrue(standard['quote_url'])
        return standard['quote_url']

    def test_guest_budget_survives_login_and_targeted_reply_round_trip(self):
        draft=self.quote()
        login=self.client.get(draft)
        self.assertEqual(login.status_code,302)
        self.assertIn('next=',login.url)
        form=self.client.get(login.url)
        self.assertContains(form,'name="next"')
        auth=self.client.post(login.url,{'username':self.owner.username,'password':'Demo-Meeting-2026!',
            'next':draft},follow=True)
        self.assertContains(auth,'ДЕМО-мастер ESEPTEP')
        token=auth.context['token']
        self.assertEqual(self.client.post(draft,{'quote':token}).status_code,400)
        self.assertEqual(ServiceRequest.objects.count(),0)
        receipt=self.client.post(draft,{'quote':token,'confirm':'yes'})
        self.assertEqual(receipt.status_code,302)
        self.assertEqual(self.client.post(draft,{'quote':token,'confirm':'yes'}).url,receipt.url)
        req=ServiceRequest.objects.get()
        self.assertEqual(req.request_snapshot['budget'],6205000)
        self.assertFalse(req.target_supplier_id)
        other=User.objects.create_user('different-master')
        UserProfile.objects.create(user=other,role='master')
        rogue=Client();rogue.force_login(other)
        reply=reverse('accounts:turnkey_reply',args=[req.pk])
        self.assertEqual(rogue.get(reply).status_code,404)
        self.assertNotContains(rogue.get(reverse('accounts:dashboard_master')),reply)
        worker=Client();worker.force_login(self.master)
        self.assertContains(worker.get(reverse('accounts:dashboard_master')),reply)
        self.assertEqual(worker.post(reverse('accounts:dashboard_master'),{'request_id':req.pk,
            'price_from':'1','message':'not allowed'}).status_code,404)
        page=worker.get(reply)
        payload={'token':page.context['token'],'price_from':'6200000,50','message':'Тестовый осмотр'}
        for _ in range(2):
            self.assertEqual(worker.post(reply,payload).status_code,302)
        self.assertEqual(MasterResponse.objects.count(),1)
        self.assertContains(self.client.get(receipt.url),'6 200 000,5')
        for language, text in [('ru','Ответ мастера'),('kk','Шебердің жауабы')]:
            self.client.cookies['django_language']=language
            self.assertContains(self.client.get(receipt.url),text)
        outsider=Client();outsider.force_login(other)
        self.assertEqual(outsider.get(receipt.url).status_code,403)

    def test_changed_rate_blocks_old_unconfirmed_request_and_production_local_flow(self):
        self.client.force_login(self.owner)
        draft=self.quote(); token=self.client.get(draft).context['token']
        RenovationRateEdition.objects.filter(is_active=True).update(is_active=False)
        RenovationRateEdition.objects.create(version='new-test',source_note='Synthetic',
            effective_date=timezone.localdate(),economy_rate=120001,standard_rate=170001,premium_rate=250001,
            is_active=True,published_at=timezone.now())
        self.assertEqual(self.client.post(draft,{'quote':token,'confirm':'yes'}).status_code,400)
        self.assertFalse(ServiceRequest.objects.exists())
        with override_settings(PRODUCTION=True):
            self.assertEqual(self.client.get(draft).status_code,404)

    def test_turnkey_can_attach_to_the_same_explicitly_enabled_project(self):
        from accounts.models import ClientProject
        from repairs.models import PilotCity, Repair
        self.client.force_login(self.owner)
        city = PilotCity.objects.create(name='Шымкент', enabled=True)
        project = ClientProject.objects.create(user=self.owner,title='Один ремонт',city='Шымкент',area_m2=36,rooms=2)
        repair = Repair.objects.create(project=project,city=city,enabled=True)
        draft = self.quote()
        preview = self.client.get(draft)
        self.assertContains(preview,'Один ремонт')
        payload={'quote':preview.context['token'],'confirm':'yes','repair_project':str(project.pk)}
        self.assertEqual(self.client.post(draft,payload).status_code,302)
        self.assertEqual(self.client.post(draft,payload).status_code,302)
        self.assertEqual(ServiceRequest.objects.get().project_id,project.pk)
        self.assertEqual(ClientProject.objects.filter(user=self.owner,title='Один ремонт').count(),1)
        repair.enabled=False
        repair.save(update_fields=['enabled'])
        self.assertNotContains(self.client.get(draft),'Один ремонт')
        self.assertEqual(self.client.post(draft,payload).status_code,404)
