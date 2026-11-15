/** Synthetic browser acceptance. No production network or credentials. */
import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
const base = 'http://127.0.0.1:8197';
const output = 'browser-evidence';
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ chromiumSandbox: true });
const evidence = { sha: execFileSync('git', ['rev-parse','HEAD'], {encoding:'utf8'}).trim(), checks: [] };
const languageForm = '[data-language-switch], [data-language-form]';
async function switchLanguage(page, lang) {
  await Promise.all([page.waitForNavigation(), page.locator(languageForm).locator(`button[value="${lang}"]`).first().click()]);
  await page.waitForFunction(lang => document.documentElement.lang === lang, lang);
}
async function overflow(page) {
  const sizes = await page.evaluate(() => ({scroll:document.documentElement.scrollWidth, width:innerWidth}));
  assert(sizes.scroll <= sizes.width + 1, `horizontal overflow: ${JSON.stringify(sizes)}`);
}
async function shot(page, name) {
  await page.evaluate(() => document.fonts.ready);
  await overflow(page);
  await page.screenshot({path:`${output}/${name}.png`, fullPage:true});
}
function countCalculations() {
  const result=execFileSync(process.env.PYTHON || 'python', ['manage.py','shell','-c','from accounts.models import Calculation; print("QA_COUNT="+str(Calculation.objects.count()))'], {encoding:'utf8'});
  return Number(result.match(/QA_COUNT=(\d+)/)[1]);
}
try {
  for (const width of [1440,390]) {
    const context=await browser.newContext({viewport:{width,height:width===1440?900:844}, reducedMotion:'reduce', permissions:['clipboard-read','clipboard-write']});
    const page=await context.newPage();
    const errors=[]; page.on('pageerror', error=>errors.push(error.message));
    for (const lang of ['ru','kk']) {
      await page.goto(base);
      await switchLanguage(page,lang);
      const cards=page.locator('.direction-card');
      assert.equal(await cards.count(),3);
      if(width===1440) for(const card of await cards.all()) {
        const box=await card.boundingBox(); assert(box && box.y+box.height<=900, 'all three paths above fold');
      }
      await shot(page,`home-${lang}-${width}`);
      await page.goto(`${base}/calculators/`);
      assert.equal(await page.locator('.work-card').count(),12);
      await shot(page,`catalog-${lang}-${width}`);
      const hrefs=await page.locator('.work-card').evaluateAll(cards=>cards.map(card=>card.matches('a')?card.href:card.querySelector('a')?.href));
      assert.equal(new Set(hrefs).size,12);
      for(const href of hrefs) {
        const response=await page.goto(href); assert.equal(response.status(),200);
        await overflow(page);
        assert.equal(await page.locator('[data-calc-form]').count(),1);
      }
      await page.goto(`${base}/calculators/plitka-keramogranit/`);
      await shot(page,`calculator-empty-${lang}-${width}`);
      await page.locator('[data-calc-form] [name=area]').fill('-1');
      await page.locator('[data-calc-form] button[type=submit]').click();
      await page.locator('[aria-invalid=true]').first().waitFor();
      await shot(page,`calculator-error-${lang}-${width}`);
      await switchLanguage(page, lang === 'ru' ? 'kk' : 'ru');
      await page.locator('[aria-invalid=true]').first().waitFor();
      assert.equal(await page.locator('[data-calc-form] [name=area]').inputValue(),'-1');
      await switchLanguage(page,lang);
      await page.locator('[data-calc-form] [name=area]').fill('36.5');
      await page.locator('[data-calc-form] button[type=submit]').click();
      await page.locator('[data-variant-button]').first().waitFor();
      await shot(page,`calculator-result-${lang}-${width}`);
      await page.locator('[data-copy-variant]').click();
      const text = await page.evaluate(()=>navigator.clipboard.readText());
      assert(text.includes('ESEPTEP') && text.length>50);
      if(lang==='kk') assert(!text.includes('Список составлен') && text.includes('Тізім'),'Kazakh copied list');
    }
    assert.deepEqual(errors,[],`browser console errors at ${width}`);
    evidence.checks.push(`RU/KK home/catalog/all12 calculators/error/result ${width}px`);
    await context.close();
  }
  const context=await browser.newContext({viewport:{width:1440,height:900}, permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage();
  await page.goto(`${base}/accounts/login/`);
  await page.locator('[name=username]').fill('browser-qa@example.test');
  await page.locator('[name=password]').fill('Synthetic-QA-Only-815!');
  const sent=[];
  page.on('request', req=>{ if(req.method()==='POST') sent.push({url:req.url(),body:req.postData()}); });
  await page.locator(languageForm).locator('button[value=kk]').click();
  await page.waitForFunction(()=>document.documentElement.lang==='kk');
  assert.equal(await page.locator('[name=password]').inputValue(),'Synthetic-QA-Only-815!');
  assert(sent.every(x=>x.url.includes('/i18n/setlang/')&&!x.body?.includes('Synthetic-QA-Only')),'password never submitted by switch');
  const storage=await page.evaluate(()=>JSON.stringify([Object.entries(localStorage),Object.entries(sessionStorage)]));
  assert(!storage.includes('Synthetic-QA-Only'),'password never stored');
  await page.locator('.auth-form button[type=submit]').click();
  await page.waitForURL(/dashboard/);
  await page.goto(`${base}/calculators/plitka-keramogranit/`);
  await page.locator('[data-calc-form] [name=area]').fill('36.5');
  await switchLanguage(page,'kk');
  assert.equal(await page.locator('[data-calc-form] [name=area]').inputValue(),'36.5');
  const before=countCalculations();
  await page.locator('[data-calc-form] button[type=submit]').click();
  await page.locator('[data-variant-button]').first().waitFor();
  const variant=page.locator('[data-variant-button]').last();
  await variant.click();
  const chosen=await variant.getAttribute('data-variant-button');
  await page.locator('[name=project_id]').selectOption({label:'QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І'});
  const project=await page.locator('[name=project_id]').inputValue();
  await switchLanguage(page,'ru');
  assert.equal(await page.locator('[data-calc-form] [name=area]').inputValue(),'36.5');
  assert.equal(await page.locator('[name=project_id]').inputValue(),project);
  assert.equal(await page.locator('[data-selected-variant-input]').inputValue(),chosen);
  assert.equal(countCalculations(),before,'language switch must not save');
  await page.locator('[data-copy-variant]').click();
  const copied=await page.evaluate(()=>navigator.clipboard.readText());
  assert(copied.includes('ESEPTEP') && copied.length>50,'actual clipboard result');
  await page.locator('button[name=action][value=save_estimate]').click();
  await page.waitForURL(/accounts\/calculations\//);
  assert.equal(countCalculations(),before+1);
  await page.reload();
  await switchLanguage(page,'kk');
  assert.equal(countCalculations(),before+1,'refresh and language must not duplicate');
  await shot(page,'saved-calculation-kk-1440');
  evidence.checks.push('language preserves unsaved area, chosen variant and project; copy; save; reload no duplicate');
  await page.goto(`${base}/calculators/plitka-keramogranit/`);
  await page.locator('label[for="tab-master"]').click();
  await page.locator('[data-row-qty]').first().fill('7.5');
  await switchLanguage(page,'ru');
  assert(await page.locator('#tab-master').isChecked(),'master tab preserved');
  assert.equal(await page.locator('[data-row-qty]').first().inputValue(),'7.5','master quantities preserved');
  evidence.checks.push('master worksheet quantities and active tab survive language change');
  await page.goto(`${base}/projects/upload/`);
  const uploadPosts=[];
  page.on('request', req=>{if(req.method()==='POST'&&req.url().includes('/projects/upload/')) uploadPosts.push(req.url());});
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==','base64');
  await page.locator('[type=file]').setInputFiles({name:'synthetic-plan.png',mimeType:'image/png',buffer:png});
  await page.locator('[name=comment]').fill('Synthetic draft Ә Ғ Қ Ң Ө Ұ Ү Һ І');
  await page.locator(languageForm).locator('button[value=kk]').click();
  await page.waitForFunction(()=>document.documentElement.lang==='kk');
  assert.equal(await page.locator('[type=file]').evaluate(el=>el.files[0]?.name),'synthetic-plan.png');
  assert.equal(await page.locator('[name=comment]').inputValue(),'Synthetic draft Ә Ғ Қ Ң Ө Ұ Ү Һ І');
  assert.equal(uploadPosts.length,0,'language switch did not upload');
  await page.locator('.project-upload-form button[type=submit]').click();
  await page.locator('[name=upload_id]').waitFor();
  assert.equal(uploadPosts.length,1,'explicit upload sent once');
  await switchLanguage(page,'ru');
  assert.equal(uploadPosts.length,1,'language switch after upload did not replay');
  evidence.checks.push('password and file nodes retained through language switch; explicit submit succeeds without replay');
  await context.close();
} finally {
  await fs.writeFile(`${output}/evidence.json`,JSON.stringify(evidence,null,2));
  await browser.close();
}
