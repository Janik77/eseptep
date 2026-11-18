/** Real Django browser flow; AI unavailable/manual fallback. NOT a live AI demonstration. */
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_PACKAGE||'playwright');
const base='http://127.0.0.1:8207', output=process.env.PLAN_EVIDENCE||'/tmp/eseptep-plan-evidence';
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{channel:'chrome'}),chromiumSandbox:true});
const checks=[];
try {
for(const width of [1440,390]){
const context=await browser.newContext({viewport:{width,height:900},recordVideo:{dir:output,size:{width,height:900}}});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base+'/accounts/login/');await page.locator('[name=username]').fill('browser-qa@example.test');await page.locator('[name=password]').fill('Synthetic-QA-Only-815!');await page.locator('form button[type=submit]').last().click();
for(const lang of ['ru','kk']){
await page.goto(base+'/projects/upload/');
await page.locator('[data-language-switch], [data-language-form]').locator(`button[value="${lang}"]`).first().click();
await page.waitForFunction(lang=>document.documentElement.lang===lang,lang);
await page.locator('[name=file]').setInputFiles('tests/fixtures/plans/apartment-unreadable-area.pdf');
await page.waitForTimeout(800); // Deliberate reviewable recording pace, not a readiness assertion.
await page.locator('form [name=action][value=upload]').locator('..').locator('button[type=submit]').click();
await page.locator('a[href$="/plan/"]').click();
await page.locator('.plan-image').waitFor();
await page.locator('form [name=action][value=analyze]').locator('..').locator('button').click();
assert(await page.locator('[role=alert]').isVisible());
await page.waitForTimeout(1200);
const form=page.locator('details form');await form.locator('[name=area]').fill('5,25');
await page.screenshot({path:`${output}/manual-${lang}-${width}.png`,fullPage:true});
await page.waitForTimeout(1000);
await form.locator('button').click();
assert.equal(await page.locator('[data-calc-form] [name=area]').inputValue(),'5.25');
await page.waitForTimeout(800);
await page.locator('[data-calc-form] button[type=submit]').click();
await page.waitForTimeout(1000);
await page.locator('[data-variant-button]').last().click();
assert(await page.locator('[data-copy-variant]').isVisible());
await page.screenshot({path:`${output}/tile-${lang}-${width}.png`,fullPage:true});
await page.locator('button[name=action][value=save_estimate]').scrollIntoViewIfNeeded();
await page.waitForTimeout(1200);
assert(await page.locator('body').innerText().then(x=>x.includes('SYNTHETIC QA STORE')));
await page.locator('select[name=project_id]').selectOption({index:1});
await page.locator('button[name=action][value=save_estimate]').click();
await page.waitForURL(/calculations/);
assert(await page.locator('body').innerText().then(x=>x.includes('5.25')));
const dimensions=await page.evaluate(()=>({w:innerWidth,s:document.documentElement.scrollWidth}));assert(dimensions.s<=dimensions.w+1,JSON.stringify(dimensions));
await page.screenshot({path:`${output}/saved-${lang}-${width}.png`,fullPage:true});
await page.waitForTimeout(1200);
checks.push({width,lang,path:'unreadable plan → unavailable AI notice → manual 5.25 → floor tiles → variant → partial synthetic store quote → saved source',liveApiCalls:0});
}
assert.deepEqual(errors,[]);await context.close();
}
}finally{await browser.close();await fs.writeFile(output+'/checks.json',JSON.stringify(checks,null,2));}
