import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from .models import ProjectUpload, PlanAnalysis, PlanAnalysisBudget, WholePlanEstimate
from .plan_analysis import analyze, normalize_rooms, analysis_identity, PlanError
from .whole_plan import initial_rooms, persist_estimate


@override_settings(PLAN_AI_ENABLED=True, OPENAI_LIVE_CONFIRMED=True, OPENAI_API_KEY='test-placeholder', OPENAI_MODEL='gpt-6.1-sol', PRODUCTION=False, ESEPTEP_DEMO_MODE=True)
class WholePlanTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(PRIVATE_MEDIA_ROOT=self.tmp.name)
        override.enable(); self.addCleanup(override.disable)
        self.user = User.objects.create_user('whole-plan-client')
        self.client.force_login(self.user)
        image = io.BytesIO(); Image.new('RGB',(120,120),'white').save(image,'PNG')
        self.raw = image.getvalue()
        self.upload = ProjectUpload.objects.create(user=self.user,file=SimpleUploadedFile('apartment.png',self.raw))
        self.rooms = [dict(name=n,kind=k,area=a,source='stated' if a else 'unknown',page=1,
                           evidence=f'{n} {a} m2' if a else 'unreadable',page_type='floor_plan')
                      for n,k,a in [('Living','other',18),('Kitchen','other',10.2),('Bath','bathroom',4.8),('Hall','other',6)]]

    def response(self, rooms=None):
        return {'status':'completed','id':'test','usage':{},'output':[{'content':[{'type':'output_text','text':json.dumps({'rooms':rooms or self.rooms})}]}]}

    def prepared(self, api):
        api.return_value = self.response()
        analysis = analyze(self.upload)
        return persist_estimate(self.upload, initial_rooms(analysis), analysis.pk)

    @patch('projects.plan_analysis.responses_create')
    def test_all_rooms_auto_estimate_and_finish_recompute_without_api(self, api):
        estimate = self.prepared(api)
        self.assertEqual(len(estimate.snapshot['rooms']),4)
        self.assertEqual(estimate.snapshot['known_area'],'39.00')
        self.assertEqual(estimate.snapshot['rooms'][2]['finish'],'tile')
        self.assertEqual(estimate.snapshot['rooms'][0]['finish'],'laminate')
        self.assertEqual(estimate.snapshot['rounding'],'grouped-by-finish')
        self.assertIsNone(estimate.snapshot['total'])
        self.assertTrue(all(r['unit_price'] is None for r in estimate.snapshot['procurement']))
        response = self.client.post(f'/projects/{self.upload.pk}/whole/', {'action':'update','room':'0','finish':'tile','estimate_id':estimate.pk})
        self.assertEqual(response.status_code,302)
        newer = WholePlanEstimate.objects.latest('pk')
        self.assertNotEqual(newer.snapshot['procurement'],estimate.snapshot['procurement'])
        self.assertEqual(newer.snapshot['rooms'][0]['finish'],'tile')
        self.assertEqual(api.call_count,1)
        # Returning to a prior finish selects the prior content revision, not the greatest PK.
        response = self.client.post(f'/projects/{self.upload.pk}/whole/', {'action':'update','room':'0','finish':'laminate','estimate_id':newer.pk})
        self.assertEqual(response.status_code,302)
        self.upload.refresh_from_db()
        selected = WholePlanEstimate.objects.get(pk=self.upload.ai_summary['whole_estimate_id'])
        self.assertEqual(selected.snapshot['rooms'][0]['finish'],'laminate')
        self.assertEqual(self.client.post(f'/projects/{self.upload.pk}/whole/', {'action':'update','room':'1','finish':'tile','estimate_id':estimate.pk}).status_code,400)

    @patch('projects.plan_analysis.responses_create')
    def test_partial_and_different_file_isolation(self, api):
        self.rooms[2]['area'] = None; self.rooms[2]['source']='unknown'
        estimate = self.prepared(api)
        self.assertEqual(estimate.snapshot['unknown_rooms'],1)
        self.assertEqual(estimate.snapshot['known_area'],'34.20')
        self.client.post(f'/projects/{self.upload.pk}/whole/',{'action':'update','estimate_id':estimate.pk,'room':2,'finish':'tile','area':'5.25'})
        other = ProjectUpload.objects.create(user=self.user,file=SimpleUploadedFile('new.png',self.raw+b'new'))
        response=self.client.post(f'/projects/{other.pk}/whole/',{'action':'update','estimate_id':estimate.pk,'room':2,'finish':'tile','area':'50'})
        self.assertEqual(response.status_code,400)
        self.assertFalse(WholePlanEstimate.objects.filter(upload=other).exists())

    @patch('projects.plan_analysis.responses_create')
    def test_duplicate_languages_version_pdf_and_supplier(self, api):
        estimate=self.prepared(api)
        self.assertEqual(persist_estimate(self.upload,initial_rooms(analyze(self.upload)),estimate.snapshot['analysis_id']).pk,estimate.pk)
        duplicate=ProjectUpload.objects.create(user=self.user,file=SimpleUploadedFile('duplicate.png',self.raw))
        self.assertEqual(analyze(duplicate).pk,estimate.snapshot['analysis_id'])
        self.assertEqual(api.call_count,1)
        pdf=self.client.get(f'/projects/{self.upload.pk}/whole/{estimate.pk}/pdf/')
        self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF'))
        for _ in range(2):
            response=self.client.post(f'/projects/{self.upload.pk}/whole/',{'action':'supplier_simulate','estimate_id':estimate.pk})
            self.assertEqual(response.status_code,302)
        estimate.refresh_from_db();self.assertIsNotNone(estimate.supplier_simulated_at)
        self.client.force_login(User.objects.create_user('another-client'))
        self.assertEqual(self.client.get(f'/projects/{self.upload.pk}/whole/').status_code,404)
        self.assertEqual(self.client.get(f'/projects/{self.upload.pk}/whole/{estimate.pk}/pdf/').status_code,404)

    def test_elevation_missing_quote_and_dimensions(self):
        values=[dict(self.rooms[0],page_type='elevation'),dict(self.rooms[1],evidence='room'),
                dict(self.rooms[2],source='dimensions',width=2,length=2.4,evidence='2 x 2.4 m')]
        rows=normalize_rooms(values,[(b'', '')], strict=True)
        self.assertIsNone(rows[0]['area']);self.assertIsNone(rows[1]['area']);self.assertEqual(rows[2]['area'],'4.80')

    @patch('projects.plan_analysis.responses_create')
    def test_old_analysis_cannot_be_reused_or_silently_recharged(self, api):
        import hashlib
        legacy=hashlib.sha256(f'user:{self.user.pk}'.encode()+b'\0'+self.raw).hexdigest()
        PlanAnalysis.objects.create(identity=legacy,upload=self.upload,status='completed',rooms=[{'name':'Bath','area':'50'}])
        with self.assertRaisesMessage(PlanError,'legacy_analysis'):analyze(self.upload)
        api.assert_not_called();self.assertFalse(WholePlanEstimate.objects.exists())

    @patch('projects.plan_analysis.responses_create')
    def test_templates_ru_kk_and_upload_auto_redirect(self, api):
        api.return_value=self.response()
        result=self.client.post('/projects/upload/', {'action':'upload_calculate','file':SimpleUploadedFile('new.png',self.raw)})
        self.assertEqual(result.status_code,302)
        self.assertIn('/whole/',result.url)
        for lang, title in [('ru','От плана к материалам'),('kk','Жоспардан материалдарға')]:
            response=self.client.get(result.url,HTTP_ACCEPT_LANGUAGE=lang)
            self.assertContains(response,title)
            self.assertContains(response,'39.00')
            self.assertNotContains(response,'50.00')
        self.assertEqual(api.call_count,1)

    @patch('projects.plan_analysis.responses_create')
    def test_mixed_pages_floor_page_and_missing_room_does_not_block(self, api):
        from reportlab.pdfgen import canvas
        raw=io.BytesIO();pdf=canvas.Canvas(raw)
        pdf.drawString(40,700,'ELEVATION 50 m2');pdf.showPage()
        pdf.drawString(40,700,'FLOOR PLAN: Living 18.0 m2; Bath unreadable');pdf.save()
        upload=ProjectUpload.objects.create(user=self.user,file=SimpleUploadedFile('mixed.pdf',raw.getvalue()))
        rooms=[dict(self.rooms[0],page=2),dict(self.rooms[2],page=2,area=None,source='unknown')]
        api.return_value=self.response(rooms)
        analysis=analyze(upload)
        estimate=persist_estimate(upload,initial_rooms(analysis),analysis.pk)
        self.assertEqual(estimate.snapshot['known_area'],'18.00')
        self.assertEqual(estimate.snapshot['unknown_rooms'],1)
        page=self.client.get(f'/projects/{upload.pk}/whole/')
        self.assertEqual(page.context['preview_page'],2)
        self.assertNotContains(page,'50.00')

    @override_settings(PLAN_AI_ENABLED=False)
    @patch('projects.plan_analysis.responses_create')
    def test_primary_upload_keeps_manual_fallback_accessible_without_ai(self, api):
        for lang in ('ru', 'kk'):
            self.client.cookies['django_language'] = lang
            response = self.client.post('/projects/upload/', {
                'action':'upload_calculate',
                'file':SimpleUploadedFile('fallback.png', self.raw, content_type='image/png'),
            }, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'data-manual-plan')
            self.assertContains(response, 'data-legacy-estimate')
            upload = ProjectUpload.objects.latest('pk')
            self.assertContains(response, f'/projects/{upload.pk}/plan/')
            self.assertEqual(self.client.get(f'/projects/{upload.pk}/plan/').status_code, 200)
            legacy = self.client.get(f'/projects/upload/?upload_id={upload.pk}')
            self.assertContains(legacy, 'name="upload_id"')
        api.assert_not_called()

    @patch('projects.plan_analysis.responses_create')
    def test_known_area_manual_correction_does_not_call_provider(self, api):
        record=self.prepared(api)
        r=self.client.post(f'/projects/{self.upload.pk}/whole/',{'action':'update','room':'0','finish':'laminate','area':'19.5','estimate_id':record.pk})
        self.assertEqual(r.status_code,302)
        latest=WholePlanEstimate.objects.latest('pk')
        self.assertEqual(latest.snapshot['rooms'][0]['area'],'19.50')
        self.assertEqual(latest.snapshot['rooms'][0]['source'],'manual')
        self.assertEqual(api.call_count,1)

    @patch('projects.plan_analysis.responses_create')
    def test_rename_partial_edit_preserves_other_rooms_and_provenance(self, api):
        self.rooms[0].update(finish='parquet', finish_evidence='parquet flooring')
        estimate = self.prepared(api)
        original = estimate.snapshot
        response = self.client.post(f'/projects/{self.upload.pk}/whole/', {
            'action':'update', 'estimate_id':estimate.pk, 'room':0,
            'name':'Спальня / Жатын бөлме', 'area':'18,00'})
        self.assertEqual(response.status_code,302)
        self.upload.refresh_from_db()
        new = WholePlanEstimate.objects.get(pk=self.upload.ai_summary['whole_estimate_id']).snapshot
        self.assertEqual(new['rooms'][0]['name'],'Спальня / Жатын бөлме')
        self.assertEqual(new['rooms'][0]['finish_source'],'plan')
        self.assertEqual(new['rooms'][0]['source'],'stated')
        self.assertEqual(new['rooms'][0]['visual_evidence'],original['rooms'][0]['visual_evidence'])
        self.assertEqual(new['rooms'][1:],original['rooms'][1:])
        self.assertEqual(new['procurement'],original['procurement'])
        estimate.refresh_from_db()
        self.assertEqual(estimate.snapshot,original)
        self.assertEqual(api.call_count,1)

    @patch('projects.plan_analysis.responses_create')
    def test_partial_room_counts_coverage_and_rename_unknown_room(self, api):
        self.rooms[0].update(area=None, source='unknown')
        estimate = self.prepared(api)
        self.assertEqual(estimate.snapshot['calculated_rooms'],3)
        self.assertEqual(estimate.snapshot['priced_positions'],0)
        self.assertGreater(estimate.snapshot['total_positions'],0)
        self.assertEqual(self.client.post(f'/projects/{self.upload.pk}/whole/', {
            'action':'update','estimate_id':estimate.pk,'room':0,'name':'Новая комната','area':''}).status_code,302)
        new = WholePlanEstimate.objects.latest('pk')
        self.assertIsNone(new.snapshot['rooms'][0]['area'])
        self.assertTrue(new.snapshot['rooms'][0]['finish_proposed'])
        for language in ('ru','kk'):
            response = self.client.get(f'/projects/{self.upload.pk}/whole/', HTTP_ACCEPT_LANGUAGE=language)
            self.assertContains(response, '3 / 4')
            self.assertContains(response, 'Новая комната')
        self.assertEqual(api.call_count,1)

    @patch('projects.plan_analysis.responses_create')
    def test_invalid_names_and_stale_edit_do_not_create_revision(self, api):
        estimate=self.prepared(api)
        count=WholePlanEstimate.objects.count()
        for name in ('', ' ', 'x'*101, 'room\nname'):
            self.assertEqual(self.client.post(f'/projects/{self.upload.pk}/whole/', {
                'action':'update','estimate_id':estimate.pk,'room':0,'name':name}).status_code,400)
        self.assertEqual(WholePlanEstimate.objects.count(),count)
        self.assertEqual(api.call_count,1)

    @patch('projects.plan_analysis.responses_create')
    def test_group_identity_and_partial_price_coverage(self, api):
        from calculators.models import PriceBook, MaterialPrice
        from django.utils import timezone
        estimate=self.prepared(api)
        rows=estimate.snapshot['procurement']
        self.assertTrue(all(r['material_key'] and r['specification'] and r['calculator_slug'] for r in rows))
        row=rows[0]
        book=PriceBook.objects.create(store_name='Synthetic test only',version='synthetic-stage2',
            source_note='Synthetic test only',price_date=timezone.now().date(),is_active=True,published_at=timezone.now())
        MaterialPrice.objects.create(book=book,calculator_slug=row['calculator_slug'],variant_key=row['variant'],
            material_key=row['material_key'],unit=row['unit'],price='100')
        updated=persist_estimate(self.upload,estimate.snapshot['rooms'],estimate.snapshot['analysis_id'])
        self.assertGreater(updated.snapshot['priced_positions'],0)
        self.assertLess(updated.snapshot['priced_positions'],updated.snapshot['total_positions'])
        self.assertIsNone(updated.snapshot['materials_total'])
        self.assertEqual(updated.snapshot['total_positions'],len(updated.snapshot['procurement']))
        self.assertEqual(api.call_count,1)

    def test_equal_labels_do_not_merge_different_supported_specifications(self):
        from .whole_plan import calculate_snapshot
        rooms = [dict(index=0,name='A',area='10',finish='tile',finish_proposed=True),
                 dict(index=1,name='B',area='10',finish='laminate',finish_proposed=True)]
        with patch('projects.whole_plan.calculate_materials', return_value={'materials':[
            {'title':'Same label','unit':'м²','quantity':12}]}), patch('projects.whole_plan.material_key', return_value='stable-id'):
            snapshot = calculate_snapshot(rooms,1)
        self.assertEqual(len(snapshot['procurement']),2)
        self.assertEqual({r['specification'] for r in snapshot['procurement']},{'60x60','laminate'})
        self.assertEqual([r['quantity'] for r in snapshot['procurement']],['12','12'])
