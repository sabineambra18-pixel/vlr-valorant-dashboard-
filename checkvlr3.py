from playwright.sync_api import sync_playwright
import time
matches = ['595630','595631','595632','595633','595634','595635','595636','595639','594761','594762','594763','594764','598921','598922','598928','598929','598930','596406','596407']
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
