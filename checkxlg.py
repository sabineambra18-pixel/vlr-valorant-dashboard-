from playwright.sync_api import sync_playwright
import time
for mid in ['598930','598941']:
  with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    pg = br.new_page()
    pg.goto(f'https://www.vlr.gg/{mid}', wait_until='domcontentloaded')
    time.sleep(2)
    el = pg.query_selector('.match-header-note')
    txt = el.inner_text().strip() if el else 'NOT FOUND'
    print(f'{mid}: {txt}')
    br.close()
