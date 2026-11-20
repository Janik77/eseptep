import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import PlanAnalysis, PlanAnalysisBudget, ProjectUpload, WholePlanEstimate
from .test_plan_input_gate import model, room


def booklet(*sheets):
    buffer = io.BytesIO()
    writer = canvas.Canvas(buffer)
    for title, lines in sheets:
        if title is None:
            scan = Image.new('RGB', (300, 160), 'white')
            ImageDraw.Draw(scan).multiline_text((16, 16), '\n'.join(lines), fill='black')
            writer.drawImage(ImageReader(scan), 45, 610)
            writer.showPage()
            continue
        content = writer.beginText(45, 770)
        content.textLine(title)
        for line in lines:
            content.textLine(line)
        writer.drawText(content)
        if title == 'Floor plan':
            writer.rect(90, 300, 300, 180)
            writer.line(200, 300, 200, 480)
            writer.drawString(110, 420, '01 Bath')
            writer.drawString(240, 420, '02 Kitchen')
        writer.showPage()
    writer.save()
    return buffer.getvalue()


def schedule(title='Room schedule', unit='Apartment A-12', rows=('01 Bath 4.80 m²', '02 Kitchen 12.00 m²')):
    return title, (unit, *rows)


PLAN = ('Floor plan', ('Apartment A-12',))


def candidate(seen='01 Bath 4.80 m²'):
    return {**room(), 'area': None, 'source': 'unknown', 'evidence': '', 'schedule_evidence': seen}


@override_settings(PLAN_AI_ENABLED=True, OPENAI_LIVE_CONFIRMED=True,
                   OPENAI_API_KEY='unit-test-placeholder', OPENAI_MODEL='gpt-6.1-sol',
                   PRODUCTION=False)
class CompanionScheduleTests(TestCase):
    def upload(self, raw, filename='apartment.pdf'):
        result = self.client.post('/projects/upload/', {
            'action': 'upload_calculate', 'file': SimpleUploadedFile(filename, raw),
        })
        self.assertEqual(result.status_code, 302)
        return result

    @patch('projects.plan_analysis.responses_create')
    def test_unstated_plan_area_recovered_from_uniquely_matching_companion(self, api):
        raw = booklet(PLAN, schedule())
        api.return_value = model(rooms=[candidate()])
        result = self.upload(raw)
        analysis = PlanAnalysis.objects.get()
        self.assertEqual(analysis.rooms[0]['area'], '4.80')
        self.assertEqual(analysis.rooms[0]['page'], 2)
        api.assert_called_once()

    @patch('projects.plan_analysis.responses_create')
    def test_same_bytes_use_one_private_attempt_and_record_original_pdf_pages(self, api):
        raw = booklet(PLAN, schedule())
        api.return_value = model(rooms=[candidate()])
        first = self.upload(raw)
        analysis = PlanAnalysis.objects.get()
        recognized = analysis.rooms[0]
        self.assertEqual((recognized['page'], recognized['schedule_floor_page'], recognized['line']), (2, 1, 3))
        self.assertEqual(recognized['evidence'], '01 Bath 4.80 m²')
        self.assertEqual(WholePlanEstimate.objects.get().snapshot['known_area'], '4.80')
        first_upload = analysis.upload
        for locale, text in [('ru', 'Экспликация помещений, стр. 2'), ('kk', 'Бөлмелер кестесі, 2-бет')]:
            with self.subTest(locale=locale):
                self.client.cookies['django_language'] = locale
                response = self.client.get(first.url)
                self.assertContains(response, text)
                self.assertContains(response, f'/projects/{first_upload.pk}/plan/page/1/')
                self.assertContains(response, f'/projects/{first_upload.pk}/plan/page/2/')
                self.assertEqual(self.client.get(f'/projects/{first_upload.pk}/plan/page/2/').status_code, 200)
        self.upload(raw, 'renamed.pdf')
        self.assertEqual(ProjectUpload.objects.count(), 2)
        self.assertEqual(PlanAnalysis.objects.count(), 1)
        api.assert_called_once()
        self.assertEqual(api.call_args.kwargs['max_output_tokens'], 1800)
        self.assertFalse(api.call_args.kwargs['store'])

    @patch('projects.plan_analysis.responses_create')
    def test_unmatched_missing_or_conflicting_source_never_supplies_area(self, api):
        cases = [
            ('different apartment', (PLAN, schedule(unit='Apartment A-13')), candidate()),
            ('unknown apartment', (PLAN, schedule(unit='Building Overview')), candidate()),
            ('different room code', (PLAN, schedule(rows=('02 Bath 4.80 m²',))), candidate('02 Bath 4.80 m²')),
            ('different room name', (PLAN, schedule(rows=('01 Kitchen 4.80 m²',))), candidate('01 Kitchen 4.80 m²')),
            ('different units', (PLAN, schedule(rows=('01 Bath 4.80 ft²',))), candidate('01 Bath 4.80 ft²')),
            ('duplicate row', (PLAN, schedule(rows=('01 Bath 4.80 m²', '01 Bath 5.00 m²'))), candidate()),
            ('mixed apt schedule', (PLAN, schedule(rows=('01 Bath 4.80 m²', 'Apartment A-13'))), candidate()),
            ('different vision quote', (PLAN, schedule(rows=('01 Bath 4.8 m²',))), candidate('01 Bath 9.80 m²')),
        ]
        for count, (name, sheets, row) in enumerate(cases, 1):
            with self.subTest(name=name):
                api.return_value = model(rooms=[row])
                self.upload(booklet(*sheets))
                recognized = PlanAnalysis.objects.order_by('-pk').first().rooms[0]
                self.assertIsNone(recognized['area'])
                self.assertEqual(recognized['page'], 1)
                self.assertNotIn('schedule_floor_page', recognized)
                self.assertEqual(api.call_count, count)

    @patch('projects.plan_analysis.responses_create')
    def test_unreadable_and_old_cached_results_are_not_resubmitted(self, api):
        raw = booklet(PLAN, schedule())
        api.return_value = model(rooms=[candidate('')])
        self.upload(raw)
        self.assertIsNone(PlanAnalysis.objects.get().rooms[0]['area'])
        api.return_value = model(rooms=[candidate()])
        self.upload(raw, 'renamed.pdf')
        api.assert_called_once()
        self.assertEqual(PlanAnalysis.objects.count(), 1)
        self.assertEqual(PlanAnalysisBudget.objects.get().reserved_cents, 20)

    @patch('projects.plan_analysis.responses_create')
    def test_schedule_heading_cannot_establish_geometry_even_if_provider_mistakes_it(self, api):
        api.return_value = model(rooms=[candidate()])
        self.upload(booklet(schedule()))
        analysis = PlanAnalysis.objects.get()
        self.assertEqual((analysis.status, analysis.error_code, analysis.rooms), ('failed', 'not_floor_plan', []))
        self.assertFalse(WholePlanEstimate.objects.exists())
        api.assert_called_once()

    @patch('projects.plan_analysis.responses_create')
    def test_does_not_override_valid_on_plan_measurement(self, api):
        api.return_value = model(rooms=[{**room(area=5), 'schedule_evidence': '01 Bath 4.80 m²'}])
        self.upload(booklet(PLAN, schedule()))
        recognized = PlanAnalysis.objects.get().rooms[0]
        self.assertEqual((recognized['page'], recognized['area']), (1, '5.00'))
        self.assertNotIn('schedule_floor_page', recognized)

    @patch('projects.plan_analysis.responses_create')
    def test_scan_without_text_does_not_turn_model_quote_into_verified_source(self, api):
        api.return_value = model(rooms=[candidate()])
        self.upload(booklet(PLAN, (None, ('Room schedule', 'Apartment A-12', '01 Bath 4.80 m²'))))
        recognized = PlanAnalysis.objects.get().rooms[0]
        self.assertEqual((recognized['page'], recognized['area'], recognized['source']), (1, None, 'unknown'))
        self.assertFalse(recognized['evidence'])
        api.assert_called_once()

    @patch('projects.plan_analysis.responses_create')
    def test_manual_area_stops_displaying_previous_schedule_as_source(self, api):
        api.return_value = model(rooms=[candidate()])
        response = self.upload(booklet(PLAN, schedule()))
        estimate = WholePlanEstimate.objects.get()
        updated = self.client.post(response.url, {'action': 'update', 'estimate_id': estimate.pk,
                                                  'room': 0, 'area': '5.25', 'name': 'Bath'})
        self.assertEqual(updated.status_code, 302)
        current = WholePlanEstimate.objects.latest('pk')
        stored_room = current.snapshot['rooms'][0]
        self.assertEqual((stored_room['source'], stored_room['area'], stored_room['page']), ('manual', '5.25', 1))
        self.assertFalse(stored_room.get('schedule_floor_page'))
        self.assertFalse(stored_room.get('line'))
        self.assertFalse(stored_room['evidence'])
        self.assertNotContains(self.client.get(updated.url), 'Экспликация помещений')
        api.assert_called_once()

    @patch('projects.plan_analysis.responses_create')
    def test_room_rename_cannot_relabel_verified_schedule_source(self, api):
        api.return_value = model(rooms=[candidate()])
        response = self.upload(booklet(PLAN, schedule()))
        estimate = WholePlanEstimate.objects.get()
        updated = self.client.post(response.url, {'action': 'update', 'estimate_id': estimate.pk,
                                                  'room': 0, 'name': 'Utility room'})
        self.assertEqual(updated.status_code, 302)
        stored_room = WholePlanEstimate.objects.latest('pk').snapshot['rooms'][0]
        self.assertEqual((stored_room['source'], stored_room['area'], stored_room['page']), ('manual', '4.80', 1))
        self.assertNotContains(self.client.get(updated.url), 'Экспликация помещений')
        api.assert_called_once()
