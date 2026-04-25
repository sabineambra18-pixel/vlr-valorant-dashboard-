#!/usr/bin/env python3
"""
rib.gg Scraper - Extract breakdown and economy stats with round counts
Usage: python rib_scraper.py 95563 --output ./rib_data
"""

import json
import re
from typing import Dict, Optional
from playwright.sync_api import sync_playwright
import argparse
import os

def parse_percentage(text: str) -> Optional[int]:
    """Extract percentage: '75%' -> 75"""
    if not text or text.strip() == '-':
        return None
    m = re.search(r'(\d+)%', text)
    return int(m.group(1)) if m else None

def parse_rounds(text: str) -> Dict[str, int]:
    """Parse '3W / 4 Rounds' -> {wins: 3, total: 4}"""
    m = re.search(r'(\d+)W?\s*/\s*(\d+)\s*Rounds?', text, re.IGNORECASE)
    if m:
        return {"wins": int(m.group(1)), "total": int(m.group(2))}
    return {"wins": 0, "total": 0}

def scrape_series(series_id: str, headless: bool = True) -> Dict:
    """Scrape rib.gg series data"""
    
    print(f"\n🔍 Scraping rib.gg series: {series_id}")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        
        results = {"total": {}, "attack": {}, "defense": {}}
        
        for view in ["total", "attack", "defense"]:
            url = f"https://www.rib.gg/series/{series_id}?view={view}&tab=team-stats"
            print(f"\n📡 Loading {view} view...")
            
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # Extract raw data
            data = page.evaluate("""
                () => {
                    // Find BREAKDOWN section
                    const breakdownHeader = Array.from(document.querySelectorAll('*'))
                        .find(el => el.textContent?.trim().toUpperCase() === 'BREAKDOWN');
                    
                    // Find ECONOMY section
                    const economyHeader = Array.from(document.querySelectorAll('*'))
                        .find(el => el.textContent?.trim().toUpperCase() === 'ECONOMY');
                    
                    const getTexts = (header) => {
                        if (!header) return [];
                        const container = header.parentElement?.parentElement || header.parentElement;
                        const texts = Array.from(container.querySelectorAll('*'))
                            .map(el => el.textContent?.trim())
                            .filter(t => t && t.length > 0 && t.length < 100);
                        return [...new Set(texts)]; // Unique values
                    };
                    
                    // Extract team names
                    const teamElems = document.querySelectorAll('[class*="team"], h2');
                    const teamNames = [];
                    teamElems.forEach(el => {
                        const text = el.textContent?.trim();
                        if (text && text.length > 2 && text.length < 50) {
                            teamNames.push(text);
                        }
                    });
                    
                    return {
                        teams: [...new Set(teamNames)].slice(0, 10),
                        breakdown: getTexts(breakdownHeader),
                        economy: getTexts(economyHeader),
                        page_text: document.body.innerText.split('\\n').slice(0, 50)
                    };
                }
            """)
            
            results[view] = data
            
            # Print findings for total view
            if view == "total":
                print(f"✓ Teams found: {data.get('teams', [])[:2]}")
                print(f"✓ Breakdown lines: {len(data.get('breakdown', []))}")
                print(f"✓ Economy lines: {len(data.get('economy', []))}")
        
        # Screenshot
        screenshot_path = f"/mnt/user-data/outputs/rib_{series_id}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n📸 Screenshot saved: {screenshot_path}")
        
        browser.close()
    
    # Parse the data
    total_data = results["total"]
    
    # Parse breakdown
    breakdown = parse_breakdown(total_data.get("breakdown", []))
    print(f"\n✓ Breakdown stats:")
    for stat, vals in breakdown.items():
        if vals.get("left") or vals.get("right"):
            print(f"  {stat}: {vals['left']} vs {vals['right']}")
    
    # Parse economy  
    economy = parse_economy(total_data.get("economy", []))
    print(f"\n✓ Economy stats:")
    for buy_type, vals in economy.items():
        left = vals.get("left", {})
        right = vals.get("right", {})
        if left.get("total", 0) > 0 or right.get("total", 0) > 0:
            print(f"  {buy_type}: {left.get('winrate')}% ({left.get('wins')}/{left.get('total')}) vs " + 
                  f"{right.get('winrate')}% ({right.get('wins')}/{right.get('total')})")
    
    return {
        "series_id": series_id,
        "teams": total_data.get("teams", [])[:2],
        "breakdown": breakdown,
        "economy": economy,
        "raw_data": results
    }

def parse_breakdown(raw_text: list) -> Dict:
    """Parse breakdown stats"""
    stats = {
        "pistol_rounds": {"left": None, "right": None},
        "first_kills": {"left": None, "right": None},
        "sniper_kills": {"left": None, "right": None},
        "kast": {"left": None, "right": None},
        "clutches": {"left": None, "right": None}
    }
    
    for i, text in enumerate(raw_text):
        text_lower = text.lower()
        
        if 'pistol' in text_lower and i > 0 and i < len(raw_text) - 1:
            stats["pistol_rounds"]["left"] = raw_text[i-1]
            stats["pistol_rounds"]["right"] = raw_text[i+1]
        if 'first kill' in text_lower and i > 0 and i < len(raw_text) - 1:
            stats["first_kills"]["left"] = raw_text[i-1]
            stats["first_kills"]["right"] = raw_text[i+1]
        if 'sniper' in text_lower and i > 0 and i < len(raw_text) - 1:
            stats["sniper_kills"]["left"] = raw_text[i-1]
            stats["sniper_kills"]["right"] = raw_text[i+1]
        if 'kast' in text_lower and i > 0 and i < len(raw_text) - 1:
            stats["kast"]["left"] = parse_percentage(raw_text[i-1])
            stats["kast"]["right"] = parse_percentage(raw_text[i+1])
        if 'clutch' in text_lower and i > 0 and i < len(raw_text) - 1:
            stats["clutches"]["left"] = raw_text[i-1]
            stats["clutches"]["right"] = raw_text[i+1]
    
    return stats

def parse_economy(raw_text: list) -> Dict:
    """Parse economy with round counts"""
    stats = {
        "eco": {"left": {}, "right": {}},
        "semi_eco": {"left": {}, "right": {}},
        "half_buy": {"left": {}, "right": {}},
        "full_buy": {"left": {}, "right": {}}
    }
    
    for i, text in enumerate(raw_text):
        text_lower = text.lower()
        
        if 'eco' in text_lower and '0-5k' in text_lower and i > 0 and i < len(raw_text) - 1:
            left_text = raw_text[i-1]
            stats["eco"]["left"]["winrate"] = parse_percentage(left_text)
            stats["eco"]["left"].update(parse_rounds(left_text))
            
            right_text = raw_text[i+1]
            stats["eco"]["right"]["winrate"] = parse_percentage(right_text)
            stats["eco"]["right"].update(parse_rounds(right_text))
        
        if 'semi-eco' in text_lower and i > 0 and i < len(raw_text) - 1:
            left_text = raw_text[i-1]
            stats["semi_eco"]["left"]["winrate"] = parse_percentage(left_text)
            stats["semi_eco"]["left"].update(parse_rounds(left_text))
            
            right_text = raw_text[i+1]
            stats["semi_eco"]["right"]["winrate"] = parse_percentage(right_text)
            stats["semi_eco"]["right"].update(parse_rounds(right_text))
        
        if 'half-buy' in text_lower and i > 0 and i < len(raw_text) - 1:
            left_text = raw_text[i-1]
            stats["half_buy"]["left"]["winrate"] = parse_percentage(left_text)
            stats["half_buy"]["left"].update(parse_rounds(left_text))
            
            right_text = raw_text[i+1]
            stats["half_buy"]["right"]["winrate"] = parse_percentage(right_text)
            stats["half_buy"]["right"].update(parse_rounds(right_text))
        
        if 'full-buy' in text_lower and i > 0 and i < len(raw_text) - 1:
            left_text = raw_text[i-1]
            stats["full_buy"]["left"]["winrate"] = parse_percentage(left_text)
            stats["full_buy"]["left"].update(parse_rounds(left_text))
            
            right_text = raw_text[i+1]
            stats["full_buy"]["right"]["winrate"] = parse_percentage(right_text)
            stats["full_buy"]["right"].update(parse_rounds(right_text))
    
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("series_id", help="Series ID from rib.gg URL")
    parser.add_argument("--output", default="./rib_data", help="Output directory")
    parser.add_argument("--no-headless", action="store_true", help="Show browser")
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    data = scrape_series(args.series_id, headless=not args.no_headless)
    
    output_path = os.path.join(args.output, f"series_{args.series_id}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ SUCCESS! Saved to: {output_path}")

if __name__ == "__main__":
    main()