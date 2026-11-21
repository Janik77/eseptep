"""Loopback-only temporary demo. Does not read or edit the usual demo database."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
HOST, PORT = '127.0.0.1', 8241


def run():
    with socket.socket() as sock:
        if sock.connect_ex((HOST, PORT)) == 0:
            raise SystemExit(f'Port {PORT} is already occupied; no demo data was created.')

    with TemporaryDirectory(prefix='eseptep-repair-preview-') as directory:
        base = Path(directory)
        media = base / 'private-media'
        media.mkdir()
        # Clear provider inputs and outbound proxy configuration from the child.
        env = {key: value for key, value in os.environ.items()
               if not any(marker in key.upper() for marker in ('OPENAI', 'SMTP', 'EMAIL', 'PROXY'))}
        env.update({
            'DJANGO_ENV': 'test', 'DJANGO_DEBUG': 'true', 'DJANGO_ALLOWED_HOSTS': HOST,
            'DJANGO_PRIVATE_MEDIA_ROOT': str(media),
            'DJANGO_DB_PATH': str(base / 'repair-browser.sqlite3'),
            'PLAN_AI_ENABLED': '0', 'ESTIMATE_AI_ENABLED': '0', 'OPENAI_LIVE_CONFIRMED': '0',
            'OPENAI_API_KEY': '', 'ESEPTEP_REPAIR_BROWSER_QA': '1', 'ESEPTEP_DEMO_MODE':'1',
            'DJANGO_SECRET_KEY': 'local-only-repair-qa-preview-not-a-real-production-secret',
        })
        for key in tuple(env):
            if key.startswith('POSTGRES_') or key in ('DATABASE_URL', 'DJANGO_DATABASE_URL'):
                env.pop(key)
        subprocess.run([sys.executable, '-B', 'tools/seed_repair_browser_qa.py', directory],
                       cwd=ROOT, env=env, check=True)
        project = json.loads((base / 'repair-fixture.json').read_text(encoding='ascii'))['ru']
        print(f'http://{HOST}:{PORT}/accounts/login/?next=/repair/{project}/', flush=True)
        print('Client: repair-client@example.test | Password: Repair-local-QA-only!', flush=True)
        print('Synthetic data only. Stop with Ctrl+C; the temporary database is discarded.', flush=True)
        try:
            return subprocess.call([sys.executable, '-B', 'manage.py', 'runserver', f'{HOST}:{PORT}', '--noreload'],
                                   cwd=ROOT, env=env)
        except KeyboardInterrupt:
            return 0


if __name__ == '__main__':
    raise SystemExit(run())
