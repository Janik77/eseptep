/** Real Chromium localhost walkthrough. Only synthetic plans, no API and no outbound messages. */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';

const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_PACKAGE||'playwright');
const base=process.env.MEETING_BASE||'http://127.0.0.1:8233';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const out='closed-pilot-evidence/apartment-pilot';
await fs.mkdir(out,{recursive:true});
const evidence=[], errors=[];
const browser=await chromium.launch({channel:'chrome',chromiumSandbox:true});
const viewport={width:390,height:844};
async function fillLogin(page,role) {
  const form=page.locator('form.auth-form');
  await form.locator('[name=username]').fill(`demo-${role}@example.test`);
  await form.locator('[name=password]').fill('Demo-Meeting-2026!');
  await form.locator('button[type=submit]').click();
}
async function lang(page,value) {
  await page.locator(`[data-language-form] button[value="${value}"]`).click();
  await page.waitForFunction(id=>document.documentElement.lang===id,value);
}
async function picture(page,name) {
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'narrow view does not overflow');
  await page.screenshot({path:`${out}/${name}.png`});
}
async function chooseTypical(page) {
  await page.goto(base+'/projects/upload/');
  await page.locator('#typical-plans summary').click();
  await page.locator('#typical-plans form:has([value=two-room]) button').click();
  await page.waitForURL(/\/projects\/\d+\/whole\//);
}
async function postFormData(form) {return form.evaluate(f=>Object.fromEntries(new FormData(f)));}
async function change(page,next) {
  const old=await page.locator('#whole-result').getAttribute('data-estimate');
  await page.locator('#finish-0').selectOption(next);
  await page.waitForFunction(id=>document.querySelector('#whole-result').dataset.estimate!==id,old);
  assert.equal(await page.locator('#finish-0').inputValue(),next);
}
function observe(page){page.on('pageerror',err=>errors.push(err.message));}
try {
  for(const language of ['ru','kk']){
    const customer=await browser.newContext({viewport,isMobile:true,hasTouch:true,recordVideo:{dir:out,size:viewport}});
    const page=await customer.newPage();observe(page);
    await page.goto(base+'/');await lang(page,language);
    assert.equal(await page.locator('.direction-card').count(),3);await picture(page,`home-${language}`);
    await chooseTypical(page);
    const whole=page.url();
    assert.equal(await page.locator('.whole-room').count(),5);
    assert.match(await page.locator('.whole-facts').innerText(),/5.*72\s*м²/);
    await page.locator('#purchase summary').click();
    const purchase=await page.locator('#purchase').innerText();
    assert.match(purchase,language==='ru'?/32\s*упак\./:/32\s*қапт\./);
    assert.match(purchase,/316\s800/);assert.match(purchase,/70,4\s*м²/);
    await picture(page,`floor-packs-${language}`);
    await page.locator('#details-0 summary').click();
    await page.locator('#details-0 [name=name]').focus();
    assert.equal(await page.locator('[data-request-offer]').isVisible(),false);
    await page.locator('#details-0 summary').click();
    assert.equal(await page.locator('[data-request-offer]').isVisible(),true);
    await change(page,'tile');await page.reload();
    assert.equal(await page.locator('#finish-0').inputValue(),'tile');
    assert.equal(await page.locator('#finish-1').inputValue(),'laminate');
    // Restore original cover but preserve the fact that it is a user's decision.
    await change(page,'laminate');
    await page.locator('[data-request-offer]').click();
    await page.waitForURL(/accounts\/login/);
    await fillLogin(page,'client');
    await page.waitForURL(/\/accounts\/whole\/\d+\/request/);
    await page.locator('[data-choose-lines] button[type=submit]').click();
    const confirm=page.locator('form:has([name=confirm])');
    await confirm.waitFor();await picture(page,`store-review-${language}`);
    await confirm.locator('[name=confirm]').check();
    const data=await postFormData(confirm);const preview=page.url();
    await confirm.locator('button').click();await page.waitForURL(/whole-requests\/\d+\//);
    const offer=page.url(); const replay=await customer.request.post(preview,{form:data});
    assert.equal(replay.url(),offer);
    await page.goBack();await page.goto(whole);
    assert.equal(await page.locator('#finish-0').inputValue(),'laminate');
    await change(page,'tile');
    // The immutable request still uses the original pack cost.
    await page.goto(offer);await page.locator('details summary').first().click();
    assert.match(await page.locator('.dashboard').innerText(),/316\s800/);
    const store=await browser.newContext({viewport,isMobile:true,hasTouch:true});
    const worker=await store.newPage();observe(worker);
    await worker.goto(base+'/accounts/login/');await fillLogin(worker,'supplier');
    await worker.goto(offer);
    const tile=worker.locator('form fieldset').filter({hasText:/Плитка комфорт/}).first();
    const packs=worker.locator('form fieldset').filter({hasText:/Ламинат/}).first();
    await packs.locator('input[name^=price_]').fill('9900');
    await packs.locator('select[name^=availability_]').selectOption('available');
    await tile.locator('select[name^=availability_]').selectOption('unavailable');
    await worker.locator('form:has(fieldset) button[type=submit]').click();
    await worker.locator('form fieldset').first().waitFor({state:'detached'});
    await store.close();
    await page.reload();
    assert.match(await page.locator('.dashboard').innerText(),language==='ru'?/Ответ магазина/:/Дүкеннің жауабы/);
    assert.match(await page.locator('.dashboard').innerText(),/316\s800/);
    await picture(page,`store-answer-${language}`);

    await page.goto(base+'/marketplace/');await page.locator('.turnkey-form [name=area]').fill(language==='ru'?'36,5':'38,5');
    await page.locator('.turnkey-form button[type=submit]').click();
    await page.locator('[data-turnkey-quote="standard"]').click();
    assert.match(await page.locator('.dashboard').innerText(),/ДЕМО-мастер ESEPTEP/);
    await picture(page,`master-preview-${language}`);
    const submit=page.locator('form:has([name=confirm])');await submit.locator('[name=confirm]').check();await submit.locator('button').click();
    await page.waitForURL(/accounts\/turnkey\/\d+\//);
    const receipt=page.url();
    const master=await browser.newContext({viewport,isMobile:true,hasTouch:true});
    const contractor=await master.newPage();observe(contractor);
    await contractor.goto(base+'/accounts/login/');await fillLogin(contractor,'master');
    await contractor.locator(`[data-turnkey-reply][href="${new URL(receipt).pathname}reply/"]`).click();
    const form=contractor.locator('form.auth-form');
    await form.locator('[name=price_from]').fill('6200000,50');await form.locator('[name=message]').fill('DEMO: подготовка и отделка после осмотра');
    await form.locator('button[type=submit]').click();await contractor.locator('form.auth-form').waitFor({state:'detached'});
    await master.close();await page.reload();
    assert.match(await page.locator('.dashboard').innerText(),language==='ru'?/Ответ мастера/:/Шебердің жауабы/);
    assert.match(await page.locator('.dashboard').innerText(),/6\s200\s000,5/);
    await picture(page,`master-answer-${language}`);
    const video=page.video();await customer.close();await video.saveAs(`${out}/customer-${language}-390.webm`);
    evidence.push({language,width:390,guestSampleAndClaim:true,pack:'65.4 m² to 32 packs; original request unchanged',supplier:true,master:true,apiCalls:0,externalMessages:0});
  }
  const ctx=await browser.newContext({viewport,isMobile:true,hasTouch:true});
  const page=await ctx.newPage();observe(page);
  await page.goto(base+'/projects/upload/');
  const file=page.locator('#own-plan input[type=file]');
  await file.setInputFiles({name:'damaged.png',mimeType:'image/png',buffer:Buffer.from('not a PNG')});
  await page.locator('#own-plan button[type=submit]').click();
  await page.locator('#own-plan .errorlist').waitFor();
  await file.setInputFiles('tests/fixtures/plans/typical-two-room.pdf');
  await page.locator('#own-plan button[type=submit]').click();
  await page.waitForURL(/\/projects\/\d+\/whole\//);
  const manual=page.locator('#manual-room form');
  await manual.locator('[name=name]').fill('Жатын бөлмесі және киім сақтайтын аймақ');
  await manual.locator('[name=area]').fill('15,25');
  await manual.locator('[name=finish]').selectOption('spc');
  await manual.locator('button').click();
  await page.locator('#finish-0').waitFor();await page.reload();
  assert.equal(await page.locator('#finish-0').inputValue(),'spc');
  assert.match(await page.locator('.whole-facts').innerText(),/15,25/);
  await picture(page,'offline-manual-390');await ctx.close();
  assert.deepEqual(errors,[]);
  await fs.writeFile(`${out}/checks.json`,JSON.stringify({evidence,manualAfterUnavailable:true,badImage:true,pageErrors:errors},null,2));
} finally {await browser.close();}
