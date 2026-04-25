from playwright.sync_api import sync_playwright
import time
matches = ['594742','594746','596400','596420']
with sync_playwright() as p:
  br = p.chromium.launch(headless=True)
  pg = br.new_page()
  for mid in matches:
    pg.goto(f'https://www.vlr.gg/{mid.strip()}', wait_until='domcontentloaded')
    time.sleep(2)
    el = pg.query_selector('.match-header-note')
    txt = el.inner_text().strip() if el else 'NOT FOUND'
    print(f'{mid.strip()}: {txt}')
  br.close()
