import os
import subprocess
import sys
from django.test import SimpleTestCase


class ProductionConfigurationTests(SimpleTestCase):
    def run_settings(self, **values):
        env = {k: v for k, v in os.environ.items() if not k.startswith('DJANGO_') and k != 'ESEPTEP_DEMO_MODE'}
        env.update(DJANGO_ENV='production', PYTHON_DOTENV_DISABLED='1', **values)
        return subprocess.run([sys.executable, '-c', 'import config.settings'], env=env, capture_output=True, text=True)

    def test_missing_secret_fails_closed(self):
        result = self.run_settings()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_missing_hosts_fails_closed(self):
        result = self.run_settings(DJANGO_SECRET_KEY='test-only-abcdef0123456789' * 4)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_ALLOWED_HOSTS', result.stderr)

    def test_complete_configuration_loads(self):
        result = self.run_settings(DJANGO_SECRET_KEY='test-only-abcdef0123456789' * 4,
                                   DJANGO_ALLOWED_HOSTS='example.test', DJANGO_PRIVATE_MEDIA_ROOT='/tmp/private-test')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_demo_mode_rejected_in_production(self):
        result = self.run_settings(DJANGO_SECRET_KEY='test-only-abcdef0123456789' * 4,
                                   DJANGO_ALLOWED_HOSTS='example.test', DJANGO_PRIVATE_MEDIA_ROOT='/tmp/private-test',
                                   ESEPTEP_DEMO_MODE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Demo mode cannot run in production', result.stderr)
