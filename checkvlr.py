from playwright.sync_api import sync_playwright
import time
matches = {'Americas': '596405', 'EMEA': '594740', 'Pacific': '594748', 'China': '598925'}
with sync_playwright() as p:
  br = p.chromium.launch(headless=True)
  pg = br.new_page()
  for region, mid in matches.items():
    pg.goto(f'https://www.vlr.gg/{mid}', wait_until='domcontentloaded')
    time.sleep(2)
    el = pg.query_selector('.match-header-note')
    txt = el.inner_text().strip() if el else 'NOT FOUND'
    print(f'{region} ({mid}): {txt}')
  br.close()
