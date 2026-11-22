/** Full synthetic closed-repair QA in mobile Chromium; no external traffic. */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';

const {chromium} = createRequire(import.meta.url)(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
const base = new URL(process.env.REPAIR_QA_BASE || 'http://127.0.0.1:8241');
assert.equal(base.hostname, '127.0.0.1', 'only the isolated local fixture is permitted');
const out = process.env.REPAIR_QA_DIR;
assert(out, 'explicit disposable fixture directory required');
const fixture = JSON.parse(await fs.readFile(path.join(out, 'repair-fixture.json')));
const videoDir = path.join(out, 'recordings');
await fs.mkdir(videoDir, {recursive: true});
const viewport = {width:390, height:844};
const browser = await chromium.launch({
  ...(process.env.CHROMIUM_EXECUTABLE_PATH ? {executablePath: process.env.CHROMIUM_EXECUTABLE_PATH} : {channel:'chrome'}),
  chromiumSandbox:true,
});
const errors = [];
const evidence = [];
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4n0AAAAASUVORK5CYII=', 'base64');
const action = (page,name) => page.locator(`form:has(input[name=action][value=${name}])`);
const url = (id) => new URL(`/repair/${id}/`, base).href;

async function session(role, locale, record=false) {
  const context = await browser.newContext({viewport,isMobile:true,hasTouch:true, ...(record ? {recordVideo:{dir:videoDir,size:viewport}} : {})});
  await context.route('**/*', (route) => new URL(route.request().url()).origin === base.origin ? route.continue() : route.abort());
  const page = await context.newPage();
  page.on('pageerror', err => errors.push(err.message));
  await page.goto(new URL('/accounts/login/',base).href);
  const form = page.locator('.auth-form');
  await form.locator('input[name=username]').fill(`repair-${role}@example.test`);
  await form.locator('input[name=password]').fill('Repair-local-QA-only!');
  await form.locator('button[type=submit]').click();
  await page.locator(`[data-language-form] button[value="${locale}"]`).click();
  await page.waitForFunction(lang => document.documentElement.lang === lang, locale);
  return {page,context};
}
async function go(page, id) {
  const res=await page.goto(url(id));
  assert.equal(res.status(),200);
  await page.locator('[data-repair-page]').waitFor();
}
async function submit(form) {
  const page=form.page();
  const response = page.waitForResponse(res => res.request().method() === 'POST' && new URL(res.url()).pathname.endsWith('/action/'));
  await form.locator('button[type=submit]').click();
  const result=await response;
  assert.equal(result.status(),302,`Form failed: ${await page.locator('[role=alert]').allTextContents()}`);
  await page.waitForURL(target=>target.pathname.match(/^\/repair\/\d+\/$/));
}
async function picture(page, name) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'phone layout overflows');
  await page.screenshot({path:path.join(out,`${name}.png`), fullPage:true});
}

try {
  for (const locale of ['ru','kk']) {
    const id=fixture[locale];
    const client=await session('client',locale,true);
    const supplier=await session('supplier',locale);
    const master=await session('master',locale);
    const outsider=await session('client-unrelated',locale);
    const reviewer=await session('admin',locale);
    const buyer=client.page, shop=supplier.page, worker=master.page;
    await go(buyer,id);
    assert.match(await buyer.locator('h1').innerText(),locale==='ru'?/Мой ремонт/:/Менің жөндеуім/);
    assert.equal(await buyer.locator('.repair-hero .btn--primary').count(),1);
    for (const kind of ['materials','works']) {
      const accept=buyer.locator(`[data-repair-offer="${kind}"] form`);
      await accept.locator('[name=confirm]').check();
      await submit(accept);
    }
    await go(shop,id);
    assert.equal(await shop.locator('[data-repair-agreement="works"]').count(),0);
    await go(worker,id);
    assert.equal(await worker.locator('[data-repair-agreement="materials"]').count(),0);
    assert.equal((await worker.locator('[data-repair-page]').textContent()).includes('Синтетический адрес QA'),false);
    for (const [quantity,received,day] of [[12,10,22],[2,2,23]]) {
      await go(shop,id);
      const schedule=action(shop,'schedule_delivery');
      await schedule.locator('[name=window_start]').fill(`2026-11-${day}T10:00`);
      await schedule.locator('[name=window_end]').fill(`2026-11-${day}T13:00`);
      await schedule.locator('[name=qty_1]').fill(String(quantity));
      await submit(schedule);
      assert.match(await shop.locator('[data-repair-page]').textContent(),/Синтетический адрес QA 123/);
      await go(buyer,id);
      const confirm=action(buyer,'confirm_delivery');
      await confirm.locator('[name=received_1]').fill(String(received));
      const form=await confirm.evaluate(n=>Object.fromEntries(new FormData(n)));
      const endpoint=new URL(await confirm.getAttribute('action'),buyer.url()).href;
      await submit(confirm);
      if (received===10) {
        assert.match(await buyer.locator('[data-repair-delivery]').first().innerText(),locale==='ru'?/Не получено в этой поставке:\s*2/:/Осы жеткізілімде алынбады:\s*2/);
        const replay=await client.context.request.post(endpoint,{form,maxRedirects:0,headers:{Referer:url(id)}});
        assert.equal(replay.status(),302,'same token replay must be accepted without appending a second receipt');
        await go(buyer,id);
        assert.equal(await buyer.locator('[data-repair-delivery]').count(),1);
        const entries=buyer.locator('[data-repair-agreement="materials"] [data-repair-history] li');
        assert.equal(await entries.filter({hasText: locale==='ru'?'Получение отмечено':'Қабылдау белгіленді'}).count(),1);
        assert.match(await buyer.locator('[data-repair-outstanding]').innerText(),/2/);
        await picture(buyer,`partial-${locale}-390`);
      }
    }
    assert.match(await buyer.locator('[data-repair-outstanding]').innerText(),locale==='ru'?/Все согласованные материалы получены/:/Келісілген материалдардың бәрі қабылданды/);
    await go(worker,id);
    const stage=action(worker,'plan_stage');
    await stage.locator('[name=title]').fill(locale==='ru'?'Укладка в спальне':'Жатын бөлмедегі төсем');
    await stage.locator('[name=due_on]').fill('2026-11-24');
    await submit(stage);
    for (let round=0;round<2;round++) {
      await go(worker,id);
      const proof=action(worker,'submit_stage');
      await proof.locator('[name=photo]').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:png});
      await proof.locator('[name=comment]').fill(round===0?'QA · 1':'QA · 2');
      await submit(proof);
      await go(buyer,id);
      const photo=buyer.locator('[data-repair-stage] img').last();
      const photoPath=await photo.getAttribute('src');
      const media=await client.context.request.get(new URL(photoPath,base).href);
      assert.equal(media.status(),200);
      assert.match(media.headers()['cache-control'],/private, no-store/);
      const hidden=await outsider.context.request.get(new URL(photoPath,base).href);
      assert.equal(hidden.status(),404);
      assert.equal((await supplier.context.request.get(new URL(photoPath,base).href)).status(),404);
      if (round===0) {
        const fix=action(buyer,'request_fix');
        await fix.locator('..').locator('summary').click();
        await fix.locator('[name=comment]').fill(locale==='ru'?'Исправьте стык у двери':'Есік жанындағы түйіспені түзетіңіз');
        await submit(fix);
      } else {
        const issue=action(buyer,'report_issue').last();
        await issue.locator('..').locator('summary').click();
        await issue.locator('[name=comment]').fill('QA · demo issue');
        await submit(issue);
        await go(reviewer.page,id);
        await action(reviewer.page,'resolve_issue').locator('[name=comment]').fill('QA · reviewed');
        await submit(action(reviewer.page,'resolve_issue'));
        await go(buyer,id);
        await submit(action(buyer,'accept_stage'));
      }
    }
    assert.match(await buyer.locator('[data-repair-stage] .repair-badge').innerText(),locale==='ru'?/Принято/:/Қабылданды/);
    await picture(buyer,`complete-${locale}-390`);
    for (const denied of [
      client.context.request.get(url(fixture.disabled)),
      client.context.request.get(url(fixture.sameCityDisabled)),
      outsider.context.request.get(url(id)),
    ]) assert.equal((await denied).status(),404);
    const video=buyer.video();
    await client.context.close();
    await video.saveAs(path.join(out,`my-repair-${locale}-390.webm`));
    for (const user of [supplier,master,reviewer,outsider]) await user.context.close();
    evidence.push({locale,width:390,partial:[12,10,2],dedup:true,correctionAndAcceptance:true,staffResolution:true,scopeDenials:true});
  }
  assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(out,'repair-checks.json'),JSON.stringify({evidence,providerCalls:0,externalMessages:0},null,2));
  console.log(JSON.stringify(evidence));
} finally {
  await browser.close();
}
