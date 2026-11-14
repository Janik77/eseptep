from io import BytesIO
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from pathlib import Path
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter
from .models import ProjectUpload
from .forms import ProjectUploadForm


def image_file():
    buf = BytesIO()
    Image.new('RGB', (8, 8), 'white').save(buf, 'PNG')
    return SimpleUploadedFile('synthetic.png', buf.getvalue(), 'image/png')


class PrivateUploadTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name,
                                                    MEDIA_ROOT=self.directory.name + '/public')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.owner = get_user_model().objects.create_user('owner', password='synthetic-only')
        self.other = get_user_model().objects.create_user('other', password='synthetic-only')
        self.url = reverse('projects:upload')

    def upload(self, client):
        response = client.post(self.url, {'file': image_file(), 'action': 'upload'})
        self.assertEqual(response.status_code, 200)
        return ProjectUpload.objects.latest('pk')

    def test_owner_only_download_and_estimate(self):
        self.client.force_login(self.owner)
        item = self.upload(self.client)
        download = reverse('projects:download', args=[item.pk])
        response = self.client.get(download)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', response['Content-Disposition'])
        response.close()
        for client in [Client()]:
            self.assertEqual(client.get(download).status_code, 404)
            self.assertEqual(client.post(self.url, {'action': 'estimate', 'upload_id': item.pk,
                                                    'area': '20', 'repair_level': 'standard'}).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'action': 'estimate', 'upload_id': item.pk,
                                                    'area': '20', 'repair_level': 'standard'}).status_code, 404)
        item.refresh_from_db()
        self.assertIsNone(item.area)

    def test_guest_session_and_legacy_orphan(self):
        item = self.upload(self.client)
        self.assertTrue(item.guest_session_key)
        response = self.client.get(reverse('projects:download', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(Client().get(reverse('projects:download', args=[item.pk])).status_code, 404)
        item.guest_session_key = ''
        item.save()
        self.assertEqual(self.client.get(reverse('projects:download', args=[item.pk])).status_code, 404)

    def test_legacy_media_url_is_not_public(self):
        self.assertEqual(self.client.get('/media/project_uploads/old.html').status_code, 404)
        self.assertEqual(self.client.get('/media/projects/old.pdf').status_code, 404)

    def test_invalid_files_do_not_create_records(self):
        for name, content in [('file.html', b'<html>hello</html>'), ('fake.png', b'<html>not image</html>'),
                              ('fake.pdf', b'%PDF-1.7\nnot a pdf\n%%EOF'), ('file.dwg', b'AC1027fake')]:
            with self.subTest(name=name):
                response = self.client.post(self.url, {'file': SimpleUploadedFile(name, content), 'action': 'upload'})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['upload_form'].errors)
                self.assertFalse(ProjectUpload.objects.exists())

    @override_settings(PROJECT_UPLOAD_MAX_BYTES=10)
    def test_oversize_rejected(self):
        self.assertFalse(ProjectUploadForm({}, {'file': image_file()}).is_valid())

    def test_pdf_valid_and_active_rejected(self):
        for active in [False, True]:
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            if active:
                writer.add_js('app.alert("synthetic validation test")')
            data = BytesIO()
            writer.write(data)
            form = ProjectUploadForm({}, {'file': SimpleUploadedFile('plan.pdf', data.getvalue())})
            self.assertEqual(form.is_valid(), not active, form.errors)

    def test_bad_estimates_leave_record_unchanged(self):
        item = self.upload(self.client)
        for area in ['', 'abc', '0', '-1', 'NaN', 'Infinity', '-Infinity', '1000000', '1.123']:
            response = self.client.post(self.url, {'action': 'estimate', 'upload_id': item.pk,
                                                 'area': area, 'repair_level': 'standard'})
            self.assertEqual(response.status_code, 200, area)
            self.assertTrue(response.context['estimate_form'].errors, area)
            item.refresh_from_db()
            self.assertIsNone(item.area)
        response = self.client.post(self.url, {'action': 'estimate', 'upload_id': item.pk,
                                              'area': '12,5', 'repair_level': 'not-valid'})
        self.assertTrue(response.context['estimate_form'].errors)
        response = self.client.post(self.url, {'action': 'estimate', 'upload_id': item.pk,
                                              'area': '12,5', 'repair_level': 'standard'})
        self.assertEqual(response.context['estimate']['total'], 2125000)
        self.assertEqual(self.client.post(self.url, {'action': 'estimate', 'upload_id': 'oops'}).status_code, 404)

    def test_legacy_copy_preserves_owner_and_public_source(self):
        root = Path(self.directory.name) / 'public'
        (root / 'project_uploads').mkdir(parents=True)
        original = root / 'project_uploads/legacy.png'
        original.write_bytes(image_file().read())
        item = ProjectUpload.objects.create(user=self.owner, file='project_uploads/legacy.png')
        output = BytesIO()
        call_command('copy_legacy_private_uploads', stdout=__import__('io').StringIO())
        self.assertFalse((Path(self.directory.name) / item.file.name).exists())
        call_command('copy_legacy_private_uploads', apply=True, stdout=__import__('io').StringIO())
        self.assertEqual((Path(self.directory.name) / item.file.name).read_bytes(), original.read_bytes())
        self.assertTrue(original.exists())
        self.client.force_login(self.owner)
        response = self.client.get(reverse('projects:download', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        response.close()

    @override_settings(DEBUG=True)
    def test_media_traversal_cannot_reach_existing_legacy_file(self):
        root = Path(self.directory.name) / 'public'
        (root / 'project_uploads').mkdir(parents=True)
        (root / 'project_uploads/legacy.html').write_text('<html>synthetic legacy</html>')
        (root / 'avatars').mkdir()
        (root / 'avatars/public.png').write_bytes(image_file().read())
        for path in ['/media/project_uploads/legacy.html',
                     '/media/x/../project_uploads/legacy.html',
                     '/media/x/%2e%2e/project_uploads/legacy.html',
                     '/media/avatars/../project_uploads/legacy.html',
                     '/media/avatars/%2e%2e/project_uploads/legacy.html',
                     '/media/avatars/%252e%252e/project_uploads/legacy.html']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        response = self.client.get('/media/avatars/public.png')
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_pdf_file_attachment_annotation_rejected(self):
        from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject, NumberObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=72, height=72)
        stream = DecodedStreamObject()
        stream.set_data(b'synthetic attachment, not malware')
        stream[NameObject('/Type')] = NameObject('/EmbeddedFile')
        specification = DictionaryObject({NameObject('/Type'): NameObject('/Filespec'),
            NameObject('/F'): TextStringObject('test.txt'),
            NameObject('/EF'): DictionaryObject({NameObject('/F'): writer._add_object(stream)})})
        annotation = DictionaryObject({NameObject('/Type'): NameObject('/Annot'),
            NameObject('/Subtype'): NameObject('/FileAttachment'),
            NameObject('/Rect'): ArrayObject([NumberObject(0)] * 4),
            NameObject('/FS'): writer._add_object(specification)})
        page[NameObject('/Annots')] = ArrayObject([writer._add_object(annotation)])
        data = BytesIO()
        writer.write(data)
        form = ProjectUploadForm({}, {'file': SimpleUploadedFile('attachment.pdf', data.getvalue())})
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
