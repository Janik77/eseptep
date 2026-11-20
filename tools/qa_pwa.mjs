import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium, webkit, devices } = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
const base = new URL(process.env.PWA_QA_URL || 'http://127.0.0.1:8201').origin;
assert.equal(new URL(base).hostname, '127.0.0.1', 'PWA QA must use an isolated loopback server');
const output = 'pwa-evidence';
const engine = process.argv[2];
assert.ok(['chrome', 'webkit'].includes(engine));
await mkdir(output, { recursive: true });
const record = { engine, checks: [] };
const ready = async (page) => {
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  assert.equal(await page.evaluate(async () => (await navigator.serviceWorker.ready).scope), base + '/');
};
async function menu(page) {
  await page.goto(base + '/');
  await page.locator('.site-app-footer a[href="/install/"]').click();
  await page.locator('h1').filter({ hasText: 'ESEPTEP на телефоне' }).waitFor();
}
async function toggleKk(page) {
  await page.locator('.language-switch button[value=kk]').click();
  await page.locator('html[lang=kk]').waitFor();
}
async function noOverflow(page) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
}
async function login(page) {
  await page.goto(base + '/accounts/login/');
  await page.locator('[name=username]').fill('browser-qa@example.test');
  await page.locator('[name=password]').fill('Synthetic-QA-Only-815!');
  await page.locator('[name=password]').press('Enter');
  await page.waitForURL('**/accounts/dashboard/client/');
  await page.getByText('QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', { exact: true }).waitFor();
}
async function offlineChecks(context, page) {
  await ready(page);
  const probe = await context.newPage();
  await probe.goto(base + '/accounts/dashboard/client/');
  await probe.getByText('QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', { exact: true }).waitFor();
  await context.setOffline(true);
  try {
    const response = await page.goto(base + '/');
    assert.equal(response.status(), 503);
    assert.equal(response.headers()['cache-control'], 'no-store');
    await page.getByRole('heading', { name: 'Нет подключения' }).waitFor();
    await page.getByRole('heading', { name: 'Интернет байланысы жоқ' }).waitFor();
    assert.ok(!(await page.locator('body').innerText()).includes('QA project'));
    await page.screenshot({ path: output + '/offline.png' });
    // Probe from a normal app document, not the offline page's restrictive CSP.
    const results = await probe.evaluate(async () => ({
      cacheKeys: await caches.keys(),
      syncTags: (await navigator.serviceWorker.ready).sync ? await (await navigator.serviceWorker.ready).sync.getTags() : [],
      failures: await Promise.all(['/accounts/dashboard/client/', '/media/unknown.pdf', '/accounts/calculations/1/explain/'].map(async (path) => {
        try { await fetch(path); return false; } catch { return true; }
      })),
      mutationFails: await fetch('/projects/upload/', {method: 'POST', body: 'offline-only-qa'}).then(() => false, () => true),
    }));
    assert.deepEqual(results, {cacheKeys: [], syncTags: [], failures: [true,true,true], mutationFails: true});
    await assert.rejects(probe.goto(base + '/accounts/dashboard/client/'), /net::ERR_/);
  } finally { await context.setOffline(false); await probe.close(); }
  await page.goto(base + '/accounts/dashboard/client/');
  await page.getByText('QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', { exact: true }).waitFor();
  assert.equal(await page.locator('html').getAttribute('lang'), 'kk');
  record.checks.push('Offline returns only bilingual static public 503; zero CacheStorage keys; private page, file, API and POST inaccessible offline; project returns online');
}
if (engine === 'chrome') {
  const dir = await mkdtemp(join(tmpdir(), 'eseptep-chrome-pwa-'));
  const context = await chromium.launchPersistentContext(dir, { channel: 'chrome', headless: false, chromiumSandbox: true, viewport: null, locale: 'ru-RU' });
  let cdp;
  try {
    const page = await context.newPage();
    await menu(page);
    await ready(page);
    cdp = await context.newCDPSession(page);
    const { url: manifestUrl, errors } = await cdp.send('Page.getAppManifest');
    assert.equal(manifestUrl, base + '/manifest.webmanifest');
    assert.deepEqual(errors, []);
    assert.deepEqual((await cdp.send('Page.getInstallabilityErrors')).installabilityErrors, []);
    record.checks.push('Real Chrome reports no manifest or installability errors');
    await login(page);
    await toggleKk(page);
    const manifestId = base + '/';
    await cdp.send('PWA.install', { manifestId });
    const newApp = context.waitForEvent('page', { timeout: 15000 });
    await cdp.send('PWA.launch', { manifestId });
    const app = await newApp;
    await app.waitForLoadState();
    await app.waitForFunction(() => matchMedia('(display-mode: standalone)').matches);
    assert.equal(new URL(app.url()).pathname, '/');
    assert.equal(await app.locator('html').getAttribute('lang'), 'kk');
    await app.goto(base + '/accounts/dashboard/client/');
    await app.getByText('QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', { exact: true }).waitFor();
    assert.equal(await app.locator('html').getAttribute('lang'), 'kk');
    await app.goto(base + '/install/');
    await app.locator('[data-installed-app]:not([hidden])').waitFor();
    await noOverflow(app);
    await app.screenshot({ path: output + '/chrome-installed-kk.png', fullPage: true });
    record.checks.push('Actual Chrome PWA.install + PWA.launch started root in an app window and retained real login, Kazakh locale and saved project');
    await offlineChecks(context, app);
    await cdp.send('PWA.uninstall', { manifestId });
  } finally {
    await context.close();
    await rm(dir, { recursive: true, force: true });
  }
} else {
  const browser = await webkit.launch();
  const context = await browser.newContext({ ...devices['iPhone 15'], locale: 'ru-RU' });
  try {
    const page = await context.newPage();
    await menu(page);
    await noOverflow(page);
    const guide = page.locator('.pwa-back');
    await guide.focus();
    assert.ok(await guide.evaluate(el => el.getBoundingClientRect().height >= 44));
    await page.screenshot({ path: output + '/webkit-phone-ru.png', fullPage: true });
    await toggleKk(page);
    await page.getByRole('heading', { name: 'Телефондағы ESEPTEP' }).waitFor();
    await noOverflow(page);
    await page.screenshot({ path: output + '/webkit-phone-kk.png', fullPage: true });
    await login(page);
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('lang'), 'kk');
    await page.getByText('QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', { exact: true }).waitFor();
    record.checks.push('WebKit phone viewport RU/KK, installation guide, layout, actual login and project persist on reload; not Safari OS installation');
  } finally { await browser.close(); }
}
await writeFile(output + '/' + engine + '.json', JSON.stringify(record, null, 2) + '\n');
console.log(record);
