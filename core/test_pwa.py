from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image


class PwaTests(TestCase):
    def test_manifest_identity_root_scope_and_icon_assets(self):
        url = reverse('core:pwa_manifest')
        ru = self.client.get(url)
        kk = self.client.get(url, HTTP_ACCEPT_LANGUAGE='kk')
        self.assertEqual(ru['Content-Type'], 'application/manifest+json')
        self.assertEqual(ru.json(), kk.json())
        manifest = ru.json()
        self.assertEqual((manifest['id'], manifest['scope'], manifest['start_url'], manifest['display']),
                         ('/', '/', '/', 'standalone'))
        self.assertEqual([(x['sizes'], x['purpose']) for x in manifest['icons']],
                         [('192x192', 'any'), ('512x512', 'any'), ('512x512', 'maskable')])
        for icon in manifest['icons']:
            with Image.open(Path(settings.BASE_DIR, 'static', 'pwa', Path(icon['src']).name)) as image:
                self.assertEqual(image.size, tuple(map(int, icon['sizes'].split('x'))))
        with Image.open(Path(settings.BASE_DIR, 'static/pwa/icon-apple-180.png')) as image:
            self.assertEqual(image.size, (180, 180))
        self.assertContains(self.client.get('/'), 'rel="manifest"')
        self.assertContains(self.client.get('/'), 'rel="apple-touch-icon"')

    def test_worker_root_scope_only_and_no_disk_cache_code(self):
        response = self.client.get(reverse('core:pwa_worker'))
        self.assertEqual(reverse('core:pwa_worker'), '/service-worker.js')
        self.assertTrue(response['Content-Type'].startswith('text/javascript'))
        self.assertEqual(response['Cache-Control'], 'no-cache')
        script = b''.join(response.streaming_content).decode()
        self.assertNotIn('caches.', script)
        self.assertNotIn('registration.sync', script)
        self.assertIn("request.method !== 'GET' || request.mode !== 'navigate'", script)

    def test_installation_guide_uses_existing_language_cookie(self):
        route = reverse('core:pwa_install')
        self.assertContains(self.client.get(route), 'Установить ESEPTEP')
        result = self.client.post(reverse('set_language'), {'language': 'kk', 'next': route}, follow=True)
        self.assertContains(result, 'ESEPTEP-ті орнату')
        self.assertContains(result, 'Веб-қолданба ретінде ашу')
        self.assertContains(self.client.get('/'), 'Телефонға орнату')
        self.assertContains(self.client.get(route), 'lang="kk"')

    def test_sensitive_and_mutating_responses_are_private_even_for_anonymous(self):
        for path in ('/accounts/login/', '/projects/upload/', '/dashboard/client/', '/admin/', '/media/unknown.pdf'):
            response = self.client.get(path)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', self.client.post(reverse('set_language'), {'language': 'ru'}).headers['Cache-Control'])
        self.client.force_login(get_user_model().objects.create_user(username='pwa-owner'))
        self.assertIn('no-store', self.client.get('/').headers['Cache-Control'])
