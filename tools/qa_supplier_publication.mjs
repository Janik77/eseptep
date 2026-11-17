/** Isolated synthetic supplier publication, never a stock verification. */
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_PACKAGE||'playwright');
assert.equal(process.env.ESEPTEP_BROWSER_QA,'1');
const browser=await chromium.launch({channel:'chrome',chromiumSandbox:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();const base='http://127.0.0.1:8197';const checks=[];
async function calculate(){await page.goto(base+'/calculators/plitka-keramogranit/');await page.locator('[data-calc-form] [name=area]').fill('36.5');await page.locator('[data-calc-form] button[type=submit]').click();await page.locator('[data-result-ready]').waitFor();}
async function save(){await page.locator('.auth-form button[type=submit]').click();await page.waitForURL(/dashboard\/supplier/);}
try{
 await page.goto(base+'/accounts/login/');await page.locator('[name=username]').fill('supplier@example.test');await page.locator('[name=password]').fill('Synthetic-QA-Only-815!');await page.locator('.auth-form button[type=submit]').click();await page.waitForURL(/dashboard\/supplier/);
 await page.goto(base+'/accounts/dashboard/supplier/materials/create/');
 for(const [name,value] of Object.entries({name:'Плитка комфорт',category:'SYNTHETIC QA',unit:'м²',price:'17.25',stock_status:'SYNTHETIC supplier statement, unverified',delivery_time:'SYNTHETIC no delivery promise'})) await page.locator(`[name=${name}]`).fill(value);
 assert(!(await page.locator('[name=is_published]').isChecked()),'private by default');
 await save();
 const edit=await page.locator('a[href*="/materials/"][href*="/edit/"]').last().getAttribute('href');assert(edit);
 await calculate();let offers=page.locator('.variant-panel.is-active details.material-offers');assert.equal(await offers.locator('.offer-candidate').count(),0,'private product not public');
 await page.goto(base+edit);await page.locator('[name=is_published]').check();await save();await calculate();
 offers=page.locator('.variant-panel.is-active details.material-offers');await offers.locator('summary').click();
 assert.equal(await offers.locator('.offer-candidate').count(),1);assert((await offers.innerText()).includes('17,25'));assert((await offers.innerText()).includes('unverified'));
 for(const lang of ['ru','kk']){
  await Promise.all([page.waitForNavigation(),page.locator('[data-language-switch], [data-language-form]').locator(`button[value=${lang}]`).first().click()]);
  offers=page.locator('.variant-panel.is-active details.material-offers');if(!(await offers.evaluate(e=>e.open)))await offers.locator('summary').click();
  for(const width of [390,1440]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:`browser-evidence/supplier-published-${lang}-${width}.png`,fullPage:true});}
 }
 await page.goto(base+edit);await page.locator('[name=is_published]').uncheck();await save();await calculate();
 assert.equal(await page.locator('.variant-panel.is-active details.material-offers .offer-candidate').count(),0,'unpublished product disappears');
 checks.push('supplier creates private product; exact-name/unit candidate appears only after explicit publication; RU/KK 390/1440; unpublish removes candidate; price and unverified stock label preserved');
}finally{await fs.writeFile('browser-evidence/supplier-publication-checks.json',JSON.stringify({checks},null,2));await context.close();await browser.close();}
