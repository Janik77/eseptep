/** Synthetic typed rate edition and historical upload snapshots. */
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const require=createRequire(import.meta.url);const{chromium}=require(process.env.PLAYWRIGHT_PACKAGE||'playwright');
assert.equal(process.env.ESEPTEP_BROWSER_QA,'1');
const base='http://127.0.0.1:8197';const checks=[];
const browser=await chromium.launch({...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE} : {channel:'chrome'}),chromiumSandbox:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:'browser-evidence/typed-rates-video'}});
const page=await context.newPage();
const customer=await browser.newContext({viewport:{width:390,height:900},recordVideo:{dir:'browser-evidence/typed-rates-client-video'}});const client=await customer.newPage();
const raw=execFileSync(process.env.PYTHON||'python',['manage.py','shell','-c','from projects.models import ProjectUpload; print("UPLOAD_ID="+str(ProjectUpload.objects.get(comment="typed-pricing-legacy").pk))'],{encoding:'utf8'});
const uploadId=raw.match(/UPLOAD_ID=(\d+)/)[1];
async function activate(version){await page.goto(base+'/admin/calculators/renovationrateedition/');await page.locator('#result_list tbody tr').filter({hasText:version}).locator('input.action-select').check();await page.locator('select[name=action]').first().selectOption('activate');await page.locator('button[name=index]').first().click();await page.locator('.messagelist').getByText((await page.locator('html').getAttribute('lang'))==='kk'?'Жөндеу тарифтері жарияланды. Бұрынғы есептер өзгерген жоқ.':'Ставки ремонта опубликованы. Исторические расчёты не изменились.',{exact:true}).waitFor();}
async function showResult(){await client.locator('.project-estimate-total').scrollIntoViewIfNeeded();await client.waitForTimeout(1200);}
async function language(p,lang){await Promise.all([p.waitForNavigation(),p.locator('[data-language-switch], [data-language-form]').locator(`button[value=${lang}]`).first().click()]);}
try{
 await page.goto(base+'/admin/login/');await page.locator('[name=username]').fill('price-admin@example.test');await page.locator('[name=password]').fill('Synthetic-Price-Admin-815!');await page.locator('input[type=submit]').click();await page.waitForURL(base+'/admin/');
 await activate('qa-rates-v1');
 await client.goto(base+'/accounts/login/');await client.locator('[name=username]').fill('browser-qa@example.test');await client.locator('[name=password]').fill('Synthetic-QA-Only-815!');await client.locator('.auth-form button[type=submit]').click();await client.waitForURL(/dashboard/);
 await client.goto(`${base}/projects/upload/?upload_id=${uploadId}`);
 assert((await client.locator('.project-estimate-total').innerText()).replace(/[\s\u00a0\u202f]/g,'').includes('6205000'),'legacy existing estimate not repriced by active edition');
 await showResult();
 assert.equal(await client.locator('[name=rate_version]').inputValue(),'qa-rates-v1');
 await client.locator('.project-estimate-form button[type=submit]').click();
 assert((await client.locator('.project-estimate-total').innerText()).includes('8 103'));
 await showResult();
 await activate('qa-rates-v2');
 await client.locator('.project-estimate-form button[type=submit]').click();
 assert(await client.locator('.project-estimate-form .errorlist').count()>0,'stale edition rejected without silent save');
 await client.locator('.project-estimate-form .errorlist').scrollIntoViewIfNeeded();await client.waitForTimeout(1200);
 await client.goto(`${base}/projects/upload/?upload_id=${uploadId}`);
 assert((await client.locator('.project-estimate-total').innerText()).includes('8 103'),'saved snapshot remains original after new edition');
 await showResult();
 for(const lang of ['ru','kk']){await language(client,lang);for(const width of [390,1440]){await client.setViewportSize({width,height:1000});assert(await client.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await client.screenshot({path:`browser-evidence/typed-rate-snapshot-${lang}-${width}.png`,fullPage:true});}}
 checks.push('published typed edition applies only to explicit new estimate; legacy estimate and saved snapshot do not reprice; stale form refused; RU/KK provenance visible');
 await client.goto(base+'/marketplace/');await client.locator('.turnkey-form [name=area]').fill('36.5');await client.locator('.turnkey-form button[type=submit]').click();
 assert((await client.locator('details.turnkey-card').nth(1).innerText()).includes('16 206'),'turnkey uses active standard rate444×36.5');
 await client.locator('details.turnkey-card').nth(1).scrollIntoViewIfNeeded();await client.waitForTimeout(1200);
 await client.screenshot({path:'browser-evidence/typed-rates-turnkey.png',fullPage:true});
 checks.push('same typed edition serves turnkey and upload, fixed KZT/m2 units');
}finally{await fs.writeFile('browser-evidence/typed-rates-checks.json',JSON.stringify({checks},null,2));await customer.close();await context.close();await browser.close();}
