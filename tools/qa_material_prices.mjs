import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_PACKAGE||'playwright');
const browser=await chromium.launch({channel:'chrome',chromiumSandbox:true});
const base='http://127.0.0.1:8197';
const context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:'browser-evidence/material-pricing-video'}});
const page=await context.newPage();
const checks=[];
async function publish(version){
 await page.goto(base+'/admin/calculators/pricebook/');
 const row=page.locator('#result_list tbody tr').filter({hasText:version});
 await row.locator('input.action-select').check();
 await page.locator('select[name=action]').first().selectOption('activate');
 await page.locator('button[name=index]').first().click();
 await page.locator('.messagelist .success').waitFor();
}
async function calculate(){
 await page.goto(base+'/calculators/plitka-keramogranit/');
 await page.locator('[data-calc-form] [name=area]').fill('36.5');
 await page.locator('[data-calc-form] button[type=submit]').click();
 await page.locator('[data-result-ready]').waitFor();
}
try{
 await page.goto(base+'/admin/login/');
 await page.locator('[name=username]').fill('price-admin@example.test');
 await page.locator('[name=password]').fill('Synthetic-Price-Admin-815!');
 await page.locator('input[type=submit]').click();
 await page.waitForURL(base+'/admin/');
 await page.goto(base+'/admin/calculators/pricebook/');
 await page.locator('#result_list tbody tr').filter({hasText:'qa-full'}).locator('th a').click();
 const editedVariant=await page.locator('[name="entries-0-variant_key"]').inputValue();
 await page.locator('[name="entries-0-price"]').fill('15.25');
 await page.locator('input[name=_save]').click();
 await page.locator('.messagelist .success').waitFor();
 await publish('qa-full');
 await calculate();
 await page.locator(`[data-variant-button=${editedVariant}]`).click();
 assert((await page.locator('.variant-panel.is-active .admin-quote').innerText()).includes('15,25'), 'edited draft unit price reaches the actual selected quote');
 const quote=page.locator('.variant-panel.is-active .admin-quote');
 await quote.getByText('SYNTHETIC QA STORE',{exact:false}).waitFor();
 assert.equal(await quote.locator('.offer-empty').count(),0,'full coverage has no missing rows');
 for(const lang of ['ru','kk']){
  await Promise.all([page.waitForNavigation(),page.locator('[data-language-switch], [data-language-form]').locator(`button[value=${lang}]`).first().click()]);
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:1000});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:`browser-evidence/material-price-${lang}-${width}.png`,fullPage:true});
  }
 }
 await page.locator('[data-variant-button=business]').click();
 assert((await page.locator('.variant-panel.is-active .admin-quote').innerText()).includes('qa-full'));
 checks.push('admin edits draft price, publishes full scoped edition; RU/KK variants and mobile/desktop show store quotation');
 await publish('qa-partial');await calculate();
 assert(await page.locator('.variant-panel.is-active .admin-quote .offer-empty').count()>0,'partial edition reports missing prices');
 await page.screenshot({path:'browser-evidence/material-price-partial.png',fullPage:true});
 checks.push('partial edition never presented as complete total');
 await page.goto(base+'/admin/calculators/pricebook/');
 await page.locator('#result_list tbody tr').filter({hasText:'qa-full'}).locator('th a').click();
 assert.equal(await page.locator('[name="entries-0-price"]').count(),0,'published prices read-only');
 checks.push('published edition immutable in admin');
} finally {
 await fs.writeFile('browser-evidence/material-pricing-checks.json',JSON.stringify({checks},null,2));
 await context.close();await browser.close();
}
