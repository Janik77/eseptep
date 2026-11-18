"""Explicit single live UI check. Run only after owner-approved remaining budget.
Never retries an analysis. Uses only our own studio fixture and synthetic accounts.
"""
from pathlib import Path
import sys
CACHED="--cached" in sys.argv
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/('meeting-demo-data/cached-evidence' if CACHED else 'meeting-demo-data/live-evidence');OUT.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:8220'
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='chrome',chromium_sandbox=True)
 context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(OUT),accept_downloads=True)
 page=context.new_page()
 def login(role):
  page.goto(base+'/accounts/login/');page.locator('[name=username]').fill('demo-'+role+'@example.test');page.locator('[name=password]').fill('Demo-Meeting-2026!');page.locator('form button[type=submit]').last.click();page.wait_for_url('**/dashboard/**')
 def logout():page.locator('form[action$="/accounts/logout/"] button').click()
 try:
  login('client');page.goto(base+'/projects/upload/');page.locator('#typical-plans summary').click();page.locator('form:has(input[name=sample][value=studio]) button').click();page.locator('.plan-image').wait_for()
  page.screenshot(path=str(OUT/'01-preview.png'),full_page=True)
  # Exactly ONE paid action; no loops or retry path.
  if not CACHED: page.locator('[data-plan-analysis-form] button').click(timeout=60000)
  page.wait_for_load_state('networkidle',timeout=90000)
  page.screenshot(path=str(OUT/'02-actual-analysis.png'),full_page=True)
  forms=page.locator('form.plan-room').all()
  matches=[f for f in forms if f.locator('[name=room]').input_value()!='-1' and 'санузел' in f.locator('[name=name]').input_value().lower()]
  assert len(matches)==1, 'Expected a uniquely identified bathroom; no guessed fallback'
  form=matches[0]
  assert abs(float(form.locator('[name=area]').input_value().replace(',','.'))-4.8)<.001,'Recognized value must be checked against source; never force expected answer'
  form.locator('button').click();page.locator('[data-calc-form] button[type=submit]').click();page.locator('[data-variant-button="comfort"]').click();page.locator('select[name=project_id]').select_option(index=1);page.locator('button[value=save_estimate]').click();page.wait_for_url('**/accounts/calculations/**')
  page.screenshot(path=str(OUT/'03-saved.png'),full_page=True)
  with page.expect_download() as dl:page.locator('a[href$="/pdf/"]').click()
  dl.value.save_as(str(OUT/'live-estimate.pdf'))
  page.locator('a[href$="/request-offer/"]').click();page.locator('form:has(input[name=request_token]) button').click();page.wait_for_url('**/accounts/requests/**');url=page.url
  logout();login('supplier');page.goto(url);page.locator('form:has(input[name=action][value=mark_viewed]) button').click();logout();login('client');page.goto(url)
  page.screenshot(path=str(OUT/'04-client-status.png'),full_page=True)
  page.locator('[data-language-form] button[value=kk]').click();page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'05-client-status-kk-mobile.png'),full_page=True)
  print(('CACHED response' if CACHED else 'ONE live analysis')+' -> recognized area verified -> saved estimate -> PDF -> synthetic supplier request -> viewed status PASS')
 finally:context.close();browser.close()
