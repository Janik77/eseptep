import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import ClientProject, SavedWholeEstimate, UserProfile, ServiceRequest
from .models import ProjectUpload, WholePlanEstimate
from .plan_analysis import analyze


@override_settings(ESEPTEP_DEMO_MODE=True, PLAN_AI_ENABLED=False, OPENAI_LIVE_CONFIRMED=False)
class GuestWholeTests(TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        private = override_settings(PRIVATE_MEDIA_ROOT=temp.name)
        private.enable()
        self.addCleanup(private.disable)
        self.account = User.objects.create_user('pilot@example.test', password='Offline-Pilot-2026!')
        UserProfile.objects.create(user=self.account, role='client', city='Шымкент')

    def sample(self):
        response = self.client.post(reverse('projects:choose_sample'), {'sample': 'two-room'}, follow=True)
        self.assertContains(response, 'Готовый учебный расчёт')
        return response.context['upload'], response.context['estimate']

    def test_guest_edit_and_save_through_real_login(self):
        upload, before = self.sample()
        url = reverse('projects:whole_plan', args=[upload.pk])
        edited = self.client.post(url, {'action':'update','estimate_id':before.pk,'room':0,'finish':'tile'}, follow=True)
        source = edited.context['estimate']
        self.assertNotEqual(source.pk, before.pk)
        expected = deepcopy(source.snapshot)
        save = reverse('accounts:whole_guest_save', args=[source.pk])
        self.assertEqual(self.client.get(save).status_code,405)
        self.assertEqual(Client().post(save, {'next':'save'}).status_code,404)
        logged_in = Client(); logged_in.force_login(self.account)
        self.assertEqual(logged_in.get(url).status_code,404)
        for _ in range(2):
            self.assertRedirects(self.client.post(save, {'next':'save'}), reverse('accounts:login'))
        self.assertContains(self.client.get(reverse('accounts:login')), 'сохранится в вашем кабинете')
        failure = self.client.post(reverse('accounts:login'), {'username':self.account.username,'password':'wrong'})
        self.assertEqual(failure.status_code,200)
        self.assertEqual(SavedWholeEstimate.objects.count(),0)
        with patch('projects.plan_analysis.responses_create') as send:
            response = self.client.post(reverse('accounts:login'), {'username':self.account.username,
                                        'password':'Offline-Pilot-2026!'},follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.resolver_match.url_name, 'whole_saved')
            saved = SavedWholeEstimate.objects.get()
            self.assertEqual(saved.snapshot,expected)
            self.assertEqual(saved.source_id,source.pk)
            self.assertEqual(saved.project.user,self.account)
            self.assertContains(self.client.get(reverse('accounts:dashboard_client')), saved.project.title)
            after = self.client.get(url)
            self.assertEqual(after.context['estimate'].pk,source.pk)
            self.assertEqual(analyze(ProjectUpload.objects.get(pk=upload.pk)).pk,source.snapshot['analysis_id'])
            send.assert_not_called()
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertEqual(Client().get(url).status_code,404)
        self.assertEqual(ClientProject.objects.count(),1)

    def test_failed_preflight_keeps_file_and_manual_whole_estimate(self):
        path=Path(settings.BASE_DIR,'tests','fixtures','plans','typical-two-room.pdf')
        with patch('projects.plan_analysis.responses_create') as send:
            submitted=self.client.post(reverse('projects:upload'),{'action':'upload_calculate',
                'file':SimpleUploadedFile('private-plan.pdf',path.read_bytes())},follow=True)
            self.assertContains(submitted,'Файл сохранён.')
            upload=submitted.context['upload'];url=reverse('projects:whole_plan',args=[upload.pk])
            self.assertEqual(self.client.get(reverse('projects:download',args=[upload.pk])).status_code,200)
            error=self.client.post(url,{'action':'add_room','name':'Бөлме','area':'-2','finish':'laminate'})
            self.assertContains(error,'value="-2"',status_code=400)
            result=self.client.post(url,{'action':'add_room','name':'Бөлме','area':'15,25','finish':'spc'},follow=True)
            found=result.context['estimate']
            self.assertEqual(found.snapshot['known_area'],'15.25')
            self.assertEqual(found.snapshot['rooms'][0]['finish'],'spc')
            self.assertEqual(self.client.post(url,{'action':'add_room','name':'Дубликат','area':'15,25','finish':'spc'}).status_code,400)
            self.assertEqual(self.client.post(url, {'action':'analyze'}).status_code,302)
            self.assertEqual(self.client.get(url).context['estimate'].pk,found.pk)
            self.assertEqual(WholePlanEstimate.objects.count(),1)
            send.assert_not_called()

    def test_area_store_price_rounds_purchase_and_keeps_signed_request_and_pdfs(self):
        from io import BytesIO
        from django.utils import timezone
        from pypdf import PdfReader
        from calculators.price_import import import_floor_prices
        from accounts.models import SupplierProfile, WholeSupplierOffer
        raw = ('material,unit,price_basis,pack_coverage,price_kzt\nlaminate,м²,canonical,2.2,4500.00\n').encode()
        book, _ = import_floor_prices(raw, store='Synthetic', version='sq-m-and-packs-v1', source='Synthetic',
                                      date_text='2026-11-20', write=True)
        book.is_active = True; book.published_at = timezone.now(); book.save()
        vendor = User.objects.create_user('demo-supplier@example.test')
        UserProfile.objects.create(user=vendor, role='supplier')
        SupplierProfile.objects.create(user=vendor, company_name='Учебный магазин', is_active=True)
        upload, estimate = self.sample()
        row = next(r for r in estimate.snapshot['procurement'] if r['material_key']=='mat_0067')
        # 65.4 m² dry rooms * 1.05 -> ceil 69 m²; ceil(69/2.2)=32; 32*2.2*4500=316800.
        self.assertEqual((row['quantity'],row['purchase_quantity'],row['unit_price'],row['line_total']),
                         ('69','32','9900.00','316800.00'))
        self.assertEqual(row['purchase_covered_quantity'], '70.4')
        self.assertEqual(estimate.snapshot['priced_subtotal'], '316800.00')
        self.client.post(reverse('accounts:whole_guest_save',args=[estimate.pk]), {'next':'quote'})
        login = self.client.post(reverse('accounts:login'), {'username':self.account.username,'password':'Offline-Pilot-2026!'},follow=True)
        saved = SavedWholeEstimate.objects.get()
        self.assertEqual(login.context['saved'].pk,saved.pk)
        url = reverse('accounts:whole_preview',args=[saved.pk])
        ids = [str(i) for i in range(len(saved.snapshot['procurement']))]
        preview = self.client.get(url, {'select':'1','line':ids})
        self.assertContains(preview,'32 упак.')
        self.assertContains(preview,'316 800')
        self.assertContains(preview,'Редакция каталога исходной сметы ESEPTEP: sq-m-and-packs-v1')
        new_book, _ = import_floor_prices(raw.replace(b'4500.00', b'9000.00'), store='Synthetic',
            version='sq-m-and-packs-v2', source='Synthetic', date_text='2026-11-20', write=True)
        book.is_active = False; book.save(update_fields=['is_active'])
        new_book.is_active = True; new_book.published_at = timezone.now(); new_book.save()
        data={'token':preview.context['token'],'confirm':'yes'}
        for _ in range(2):
            self.assertEqual(self.client.post(url,data).status_code,302)
        req=ServiceRequest.objects.get()
        self.assertEqual(req.request_snapshot['priced_subtotal'],saved.snapshot['priced_subtotal'])
        frozen=deepcopy(req.request_snapshot)
        self.assertNotIn('price_version', frozen)  # Existing signed flow/schema stays unchanged.
        self.assertContains(self.client.get(reverse('accounts:whole_saved',args=[saved.pk])),'sq-m-and-packs-v1')
        pdf=self.client.get(reverse('accounts:saved_whole_pdf',args=[saved.pk]))
        extract=lambda response: ' '.join(' '.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages).split())
        self.assertIn('32 упак.',extract(pdf));self.assertIn('316800.00',extract(pdf));self.assertIn('к закупке 70.4 м²',extract(pdf))
        self.assertIn('Редакция каталога сметы ESEPTEP: sq-m-and-packs-v1',extract(pdf))
        self.assertNotIn('sq-m-and-packs-v2',extract(pdf))
        self.client.post(reverse('projects:whole_plan',args=[upload.pk]),{'action':'update','estimate_id':estimate.pk,'room':'0','finish':'tile'})
        req.refresh_from_db()
        self.assertEqual(req.request_snapshot,frozen)
        provider=Client();provider.force_login(vendor)
        response_url=reverse('accounts:whole_request',args=[req.pk])
        page=provider.get(response_url)
        lam=next(r for r in frozen['lines'] if r['material_key']=='mat_0067')
        i=lam['line_id']
        payload={'token':page.context['token'],f'price_{i}':'9900.00',f'availability_{i}':'available'}
        for _ in range(2):self.assertEqual(provider.post(response_url,payload).status_code,302)
        offer=WholeSupplierOffer.objects.get()
        self.assertEqual(offer.snapshot['confirmed_subtotal'],'316800.00')
        self.assertContains(self.client.get(response_url),'316 800')
        offer_pdf=self.client.get(reverse('accounts:whole_offer_pdf',args=[req.pk]))
        self.assertIn('316800.00',extract(offer_pdf))
        self.assertIn('каталога исходной сметы ESEPTEP: sq-m-and-packs-v1',extract(offer_pdf))
        self.assertIn('Цены предложения указаны магазином отдельно.',extract(offer_pdf))
        self.assertNotIn('sq-m-and-packs-v2',extract(offer_pdf))
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME]='kk'
        self.assertContains(self.client.get(response_url),'каталог нұсқасы: sq-m-and-packs-v1')
        self.assertIn('каталог нұсқасы: sq-m-and-packs-v1',
            extract(self.client.get(reverse('accounts:whole_offer_pdf',args=[req.pk]))))

    def test_authenticated_first_project_is_created_once_without_a_dead_end(self):
        self.client.force_login(self.account)
        _, estimate=self.sample()
        url=reverse('accounts:save_whole',args=[estimate.pk])
        self.assertContains(self.client.get(url,{'next':'save'}),'Создать проект и сохранить')
        first=self.client.post(url,{'project_id':'new','next':'save'})
        second=self.client.post(url,{'project_id':'new','next':'save'})
        self.assertEqual(first.url,second.url)
        self.assertEqual(SavedWholeEstimate.objects.count(),1)
        self.assertEqual(ClientProject.objects.count(),1)
