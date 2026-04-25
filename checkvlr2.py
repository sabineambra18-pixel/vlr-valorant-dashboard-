from playwright.sync_api import sync_playwright
import time
matches = ['594753','594754','594755','594756','595637','595638','595641','595642','596398','596399','596401','596413','596423','598932','598933','598934','598935',' 598943','598944']
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
