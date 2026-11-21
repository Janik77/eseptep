import io
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import ClientProject, MasterProfile, MasterResponse, SavedWholeEstimate, ServiceRequest, SupplierProfile, UserProfile, WholeSupplierOffer
from projects.models import WholePlanEstimate, ProjectUpload
from .models import Agreement, Delivery, Event, Photo, PilotCity, Problem, Repair, Stage, Terms
from .services import offer_rows, offer_token, receipt_balance


class RepairFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = cls.user_for('buyer', 'client')
        cls.shop = cls.user_for('shop', 'supplier')
        cls.master = cls.user_for('master', 'master')
        cls.reviewer = cls.user_for('reviewer', 'admin')
        cls.stranger = cls.user_for('stranger', 'client')
        cls.other_shop = cls.user_for('other-shop', 'supplier')
        cls.project = ClientProject.objects.create(user=cls.buyer, title='Пилот 12', city='Шымкент', area_m2=40, rooms=2)
        cls.city = PilotCity.objects.create(name='Шымкент', enabled=True)
        cls.repair = Repair.objects.create(project=cls.project, city=cls.city, reviewer=cls.reviewer,
                                           enabled=True, delivery_address='ТОЧНЫЙ-ТЕСТОВЫЙ-АДРЕС')
        cls.supplier = SupplierProfile.objects.create(user=cls.shop, company_name='Пилотный магазин', city='Шымкент', address='')
        cls.contractor = MasterProfile.objects.create(user=cls.master, full_name='Пилотный мастер', city='Шымкент', specialization='floor')
        plan = ProjectUpload.objects.create(user=cls.buyer, file="synthetic-only.pdf")
        # Baseline model carries neutral immutable snapshot fields; no AI calls in this flow.
        whole = WholePlanEstimate.objects.create(upload=plan, fingerprint="synthetic", snapshot={})
        saved = SavedWholeEstimate.objects.create(project=cls.project, source=whole, snapshot={})
        material_request = ServiceRequest.objects.create(client=cls.buyer, project=cls.project, target_supplier=cls.supplier,
            whole_estimate=saved, request_type='supplier', status='responded')
        cls.supplier_offer = WholeSupplierOffer.objects.create(request=material_request, supplier=cls.supplier,
            snapshot={'total':'12000.00', 'lines':[{'line_id':'1','quantity':'12','purchase_quantity':'12','name':'Ламинат',
                'purchase_unit':'упак.', 'unit_price':'1000.00','availability':'available'}]})
        work_request = ServiceRequest.objects.create(client=cls.buyer, project=cls.project, target_master=cls.contractor,
            request_type='full_repair', status='responded')
        cls.master_reply = MasterResponse.objects.create(request=work_request, master=cls.contractor, price_from='80000.00', message='Укладка пола')

    @staticmethod
    def user_for(name, role):
        user = get_user_model().objects.create_user(username=name)
        UserProfile.objects.update_or_create(user=user, defaults={'role':role})
        return user

    def browser(self, user):
        c = Client()
        c.force_login(user)
        return c

    def url(self, name='action'):
        return reverse(f'repairs:{name}', args=[self.project.pk])

    def post(self, browser, action, token=None, status=302, **kwargs):
        response = browser.post(self.url(), {'action':action, 'token':token or str(uuid.uuid4()), **kwargs})
        self.assertEqual(response.status_code, status)
        return response

    def accept(self, kind):
        buyer = self.browser(self.buyer)
        row = next(r for r in offer_rows(self.repair) if r['kind'] == kind)
        token = str(uuid.uuid4())
        params = dict(kind=kind, offer_id=row['id'], confirm='yes', offer_token=offer_token(self.repair, self.buyer, row))
        self.post(buyer,'accept_offer',token=token,**params)
        self.post(buyer,'accept_offer',token=token,**params)
        self.post(buyer,'accept_offer',token=token,status=400,**{**params, 'confirm':'no'})
        a = Agreement.objects.get(kind=kind)
        self.assertEqual(a.events.filter(action='accept_offer').count(), 1)
        self.assertEqual(a.request.status, 'accepted')
        return a

    @staticmethod
    def pic():
        b = io.BytesIO()
        Image.new('RGB',(20,20),'red').save(b,'PNG')
        return SimpleUploadedFile('demo.png', b.getvalue(), 'image/png')

    def test_materials_works_partial_damage_replay_repair_and_dispute(self):
        material, work = self.accept('materials'), self.accept('works')
        buyer, shop, master, reviewer = (self.browser(x) for x in (self.buyer,self.shop,self.master,self.reviewer))
        self.assertNotContains(shop.get(self.url('detail')), 'Пилотный мастер')
        self.assertNotContains(master.get(self.url('detail')), 'Пилотный магазин')
        self.assertNotContains(shop.get(self.url('detail')), 'ТОЧНЫЙ-ТЕСТОВЫЙ-АДРЕС')
        window = dict(window_start='2030-01-09T10:00',window_end='2030-01-09T13:00')
        self.post(shop,'schedule_delivery',agreement_id=material.pk,qty_1='12',**window)
        delivery = Delivery.objects.get()
        self.assertContains(shop.get(self.url('detail')), 'ТОЧНЫЙ-ТЕСТОВЫЙ-АДРЕС')
        self.assertNotContains(master.get(self.url('detail')), 'ТОЧНЫЙ-ТЕСТОВЫЙ-АДРЕС')
        self.assertNotContains(reviewer.get(self.url('detail')), 'ТОЧНЫЙ-ТЕСТОВЫЙ-АДРЕС')
        self.post(master,'report_issue',target_kind='delivery',target_id=delivery.pk,comment='Wrong scope',status=404)
        token = str(uuid.uuid4())
        self.post(buyer,'confirm_delivery',token=token,delivery_id=delivery.pk,received_1='10',damaged_1='0')
        self.post(buyer,'confirm_delivery',token=token,delivery_id=delivery.pk,received_1='10',damaged_1='0')
        self.assertEqual(material.events.filter(action='confirm_delivery').count(),1)
        self.assertEqual(receipt_balance(material),{'1':Decimal(2)})
        self.post(shop,'schedule_delivery',agreement_id=material.pk,qty_1='3',status=400,**window)
        self.post(shop,'schedule_delivery',agreement_id=material.pk,qty_1='2',**window)
        left = material.deliveries.latest('pk')
        self.post(buyer,'confirm_delivery',delivery_id=left.pk,received_1='2',damaged_1='0')
        self.assertEqual(receipt_balance(material),{'1':Decimal(0)})
        self.post(master,'plan_stage',agreement_id=work.pk,title='Укладка в спальне',due_on='2030-01-10')
        stage = Stage.objects.get()
        self.post(master,'submit_stage',stage_id=stage.pk,comment='Готово',photo=self.pic())
        img = Photo.objects.get()
        photo_url = reverse('repairs:photo',args=[img.pk])
        self.assertEqual(buyer.get(photo_url).headers['Cache-Control'],'private, no-store')
        self.assertEqual(shop.get(photo_url).status_code,404)
        self.assertEqual(self.browser(self.stranger).get(photo_url).status_code,404)
        self.post(buyer,'request_fix',stage_id=stage.pk,comment='Выровнять стык',submission=1)
        self.post(master,'submit_stage',stage_id=stage.pk,comment='Исправлено',photo=self.pic())
        self.post(buyer,'accept_stage',stage_id=stage.pk,submission=1,status=400)
        self.post(buyer,'accept_stage',stage_id=stage.pk,submission=2)
        stage.refresh_from_db()
        self.assertEqual(stage.state,'accepted')
        self.post(buyer,'report_issue',target_kind='stage',target_id=stage.pk,comment='Проверить стык',photo=self.pic())
        issue = Problem.objects.get()
        self.post(master,'issue_reply',problem_id=issue.pk,comment='Стык проверен')
        self.post(reviewer,'resolve_issue',problem_id=issue.pk,comment='Стороны ознакомились')
        self.assertContains(reviewer.get(self.url('detail')),'Стороны ознакомились')
        self.assertNotContains(shop.get(self.url('detail')),'Проверить стык')

    def test_city_project_media_and_write_switches_and_revisions(self):
        work = self.accept('works')
        buyer, master = self.browser(self.buyer), self.browser(self.master)
        self.post(master,'propose_terms',agreement_id=work.pk,total='81000',starts_on='2030-01-01',ends_on='2030-01-11')
        terms = work.versions.get(revision=2)
        self.assertEqual(work.versions.get(revision=1).total, Decimal(80000))
        self.assertIsNone(terms.accepted_at)
        self.post(buyer,'confirm_terms',agreement_id=work.pk,revision_id=terms.pk)
        self.post(master,'plan_stage',agreement_id=work.pk,title='Тест',due_on='2030-01-10')
        stage = Stage.objects.get()
        self.post(master,'submit_stage',stage_id=stage.pk,comment='Фото',photo=self.pic())
        photo_url = reverse('repairs:photo',args=[Photo.objects.get().pk])
        self.assertEqual(buyer.get(self.url('detail')).status_code,200)
        self.city.enabled = False
        self.city.save()
        self.assertEqual(buyer.get(self.url('detail')).status_code,404)
        self.assertEqual(buyer.get(photo_url).status_code,404)
        self.post(buyer,'accept_stage',stage_id=stage.pk,submission=1,status=404)
        self.city.enabled = True
        self.city.save()
        Repair.objects.filter(pk=self.repair.pk).update(enabled=False)
        self.assertEqual(master.get(photo_url).status_code,404)
        Repair.objects.filter(pk=self.repair.pk).update(enabled=True)
        self.project.city='Алматы'
        self.project.save()
        self.assertEqual(buyer.get(photo_url).status_code,404)
        self.assertEqual(Event.objects.count(),5)
        self.project.city='  Шымкент '
        self.project.save()
        self.assertEqual(buyer.get(photo_url).status_code,200)
        self.assertEqual(Stage.objects.get().state,'review')

    def test_disabled_default_and_project_consent_not_city_wide(self):
        another = ClientProject.objects.create(user=self.buyer, title='Не пилот', city='Шымкент',area_m2=30,rooms=1)
        Repair.objects.create(project=another,city=self.city)
        self.assertEqual(self.browser(self.buyer).get(reverse('repairs:detail',args=[another.pk])).status_code,404)
        self.assertEqual(self.browser(self.other_shop).get(self.url('detail')).status_code,404)

    def test_photos_are_validated_and_replay_does_not_create_duplicate_attachments(self):
        work = self.accept('works')
        worker = self.browser(self.master)
        self.post(worker,'plan_stage',agreement_id=work.pk,title='Задача',due_on='2030-01-10')
        stage = Stage.objects.get()
        self.post(worker,'submit_stage',stage_id=stage.pk,status=400,
                  photo=SimpleUploadedFile('bad.png',b'<svg/>','image/png'))
        self.assertEqual(Photo.objects.count(),0)
        token = str(uuid.uuid4())
        for _ in range(2):
            self.post(worker,'submit_stage',stage_id=stage.pk,token=token,photo=self.pic())
        self.assertEqual(Photo.objects.count(),1)
        self.assertEqual(Event.objects.filter(action='submit_stage').count(),1)

    def test_only_assigned_reviewer_sees_active_projects(self):
        self.accept('works')
        url = reverse('repairs:review_queue')
        reviewer = self.browser(self.reviewer)
        self.assertContains(reviewer.get(url), self.project.title)
        other = self.user_for('other-reviewer', 'admin')
        self.assertNotContains(self.browser(other).get(url), self.project.title)
        self.assertEqual(self.browser(self.shop).get(url).status_code,404)
        self.city.enabled=False
        self.city.save(update_fields=['enabled'])
        self.assertNotContains(reviewer.get(url), self.project.title)

    def test_damage_is_not_received_in_good_condition_or_double_scheduled(self):
        a = self.accept('materials')
        buyer, shop = self.browser(self.buyer), self.browser(self.shop)
        window = dict(window_start='2030-01-09T10:00',window_end='2030-01-09T13:00')
        self.post(shop,'schedule_delivery',agreement_id=a.pk,qty_1='12',**window)
        delivery = Delivery.objects.get()
        self.post(buyer,'confirm_delivery',delivery_id=delivery.pk,received_1='11',damaged_1='12',status=400)
        self.post(buyer,'confirm_delivery',delivery_id=delivery.pk,received_1='11',damaged_1='1')
        delivery.refresh_from_db()
        self.assertEqual(delivery.receipt,{'1':{'received':'11','damaged':'1','missing':'1'}})
        self.assertEqual(receipt_balance(a),{'1':Decimal(2)})
        self.post(shop,'schedule_delivery',agreement_id=a.pk,qty_1='2',**window)
        self.assertEqual(receipt_balance(a),{'1':Decimal(0)})
        self.assertEqual(receipt_balance(a,pending=False),{'1':Decimal(2)})
