"""Local layout acceptance. No analysis form is submitted, no external API calls."""
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('meeting-demo-data/typical-final-layout');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',chromium_sandbox=True)
 for width in (1440,390):
  c=b.new_context(viewport={'width':width,'height':900});page=c.new_page()
  for lang in ('ru','kk'):
   page.goto('http://127.0.0.1:8220/projects/upload/');page.locator('[data-language-form] button[value='+lang+']').click()
   page.locator('a[href="#typical-plans"]').click();assert page.locator('#typical-plans').evaluate('(e)=>e.open')
   assert page.locator('.typical-card').count()==3
   for img in page.locator('.typical-card img').all():
    img.scroll_into_view_if_needed();page.wait_for_function('(e)=>e.complete && e.naturalWidth>0',arg=img.element_handle())
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
   page.screenshot(path=str(OUT/f'catalog-{lang}-{width}.png'),full_page=True)
   with page.expect_popup() as enlarged:page.locator('.typical-card a').first.click()
   popup=enlarged.value;popup.wait_for_load_state();assert popup.locator('img').evaluate('(e)=>e.naturalWidth>=1000');popup.close()
  c.close()
 b.close()
print('RU/KK desktop1440/mobile390 catalogue, direct secondary CTA, image zoom, no overflow PASS')
