/** End-to-end synthetic meeting. Real Django, manual plan confirmation; no live AI. */
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_PACKAGE||'playwright');
const base=process.env.MEETING_BASE||'http://127.0.0.1:8220';
const output=process.env.MEETING_EVIDENCE||'meeting-evidence';await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{channel:'chrome'}),chromiumSandbox:true});
const checks=[];let priceChanged=false;let unreadableSeen=false;
async function shot(page,name){await page.evaluate(()=>document.fonts.ready);const size=await page.evaluate(()=>({w:innerWidth,s:document.documentElement.scrollWidth}));assert(size.s<=size.w+1,JSON.stringify(size));await page.screenshot({path:`${output}/${name}.png`,fullPage:true});}
async function lang(page,value){await page.locator('[data-language-form] button[value="'+value+'"]').click();await page.waitForFunction(v=>document.documentElement.lang===v,value);}
async function login(page,role){await page.goto(base+'/accounts/login/');await page.locator('[name=username]').fill(`demo-${role}@example.test`);await page.locator('[name=password]').fill('Demo-Meeting-2026!');await page.locator('form button[type=submit]').last().click();await page.waitForURL(/dashboard/);}
async function logout(page){await page.locator('form[action$="/accounts/logout/"] button').click();}
const pause=page=>page.waitForTimeout(900); // Deliberate viewing pace for acceptance video.
try{
for(const width of [1440,390]){
 const context=await browser.newContext({viewport:{width,height:900},recordVideo:{dir:output,size:{width,height:900}},acceptDownloads:true});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await login(page,'client');
 for(const language of ['ru','kk']){
  await page.goto(base+'/projects/upload/');await lang(page,language);
  await shot(page,`upload-${language}-${width}`);
  await page.locator('#typical-plans summary').click();
  assert.equal(await page.locator('.typical-card').count(),3);
  await shot(page,`typical-catalog-${language}-${width}`);
  await page.locator('form:has(input[name=sample][value=studio]) button').click();
  // Catalog examples now lead to a clearly tagged ready estimate.
  await page.locator('#whole-result [data-offline-example]').waitFor();
  assert.match(await page.locator('.whole-facts').innerText(),/36\s*м²/);
  await shot(page,`typical-result-${language}-${width}`);
  // Separately exercise the still supported single-room/manual compatibility path.
  await page.goto(base+'/projects/upload/');
  const clearCsrf=await page.locator('#own-plan [name=csrfmiddlewaretoken]').inputValue();
  const clear=await context.request.post(base+'/projects/examples/select/',{
    form:{sample:'clear',csrfmiddlewaretoken:clearCsrf}});
  await page.goto(clear.url());
  await page.locator('.plan-image').waitFor();await pause(page);
  // Pause native submission for a UI-only pending-state check; never mock an AI response.
  await page.locator('[data-plan-analysis-form]').evaluate(form=>form.addEventListener('submit',event=>event.preventDefault(),{once:true}));
  await page.locator('[data-plan-analysis-form] button').click();
  await page.locator('.plan-progress:not([hidden])').waitFor();
  await shot(page,`waiting-${language}-${width}`);await pause(page);
  await page.locator('[data-plan-analysis-form]').evaluate(form=>HTMLFormElement.prototype.submit.call(form));
  await page.locator('[role=alert]').waitFor();
  const form=page.locator('details form');await form.locator('[name=area]').fill('4,8');await pause(page);
  await shot(page,`plan-${language}-${width}`);await form.locator('button').click();
  assert.equal(Number(await page.locator('[data-calc-form] [name=area]').inputValue()),4.8);
  await page.locator('[data-calc-form] button[type=submit]').click();
  await page.locator('[data-variant-button="comfort"]').click();
  await page.locator('select[name=project_id]').selectOption({index:1});
  const project=await page.locator('select[name=project_id]').inputValue();
  await page.locator('[data-calc-form] [name=area]').fill('5.8');
  assert(await page.locator('button[value=save_estimate]').isDisabled());
  await page.locator('[data-calc-form] [name=area]').fill('4.8');
  assert(!(await page.locator('button[value=save_estimate]').isDisabled()));
  await page.locator('[data-calc-form] button[type=submit]').click();
  assert.equal(await page.locator('select[name=project_id]').inputValue(),project);
  await page.locator('[data-variant-button="comfort"]').click();
  await lang(page,language==='ru'?'kk':'ru');
  assert.equal(await page.locator('select[name=project_id]').inputValue(),project);
  assert.equal(await page.locator('[data-selected-variant-input]').inputValue(),'comfort');
  assert.equal(Number(await page.locator('[data-calc-form] [name=area]').inputValue()),4.8);
  await lang(page,language);
  await shot(page,`estimate-${language}-${width}`);
  assert(await page.locator('.admin-quote').first().innerText().then(x=>/4.*5|5.*4/s.test(x)));
  await page.locator('button[value=save_estimate]').click();await page.waitForURL(/accounts\/calculations/);await pause(page);
  const saved=page.url();const oldQuote=await page.locator('.admin-quote').innerText();
  const downloadPromise=page.waitForEvent('download');await page.locator('a[href$="/pdf/"]').click();const download=await downloadPromise;await download.saveAs(`${output}/estimate-${language}-${width}.pdf`);
  await page.locator('a[href$="/request-offer/"]').click();await shot(page,`request-preview-${language}-${width}`);await pause(page);
  const preview=page.url();const payload=await page.locator('form:has(input[name=request_token])').evaluate(form=>Object.fromEntries(new FormData(form)));
  await page.locator('form:has(input[name=request_token]) button').click();await page.waitForURL(/accounts\/requests/);
  const requested=page.url();await context.request.post(preview,{form:payload});await page.reload();assert.equal(page.url(),requested);await pause(page);
  await shot(page,`client-request-${language}-${width}`);
  await logout(page);await login(page,'supplier');await lang(page,language);
  assert(await page.locator(`a[href="${new URL(requested).pathname}"]`).count()>0);
  await page.goto(requested);await shot(page,`supplier-${language}-${width}`);await pause(page);
  await page.locator('form:has(input[name=action][value=mark_viewed]) button').click();await pause(page);
  await logout(page);await login(page,'client');await page.goto(requested);await lang(page,language);
  await page.locator('[data-request-status]').filter({hasText:language==='ru'?'Просмотрена':'Қаралған'}).waitFor();await shot(page,`client-status-${language}-${width}`);
  if(!priceChanged){execFileSync(process.env.PYTHON||'python',['manage.py','seed_meeting_demo','--confirm-isolated','--price-version','v2']);priceChanged=true;await page.goto(saved);assert.equal(await page.locator('.admin-quote').innerText(),oldQuote);}
  // Precision regression independent of the 4.8m² bathroom fixture.
  await page.goto(base+'/calculators/plitka-keramogranit/?_preview=0&area=36.5&zone=floor&tile_format=60x60');
  await page.locator('[data-calc-form] button[type=submit]').click();await page.locator('[data-variant-button="comfort"]').click();await page.locator('select[name=project_id]').selectOption({index:1});
  const params=await page.locator('.result-params').innerText();assert(!params.includes('36 м²'));assert.equal((params.match(/Зона|Аймақ/g)||[]).length,1);
  await shot(page,`precision-36_5-${language}-${width}`);await page.locator('button[value=save_estimate]').click();await page.waitForURL(/accounts\/calculations/);
  const pdfPromise=page.waitForEvent('download');await page.locator('a[href$="/pdf/"]').click();await (await pdfPromise).saveAs(`${output}/precision-36_5-${language}-${width}.pdf`);
  // Missing area and actual file upload stay manual, not fabricated recognition.
  await page.goto(base+'/projects/upload/');const token=await page.locator('#own-plan [name=csrfmiddlewaretoken]').inputValue();const unreadable=await context.request.post(base+'/projects/examples/select/',{form:{sample:'unreadable',csrfmiddlewaretoken:token}});await page.goto(unreadable.url());const previousManual=await page.locator('details [name=area]').inputValue();if(!unreadableSeen)assert.equal(previousManual,'');else assert.equal(Number(previousManual),5.25);unreadableSeen=true;
  await page.locator('details [name=area]').fill('5.25');await page.locator('details button').click();assert.equal(Number(await page.locator('[data-calc-form] [name=area]').inputValue()),5.25);
  await page.goto(base+'/projects/upload/');await page.locator('[name=file]').setInputFiles('tests/fixtures/plans/apartment-explication.png');await page.locator('form:has(input[name=action][value=upload_calculate]) button').click();await page.waitForURL(/\/projects\/\d+\/whole\//);await page.locator('[data-manual-plan]').click();await page.locator('.plan-image').waitFor();
  await page.goto(base+'/marketplace/');await page.locator('[name=area]').fill('36.5');await page.locator('[data-preview-form] button').click();await shot(page,`turnkey-${language}-${width}`);assert(await page.locator('.turnkey-card').count()===3);
  checks.push({width,language,flow:'clear synthetic plan → unavailable API → human-confirmed4.8 → tile comfort →4/5demo price→saved PDF→confirmed targeted request→supplier viewed→client status',realApiCalls:0,precision36_5:true,unreadableManual5_25:true,priceSnapshotPreserved:true});
 }
 assert.deepEqual(errors,[]);await context.close();
}
}finally{await browser.close();await fs.writeFile(`${output}/checks.json`,JSON.stringify(checks,null,2));}
