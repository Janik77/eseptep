/** Saved synthetic 72m² fixture only. No upload/analyze/provider calls. */
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
 // One ordinary targeted request in isolated synthetic DB, never a real merchant message.
 const client=await browser.newContext({storageState,viewport:{width:1440,height:900}});const page=await client.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/projects/1/whole/');await lang(page,'ru');await page.locator('[data-request-offer]').click();
 await page.locator('#whole-project').selectOption({index:0});await page.locator('form:has(#whole-project) button').click();
 await page.locator('[name=confirm]').waitFor();await shot(page,'request-preview-1440');
 await page.locator('[name=confirm]').check();await page.locator('form:has([name=confirm]) button').click();await page.waitForURL(/whole-requests\/\d+\//);const requestUrl=page.url();
 const supplier=await browser.newContext();const sp=await supplier.newPage();await login(sp,'supplier');await sp.goto(requestUrl);
 await sp.locator('[name=price_0]').fill('100');await sp.locator('[name=availability_0]').selectOption('available');await sp.locator('form:has([name=price_0]) button[type=submit]').click();
 await sp.locator('[name=price_0]').waitFor({state:'detached'});await supplier.close();
 await page.reload();assert.match(await page.locator('h2').allTextContents().then(x=>x.join(' ')),/Ответ магазина/);
 for(const width of [1440,390]){await page.setViewportSize({width,height:900});await shot(page,`supplier-response-${width}`);}
 await client.close();checks.push({supplierFlow:'explicit recipient/content preview → confirmed synthetic request → partial supplier answer → client receipt',externalMessages:0});
 assert.deepEqual(errors,[]);await fs.writeFile(`${output}/checks.json`,JSON.stringify({passed:true,checks,pageErrors:errors},null,2));
}finally{await browser.close();}
