import re
import sys
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---

TEAM_URLS = [
    "https://www.vlr.gg/team/matches/13807/nova-esports-gc/?group=completed",
    "https://www.vlr.gg/team/matches/18418/ninetails/?group=completed",
    "https://www.vlr.gg/team/matches/15317/xipto-esports-gc/?group=completed",
    "https://www.vlr.gg/team/matches/8050/mibr-gc/?group=completed",
    "https://www.vlr.gg/team/matches/15119/giantx-gc/?group=completed",
    "https://www.vlr.gg/team/matches/7055/team-liquid-brazil/?group=completed",
    "https://www.vlr.gg/team/matches/7511/kr-blaze/?group=completed",
    "https://www.vlr.gg/team/matches/12255/karmine-corp-gc/?group=completed",
    "https://www.vlr.gg/team/matches/6530/g2-gozen/?group=completed",
    "https://www.vlr.gg/team/matches/14278/shopify-rebellion-gold/?group=completed"
]

START_DATE_STR = "2025-04-29"  # YYYY-MM-DD
DEBUG = True

# ---------------------

def parse_vlr_date(date_text):
    """Parses VLR date strings."""
    if not date_text: return None
    now = datetime.now()
    text = date_text.strip().lower()
    
    if "today" in text: return now
    if "yesterday" in text: return now - timedelta(days=1)
    
    m_ago = re.search(r"(\d+)([dh])\s+ago", text)
    if m_ago:
        val, unit = int(m_ago.group(1)), m_ago.group(2)
        return now - timedelta(days=val) if unit == 'd' else now

    m_ymd = re.search(r"(\d{4})/(\d{2})/(\d{2})", text)
    if m_ymd:
        try: return datetime.strptime(m_ymd.group(0), "%Y/%m/%d")
        except ValueError: pass

    m_date = re.search(r"([a-z]{3})\s+(\d+)(?:,\s+(\d{4}))?", text)
    if m_date:
        month_str, day = m_date.group(1), int(m_date.group(2))
        year = int(m_date.group(3)) if m_date.group(3) else now.year
        try:
            dt = datetime.strptime(f"{month_str} {day} {year}", "%b %d %Y")
            if not m_date.group(3) and dt > now: dt = dt.replace(year=year - 1)
            return dt
        except ValueError: return None
    return None

def get_match_ids(urls):
    start_date = datetime.strptime(START_DATE_STR, "%Y-%m-%d")
    unique_ids = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for url in urls:
            print(f"\n--- Processing: {url} ---")
            try:
                page.goto(url, wait_until="domcontentloaded")
                match_elements = page.query_selector_all("a.wf-card.m-item")
                print(f"Found {len(match_elements)} matches on page.")
                
                count_new = 0
                for el in match_elements:
                    href = el.get_attribute("href")
                    if not href: continue
                    
                    m_id = re.search(r"/(\d+)/", href)
                    if not m_id: continue
                    match_id = m_id.group(1)
                    
                    # Extract Date
                    date_div = el.query_selector(".m-item-date")
                    date_text = date_div.inner_text() if date_div else ""
                    clean_text = re.sub(r"\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?", "", date_text).strip()
                    
                    dt = parse_vlr_date(clean_text)
                    
                    if dt and dt >= start_date:
                        unique_ids.add(match_id)
                        count_new += 1
                        if DEBUG: print(f"  [+] Added {match_id} ({dt.strftime('%Y-%m-%d')})")
                
                print(f"-> Found {count_new} valid matches from this team.")
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")
            
            # Polite delay between pages
            time.sleep(1)

        browser.close()
        
    return sorted(list(unique_ids))

if __name__ == "__main__":
    if not TEAM_URLS:
        print("Please add links to the TEAM_URLS list in the script!")
    else:
        ids = get_match_ids(TEAM_URLS)
        
        if ids:
            print("\n" + "="*60)
            print(f"Total Unique Matches Found: {len(ids)}")
            print("="*60)
            cmd = f"python vlr_veto_and_result.py {' '.join(ids)}"
            print("\nRUN THIS COMMAND:\n")
            print(cmd)
            print("\n" + "="*60)
        else:
            print("No matches found in that date range.")