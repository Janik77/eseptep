/** Synthetic 72m² fixture. Ordinary upload reuses saved recognition; no provider call. */
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_PACKAGE||'playwright');
const base=process.env.MEETING_BASE||'http://127.0.0.1:8233';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname),'QA must remain local');
const output=process.env.MEETING_EVIDENCE||'closed-pilot-evidence';await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{channel:'chrome'}),chromiumSandbox:true});
const checks=[];
const errors=[];
async function login(page,role){await page.goto(base+'/accounts/login/');await page.locator('[name=username]').fill(`demo-${role}@example.test`);await page.locator('[name=password]').fill('Demo-Meeting-2026!');await page.locator('form button[type=submit]').last().click();await page.waitForURL(/dashboard/);}
async function lang(page,value){await page.locator(`[data-language-form] button[value="${value}"]`).click();await page.waitForFunction(v=>document.documentElement.lang===v,value);}
async function shot(page,name){await page.evaluate(()=>document.fonts.ready);const size=await page.evaluate(()=>({w:innerWidth,s:document.documentElement.scrollWidth}));assert(size.s<=size.w+1,JSON.stringify(size));await page.screenshot({path:`${output}/${name}-first.png`});await page.screenshot({path:`${output}/${name}-full.png`,fullPage:true});}
async function revision(page){return page.locator('#whole-result').getAttribute('data-estimate');}
async function change(page,value){const old=await revision(page);await page.locator('#finish-0').selectOption(value);await page.waitForFunction(id=>document.querySelector('#whole-result')?.dataset.estimate!==id,old);await page.waitForFunction(()=>!document.querySelector('#whole-result')?.hasAttribute('aria-busy'));assert.equal(await page.locator('#finish-0').inputValue(),value);}
try{
 const auth=await browser.newContext();const authPage=await auth.newPage();await login(authPage,'client');const storageState=await auth.storageState();await auth.close();
 for(const width of [1440,390]){
  const context=await browser.newContext({storageState,viewport:{width,height:900},recordVideo:{dir:output,size:{width,height:900}}});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  for(const language of ['ru','kk']){
   await page.goto(base+'/projects/1/whole/');await lang(page,language);
   assert.equal(await page.locator('.whole-room').count(),5);
   assert.match(await page.locator('.whole-facts').innerText(),/5.*72\s*м²/);
   assert.match(await page.locator('.whole-price-caption').innerText(),language==='ru'?/Сумма по известным ценам/:/Бағасы белгілі/);
   if(width===390){const positions=await page.locator('.whole-actions a').evaluateAll(xs=>xs.map(x=>getComputedStyle(x).position));assert.equal(positions[0],'fixed');assert.equal(positions.filter(x=>x==='fixed').length,1);}

   assert.match((await page.locator('.whole-price').innerText()).replace(/\s/g,''),/61200₸/);
   assert.match(await page.locator('.whole-summary .whole-muted').innerText(),/7/);
   assert.equal(await page.locator('#purchase[open]').count(),0);
   assert.equal(await page.locator('.whole-room-details[open]').count(),0);
   assert.equal(await page.locator('[data-whole-submit]').count(),0,'No analyze action in recognized result');
   if(language==='kk')assert.match(await page.locator('#room-0 summary').innerText(),/Қонақ бөлме/);
   await shot(page,`result-${language}-${width}`);
   const select=page.locator('#finish-0');await select.focus();await page.waitForTimeout(300);
   const y=await page.evaluate(()=>scrollY);const original=await select.inputValue();
   const alternate=original==='tile'?'laminate':'tile';await change(page,alternate);
   assert(Math.abs(await page.evaluate(()=>scrollY)-y)<=3,'Autosave must preserve scroll');
   await page.waitForTimeout(700);await shot(page,`changed-${language}-${width}`);
   await change(page,original);
   // Deliberate local transport failure: server never receives this POST; old result must remain.
   const old=await revision(page);
   await page.route('**/projects/1/whole/',route=>route.request().method()==='POST'?route.abort('failed'):route.continue());
   await page.locator('#finish-0').selectOption(alternate);
   await page.locator('#whole-feedback[data-error]').waitFor();
   assert.equal(await revision(page),old);assert.equal(await page.locator('#finish-0').inputValue(),original);
   await page.unroute('**/projects/1/whole/');
   // Keyboard disclosure and aggregate list, native select remain keyboard-operable.
   await page.locator('#details-0 summary').focus();await page.keyboard.press('Enter');
   assert.equal(await page.locator('#details-0[open]').count(),1);
   await page.locator('#purchase summary').click();assert.equal(await page.locator('#purchase .whole-materials li').count(),11);
   checks.push({width,language,rooms:5,area:72,subtotal:61200,unpriced:7,autosave:true,failedPostPreservesResult:true,realApiCalls:0});
  }
  const video=page.video();await context.close();await video.saveAs(`${output}/coverage-switch-${width}.webm`);
 }

 // Ordinary upload from the existing synthetic plan; PLAN_AI_ENABLED=0 on fixture server.
 const client=await browser.newContext({storageState,viewport:{width:390,height:900}});const page=await client.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/projects/upload/');await lang(page,'ru');
 await page.locator('#own-plan input[name=file]').setInputFiles('tests/fixtures/plans/typical-two-room.pdf');
 await page.locator('#own-plan button[type=submit]').click();await page.waitForURL(/projects\/\d+\/whole\//);
 assert.equal(await page.locator('.whole-room').count(),5);
 assert.match(await page.locator('.whole-facts').innerText(),/5.*72\s*м²/);
 assert.equal(await page.locator('[data-whole-submit]').count(),0);
 const initial=await page.locator('#finish-0').inputValue();
 await change(page,initial==='tile'?'laminate':'tile');await shot(page,'ordinary-upload-changed-ru-390');
 await page.locator('[data-request-offer]').click();
 await page.locator('#whole-project').selectOption({index:0});await page.locator('form:has(#whole-project) button').click();
 const picks=page.locator('[data-choose-lines] [name=line]');assert((await picks.count())>2);
 for(let i=2;i<await picks.count();i++)await picks.nth(i).uncheck();
 await page.locator('[data-choose-lines] button[type=submit]').click();
 const confirm=page.locator('form:has([name=confirm])');await confirm.waitFor();
 const savedUrl=new URL(page.url());savedUrl.pathname=savedUrl.pathname.replace(/request\/$/,'');savedUrl.search='';
 assert.equal(await page.locator('.whole-materials li').count(),2);await shot(page,'request-review-ru-390');
 await confirm.locator('[name=confirm]').check();await confirm.locator('button').click();await page.waitForURL(/whole-requests\/\d+\//);const requestUrl=page.url();
 const supplier=await browser.newContext({viewport:{width:390,height:900}});const sp=await supplier.newPage();sp.on('pageerror',e=>errors.push(e.message));await login(sp,'supplier');
 const requestPath=new URL(requestUrl).pathname;
 await sp.locator('a[href="'+requestPath+'"]').first().click();
 await sp.locator('[name=price_0]').fill('100');await sp.locator('[name=availability_0]').selectOption('available');
 await sp.locator('[name=availability_1]').selectOption('unavailable');
 await sp.locator('form:has([name=price_0]) button[type=submit]').click();await sp.locator('[name=price_0]').waitFor({state:'detached'});await supplier.close();
 await page.goto(base+'/accounts/dashboard/client/');
 await page.locator('a[href="'+savedUrl.pathname+'"]').first().click();
 await page.locator('[data-latest-answer]').waitFor();
 for(const width of [390,1440]){
  await page.setViewportSize({width,height:900});
  for(const language of ['ru','kk']){
   await page.goto(savedUrl.href);await lang(page,language);
   await shot(page,'saved-answer-'+language+'-'+width);
   await page.locator('[data-latest-answer] a').click();
   const detail=await page.locator('.dashboard').innerText();
   assert.match(detail,language==='ru'?/Ответ магазина/:/Дүкеннің жауабы/);
   assert.match(detail,language==='ru'?/В наличии/:/Бар/);assert.match(detail,language==='ru'?/Нет в наличии/:/Жоқ/);
   assert.match(detail,/100\s*₸/);await shot(page,'supplier-response-'+language+'-'+width);
  }
 }
 await client.close();checks.push({supplierFlow:'ordinary upload → cached analysis → changed flooring → selected purchase lines → confirmed demo request → seller price+stock → reopened buyer project',externalMessages:0,realApiCalls:0});
 assert.deepEqual(errors,[]);await fs.writeFile(`${output}/checks.json`,JSON.stringify({passed:true,checks,pageErrors:errors},null,2));
}finally{await browser.close();}
