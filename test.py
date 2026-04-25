from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    br = p.chromium.launch(headless=False)
    pg = br.new_page()
    pg.goto("https://www.vlr.gg/598923", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Check structure
    pills = pg.query_selector_all('.vm-stats-gamesnav-item')
    blocks = pg.query_selector_all('.vm-stats-game')
    
    print(f"Pills: {len(pills)}")
    print(f"Blocks: {len(blocks)}")
    
    for i in range(len(blocks)):
        gid = blocks[i].get_attribute('data-game-id')
        print(f"Block {i}: game_id={gid}")
    
    input("Press Enter to close...")
    br.close()
