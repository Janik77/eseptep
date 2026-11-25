"""Drive the existing contract workflow with a disposable fixture, never live AI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8250'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def require_demo():
    try:
        with OPENER.open(BASE + '/', timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def ready(process, folder):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError('Isolated demo exited before ready.')
        scenario = folder / 'scenario.json'
        if scenario.is_file() and require_demo():
            data = json.loads(scenario.read_text(encoding='utf-8'))
            assert data['mode'] == 'mock' and data['base'] == BASE
            return data
        time.sleep(.1)
    raise RuntimeError('Isolated demo did not start.')


def exercise(page, project, out, name):
    page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(BASE + '/') else route.abort())
    failures = []
    page.on('pageerror', lambda error: failures.append(str(error)))
    page.goto(BASE + '/accounts/login/')
    page.locator('[name=username]').fill('demo-client@example.test')
    page.locator('[name=password]').fill('Demo-Meeting-2026!')
    page.locator('.auth-form button[type=submit]').click()
    page.wait_for_url('**/dashboard/**')
    page.goto(BASE + project)
    offer = page.locator('[data-repair-offer="materials"] form')
    if offer.count():
        offer.locator('[name=confirm]').check()
        offer.locator('button[type=submit]').click()
    page.locator('[data-repair-agreement="materials"]').wait_for()
    page.locator('[data-contract-entry]').click()
    page.locator('a[href$="/materials/"]').click()

    def form(action):
        return page.locator(f'form:has(input[name=action][value={action}])')

    def screen(label):
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(out / f'{name}-{label}.png'), full_page=True)
        if page.video:
            page.wait_for_timeout(1000)  # Keep each verified screen readable in the clip.

    if form('create').count():
        screen('two-choices')
        form('create').locator('button[value=template]').click()
    assert '12 упак. × 1000.00 ₸' in page.locator('#draft').inner_text()
    assert 'стоимость доставки' in page.locator('#draft').inner_text().lower()
    screen('template')
    if name == 'desktop':
        return

    current = page.locator('#draft .contract-comparison')
    edit = form('manual')
    edit.locator('xpath=ancestor::details[1]/summary').click()
    edit.locator('[name=date]').fill('2026-11-30')
    edit.locator('summary').click()
    changed = 'Две партии по 6 упаковок: 05.12.2026 и 08.12.2026.'
    edit.locator('[name=clause_delivery]').fill(changed)
    edit.locator('button[type=submit]').click()
    assert changed in page.locator('#draft').inner_text()
    assert not current.count()
    screen('edited-order')
    with page.expect_download() as doc:
        page.locator('#download a').filter(has_text='DOCX').click()
    doc.value.save_as(out / 'mobile-edited.docx')
    with page.expect_download() as pdf:
        page.locator('#download a').filter(has_text='PDF').click()
    pdf.value.save_as(out / 'mobile-edited.pdf')
    page.locator('#suggest summary').click()
    page.locator('a[href="?upload=1#source-panel"]').click()
    form('upload').locator('input[type=file]').set_input_files(str(ROOT / 'repairs/fixtures/ESEPTEP_original_DEMO-01.docx'))
    form('upload').locator('button[type=submit]').click()
    page.locator('[data-source-panel] form:has(input[value=use_source]) button').click()
    assert 'Текст загруженного договора' in page.locator('#draft').inner_text()
    screen('source-basis')
    page.locator('#source-edit summary').click()
    page.locator('#source-edit a[href^="?source_edit=p1#"]').click()
    patch = 'Заменён первый пункт. Остальные исходные условия сохранены.'
    form('source_patch').locator('[name=text]').fill(patch)
    form('source_patch').locator('button[type=submit]').click()
    assert patch in page.locator('#draft').inner_text()
    screen('source-edited')
    assert not failures, failures


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--out', type=Path, required=True)
    cli.add_argument('--video', action='store_true', help='Requires already installed Playwright ffmpeg.')
    args = cli.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory(prefix='eseptep-contract-browser-') as tmp:
        fixture = Path(tmp) / 'fixture'
        env = {**os.environ, 'TMPDIR': str(fixture.parent), 'PYTHONDONTWRITEBYTECODE': '1'}
        # The fixture launcher overwrites the local app's provider config with a synthetic provider.
        with TemporaryDirectory(prefix='eseptep-contract-launch-') as logs:
            with (Path(logs) / 'output.log').open('wb') as log:
                process = subprocess.Popen(
                    [sys.executable, '-B', str(ROOT / 'tools/run_contract_demo.py'), '--fixture-api', str(fixture)],
                    cwd=ROOT, env=env, stdout=log, stderr=log,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                try:
                    data = ready(process, fixture)
                    with sync_playwright() as p:
                        browser = p.chromium.launch(channel='chrome', headless=True, chromium_sandbox=True)
                        try:
                            for name, viewport in [('desktop', {'width':1440,'height':900}), ('mobile', {'width':390,'height':844})]:
                                options = {'viewport':viewport, 'accept_downloads':True, 'is_mobile':name == 'mobile',
                                           'has_touch':name == 'mobile'}
                                if args.video and name == 'mobile':
                                    options['record_video_dir'] = str(args.out)
                                context = browser.new_context(**options)
                                try:
                                    exercise(context.new_page(), f"/repair/{data['project']}/", args.out, name)
                                finally:
                                    context.close()
                        finally:
                            browser.close()
                    print('BROWSER PASS: 1440 and 390; no external requests or paid calls')
                    print(str(args.out))
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)


if __name__ == '__main__':
    main()
