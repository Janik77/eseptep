import hashlib
import io
import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image, ImageDraw, PngImagePlugin
from reportlab.pdfgen import canvas

from .models import PlanAnalysis, PlanAnalysisBudget, ProjectUpload, WholePlanEstimate
from .plan_analysis import PlanError, analyze


def png(label=None, blank=False, fmt='PNG'):
    output = io.BytesIO()
    image = Image.new('RGB', (220, 170), 'white')
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 200, 150), outline='black', width=5)
        draw.line((110, 20, 110, 150), width=5, fill='black')
    options = {}
    if label is not None:
        info = PngImagePlugin.PngInfo()
        info.add_text('comment', label)
        options = {'pnginfo': info}
    image.save(output, fmt, **options)
    return output.getvalue()


def pdf(*headings):
    output = io.BytesIO()
    writer = canvas.Canvas(output)
    for heading in headings:
        writer.drawString(45, 720, heading)
        writer.rect(100, 200, 175, 175)
        writer.showPage()
    writer.save()
    return output.getvalue()


def model(kind='floor_plan', selected=None, rooms=None):
    return {
        'status': 'completed', 'id': 'resp_synthetic_plan',
        'usage': {'input_tokens': 100, 'output_tokens': 50},
        'output': [{'content': [{'type': 'output_text', 'text': json.dumps({
            'document_kind': kind,
            'floor_pages': [1] if selected is None and kind == 'floor_plan' else selected or [],
            'rooms': rooms if rooms is not None else [],
        })}]}],
    }


def room(page=1, area=8):
    return {'name': 'Bath', 'kind': 'bathroom', 'area': area, 'source': 'stated',
            'evidence': f'{area} m2', 'page': page, 'page_type': 'floor_plan'}


@override_settings(PLAN_AI_ENABLED=True, OPENAI_LIVE_CONFIRMED=True,
                   OPENAI_API_KEY='unit-test-placeholder', OPENAI_MODEL='gpt-6.1-sol',
                   PRODUCTION=False)
class PlanInputGateTests(TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        settings = override_settings(PRIVATE_MEDIA_ROOT=temp.name)
        settings.enable(); self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user('scope-a')
        self.client.force_login(self.owner)

    def upload(self, raw, filename='input.png', client=None):
        return (client or self.client).post('/projects/upload/', {
            'action': 'upload_calculate', 'file': SimpleUploadedFile(filename, raw),
        })

    @patch('projects.plan_analysis.responses_create')
    def test_local_rejections_do_not_create_attempt_or_reserve_spend(self, api):
        for raw, name in [(png(blank=True), 'blank.png'), (pdf('ELEVATION 1'), 'facade.pdf')]:
            result = self.upload(raw, name)
            self.assertEqual(result.status_code, 302)
            self.assertContains(self.client.get(result.url), 'Планировка не распознана')
            self.client.cookies['django_language'] = 'kk'
            self.assertContains(self.client.post(result.url, {'action': 'analyze'}), 'Жоспар анықталмады')
            self.client.cookies['django_language'] = 'ru'
        api.assert_not_called()
        self.assertFalse(PlanAnalysis.objects.exists())
        self.assertFalse(PlanAnalysisBudget.objects.exists())
        self.assertFalse(WholePlanEstimate.objects.exists())

    @patch('projects.plan_analysis.responses_create')
    def test_bytes_and_limits_fail_before_analysis(self, api):
        for raw, name in [(png(fmt='PNG'), 'wrong.jpg'), (b'GIF89a', 'movie.gif'),
                          (b'x' * (5*1024*1024+1), 'big.pdf'),
                          (pdf(*(['Floor plan']*13)), 'long.pdf')]:
            response = self.upload(raw, name)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['upload_form'].errors)
        api.assert_not_called()
        self.assertFalse(ProjectUpload.objects.exists())

    @patch('projects.plan_analysis.responses_create')
    def test_supported_real_image_formats_transparency_and_animation(self, api):
        api.return_value = model(rooms=[room()])
        for name, fmt in [('phone.JPEG', 'JPEG'), ('phone.webp', 'WEBP'), ('floor.png', 'PNG')]:
            self.assertEqual(self.upload(png(fmt=fmt), name).status_code, 302)
        self.assertEqual(self.upload(png(fmt='JPEG'), 'alias.jpg').status_code, 302)
        # Black lines on transparency must be composited onto white before
        # classification. Dropping alpha directly looks like a solid black image.
        transparent = io.BytesIO()
        image = Image.new('RGBA', (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((20, 20, 100, 100), outline='black', width=4)
        image.save(transparent, 'PNG')
        self.assertEqual(self.upload(transparent.getvalue(), 'linework.png').status_code, 302)
        animation = io.BytesIO()
        image.save(animation, 'PNG', save_all=True, append_images=[Image.new('RGBA', image.size, 'red')])
        response = self.upload(animation.getvalue(), 'frames.png')
        self.assertContains(response, 'один неподвижный кадр')
        self.assertEqual(api.call_count, 4)

    @patch('projects.plan_analysis.responses_create')
    def test_photo_result_is_terminal_in_both_locales_and_never_recharged(self, api):
        # Synthetic image only; the model boundary is mocked, not a claim of visual QA.
        api.return_value = model('photo', rooms=[room()])
        raw = png()
        response = self.upload(raw)
        analysis = PlanAnalysis.objects.get()
        self.assertEqual((analysis.status, analysis.error_code, analysis.rooms), ('failed', 'not_floor_plan', []))
        self.assertContains(self.client.get(response.url), 'Фото помещения и фасады не подходят')
        self.client.cookies['django_language'] = 'kk'
        self.assertContains(self.client.get(response.url), 'Бөлме фотосы мен қасбет жарамайды')
        self.assertEqual(self.upload(raw, 'renamed.png').status_code, 302)
        self.assertEqual(api.call_count, 1)
        self.assertFalse(WholePlanEstimate.objects.exists())

    @patch('projects.plan_analysis.responses_create')
    def test_mixed_selection_omits_elevation_and_retains_original_page_number(self, api):
        api.return_value = model(selected=[2], rooms=[room(1, 900), room(2, 8)])
        response = self.upload(pdf('ELEVATION 1', 'FLOOR PLAN: bathroom 8 m2'), 'mixed.pdf')
        self.assertEqual(response.status_code, 302)
        rows = PlanAnalysis.objects.get().rooms
        self.assertEqual([(r['page'], r['area']) for r in rows], [(2, '8.00')])
        sent = api.call_args.kwargs
        parts = sent['input'][0]['content']
        self.assertEqual(sum(item['type']=='input_image' for item in parts), 1)
        self.assertIn({'type': 'input_text', 'text': 'Document page 2'}, parts)
        self.assertFalse(sent['store'])
        self.assertEqual(sent['max_output_tokens'], 1800)

    @patch('projects.plan_analysis.responses_create')
    def test_generic_facade_note_cannot_exclude_a_possible_floor_plan(self, api):
        api.return_value = model(rooms=[room()])
        response = self.upload(pdf('Elevation details shown elsewhere'), 'still-a-plan.pdf')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PlanAnalysis.objects.get().rooms[0]['area'], '8.00')
        api.assert_called_once()

    @patch('projects.plan_analysis.responses_create')
    def test_encrypted_and_expanded_pdf_do_not_reach_provider(self, api):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject
        encrypted = PdfWriter()
        encrypted.add_blank_page(width=100, height=100)
        encrypted.encrypt('synthetic-password')
        output = io.BytesIO()
        encrypted.write(output)
        self.assertTrue(self.upload(output.getvalue(), 'encrypted.pdf').context['upload_form'].errors)
        writer = PdfWriter()
        page = writer.add_blank_page(width=100, height=100)
        stream = DecodedStreamObject()
        stream.set_data(b' '*(2*1024*1024+1))
        page[NameObject('/Contents')] = writer._add_object(stream.flate_encode())
        output = io.BytesIO()
        writer.write(output)
        self.assertLess(len(output.getvalue()), 5*1024*1024)
        response = self.upload(output.getvalue(), 'complex.pdf')
        self.assertContains(self.client.get(response.url), 'PDF слишком сложный')
        api.assert_not_called()
        self.assertFalse(PlanAnalysisBudget.objects.exists())

    @patch('projects.plan_analysis.responses_create')
    def test_exact_source_hash_owner_scope_and_independent_manual_edits(self, api):
        api.return_value = model(rooms=[room()])
        raw = png('metadata-a')
        first = self.upload(raw)
        first_upload = ProjectUpload.objects.get()
        first_estimate = WholePlanEstimate.objects.get()
        self.assertEqual(first_upload.source_sha256, hashlib.sha256(raw).hexdigest())
        self.client.post(first.url, {'action':'update','estimate_id':first_estimate.pk,
                                    'room':0,'name':'Private corrected','area':'9.50'})
        self.assertEqual(self.upload(raw, 'another.png').status_code, 302)
        self.assertEqual(api.call_count, 1)
        repeated = ProjectUpload.objects.exclude(pk=first_upload.pk).get()
        self.assertEqual(WholePlanEstimate.objects.get(upload=repeated).snapshot['known_area'], '8.00')
        self.assertEqual(self.upload(png('metadata-b')).status_code, 302)
        self.assertEqual(api.call_count, 2)
        other = Client()
        other.force_login(get_user_model().objects.create_user('scope-b'))
        self.upload(raw, client=other)
        self.assertEqual(api.call_count, 3)
        self.assertEqual(other.get(first.url).status_code, 404)
        self.assertEqual(len({x.kwargs['_local_scope'] for x in api.call_args_list}), 3)

    @patch('projects.plan_analysis.responses_create')
    def test_prior_parser_identity_blocks_silent_recharge_without_reusing_rooms(self, api):
        raw = png()
        upload = ProjectUpload.objects.create(user=self.owner,file=SimpleUploadedFile('old.png', raw))
        identity = hashlib.sha256(f'whole-floor-v1\0user:{self.owner.pk}\0'.encode()+raw).hexdigest()
        PlanAnalysis.objects.create(identity=identity, upload=upload, status='completed', rooms=[room(area=91)])
        with self.assertRaisesMessage(PlanError, 'legacy_analysis'):
            analyze(upload)
        self.assertNotContains(self.client.get(f'/projects/{upload.pk}/whole/'), '91.00')
        api.assert_not_called()
